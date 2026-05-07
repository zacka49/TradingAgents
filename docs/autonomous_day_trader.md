# Autonomous Paper Day Trader

This runner is paper-only. The self-running CEO agent in
`tradingagents/company/autonomous_ceo.py` submits Alpaca paper orders without
per-trade approval, but it still enforces the Alpaca market clock, order caps,
buying power, duplicate-open-order suppression, and bracket exits.

By default it now behaves as a strict day trader: it stops opening new positions
15 minutes before the close, cancels working orders, and asks Alpaca to flatten
the paper account 5 minutes before the close. Disable this only for an explicit
swing/overnight experiment.

The live position monitor also protects intraday gains. It tracks each open
position's high-watermark while the bot is running and can submit a market sell
when a winner gives back too much profit. It also exits unprotected position
remainders, such as fractional leftovers or stale day-trading holdings that no
longer have enough open sell-order coverage.

## Environment

Required:

- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `APCA_API_BASE_URL=https://paper-api.alpaca.markets`
- `ALPACA_STOCK_FEED=iex` for the free/basic real-time IEX feed, or `sip` when
  your Alpaca plan supports the consolidated feed.

## Run Once

```powershell
.\.venv\Scripts\python.exe scripts\run_autonomous_day_trader.py `
  --strategy both `
  --once `
  --results-dir results/autonomous_day_trader
```

Equivalent CEO entrypoint:

```powershell
.\.venv\Scripts\python.exe scripts\run_autonomous_ceo.py `
  --strategy both `
  --run-until-close `
  --interval-seconds 30 `
  --position-monitor-seconds 5 `
  --results-dir results/autonomous_day_trader
```

## Run During The Open Session

```powershell
.\.venv\Scripts\python.exe scripts\run_autonomous_day_trader.py `
  --strategy both `
  --run-until-close `
  --interval-seconds 30 `
  --position-monitor-seconds 5 `
  --results-dir results/autonomous_day_trader
```

## Run From VS Code

Open `run_day_trader_bot.py` in VS Code and press Run Python File, or run:

```powershell
.\.venv\Scripts\python.exe run_day_trader_bot.py
```

This starts the autonomous CEO agent in Alpaca paper mode, runs both safe and
risky profiles every 30 seconds while the market is open, and checks live
positions/open orders every 5 seconds between full strategy scans. It writes a
JSONL session log under `results/autonomous_day_trader/live_logs/`. The same
events also stream to the VS Code terminal in plain English, for example when
the CEO is running research, monitoring live risk, reviewing strategies, or
placing a trade.

The default VS Code launcher now scans a broader liquid catalyst universe across
mega-cap tech, semis, crypto proxies, banks, healthcare, energy, defense,
indexes, and rates/commodity ETFs. The system also expands that base universe
from current news and political/policy themes before each strategy scan.

Useful knobs:

```powershell
.\.venv\Scripts\python.exe run_day_trader_bot.py `
  --news-query "tariffs semiconductor export controls" `
  --news-query "Federal Reserve rate cut bank stocks" `
  --news-max-symbols 75 `
  --alpaca-stock-feed sip
```

Use `--disable-news-politics` to run only the explicit universe. Use
`--alpaca-stock-feed sip` only when your Alpaca plan supports it; otherwise keep
`iex` or the value in `ALPACA_STOCK_FEED`.

Close-discipline knobs:

```powershell
.\.venv\Scripts\python.exe run_day_trader_bot.py `
  --flatten-minutes-before-close 5 `
  --stop-new-entries-minutes-before-close 15
```

Use `--disable-flatten-at-close` only when you explicitly want to test overnight
carry behavior. Use `--no-flatten-on-max-cycles` only when a bounded test run
should leave the paper account untouched after the final cycle.

Profit-protection knobs:

```powershell
.\.venv\Scripts\python.exe run_day_trader_bot.py `
  --profit-protection-min-gain-pct 0.75 `
  --profit-protection-max-giveback-pct 0.60 `
  --profit-protection-max-giveback-fraction 0.50 `
  --unprotected-position-grace-seconds 60
```

Use `--disable-profit-protection` only when comparing static bracket exits.
Use `--disable-unprotected-position-exit` only when intentionally allowing
manual or overnight leftovers to remain in the paper account.

## Profiles

`safe` minimizes loss exposure:

- minimum `$2,000` target notional per new paper order
- smaller order cap, currently up to about `$3,000` per new paper order
- up to 20% paper-account deployment by default on a `$100k` account
- higher confidence gate
- tighter stops and tighter take-profit brackets
- blocks high volatility, wide spreads, stale trades, and weak backtests

`risky` maximizes paper upside:

- minimum `$2,000` target notional per new paper order
- larger order cap, currently up to about `$5,000` per new paper order
- up to 30% paper-account deployment by default on a `$100k` account
- more target positions
- lower confidence gate
- wider stops and larger take-profit brackets
- allows more momentum-breakout behavior while still blocking stale/wide-spread
  data

## Data Sources

The realtime scanner uses Alpaca Market Data:

- 1-minute intraday bars for fast trend and volume ranking
- latest trades and quotes for entry reference, spread, and stale-data checks
- snapshots for combined latest trade, latest quote, latest minute bar, current
  daily bar, and previous daily bar context
- recent trades and top-of-book quotes for volume profile, delta, large prints,
  and absorption flags
- yfinance Search news for broad macro, politics, policy, and sector catalysts
  that can add related liquid tickers to the scan universe
- currency ETFs such as `UUP`, `FXE`, `FXY`, `FXB`, `FXA`, and `FXC` as tradable
  FX proxies; direct spot forex needs a dedicated FX broker/data integration
  because this Alpaca equities workflow is not a spot-forex execution stack

News/policy catalysts only expand and annotate the scan. They do not by
themselves authorize trades; price action, volume, spread, stale-data checks,
strategy confidence, order-flow enrichment, account exposure, and risk caps
still gate every paper order.

The broader research/training doctrine lives in
`knowledge/day_trader_ai_research_program_2026.md`.

Alpaca's docs note that Basic market data provides live IEX equity coverage,
while SIP requires the paid Algo Trader Plus plan. They also recommend stock
market-data websockets for the freshest stream, so the current polling loop is
kept short and isolated behind `tradingagents/dataflows/alpaca_realtime.py`.

References:

- [Alpaca placing orders](https://docs.alpaca.markets/docs/trading/orders/)
- [Alpaca close all positions](https://docs.alpaca.markets/reference/deleteallopenpositions-1)
- [Alpaca market data FAQ](https://docs.alpaca.markets/docs/market-data-faq)
- [Alpaca latest trades endpoint](https://docs.alpaca.markets/reference/stocklatesttrades-1)
- [Alpaca snapshots endpoint](https://docs.alpaca.markets/reference/stocksnapshots-1)
- [Alpaca real-time stock data](https://docs.alpaca.markets/docs/real-time-stock-pricing-data)
