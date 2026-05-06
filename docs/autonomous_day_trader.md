# Autonomous Paper Day Trader

This runner is paper-only. The self-running CEO agent in
`tradingagents/company/autonomous_ceo.py` submits Alpaca paper orders without
per-trade approval, but it still enforces the Alpaca market clock, order caps,
buying power, duplicate-open-order suppression, and bracket exits.

## Environment

Required:

- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `APCA_API_BASE_URL=https://paper-api.alpaca.markets`
- `ALPACA_STOCK_FEED=iex` for the free/basic real-time IEX feed, or `sip` when
  your Alpaca plan supports the consolidated feed.

WhatsApp notifications:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_FROM`
- `WHATSAPP_TO`

Twilio WhatsApp senders and recipients should use E.164 numbers. The code adds
the `whatsapp:` prefix when it is missing.

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
  --interval-seconds 300 `
  --results-dir results/autonomous_day_trader
```

## Run During The Open Session

```powershell
.\.venv\Scripts\python.exe scripts\run_autonomous_day_trader.py `
  --strategy both `
  --run-until-close `
  --interval-seconds 300 `
  --results-dir results/autonomous_day_trader
```

## Profiles

`safe` minimizes loss exposure:

- smaller order cap
- fewer target positions
- higher confidence gate
- tighter stops and tighter take-profit brackets
- blocks high volatility, wide spreads, stale trades, and weak backtests

`risky` maximizes paper upside:

- larger order cap
- more target positions
- lower confidence gate
- wider stops and larger take-profit brackets
- allows more momentum-breakout behavior while still blocking stale/wide-spread
  data

## Data Sources

The realtime scanner uses Alpaca Market Data:

- 1-minute intraday bars for fast trend and volume ranking
- latest trades and quotes for entry reference, spread, and stale-data checks
- recent trades and top-of-book quotes for volume profile, delta, large prints,
  and absorption flags

Alpaca's docs note that Basic market data provides live IEX equity coverage,
while SIP requires the paid Algo Trader Plus plan. They also recommend stock
market-data websockets for the freshest stream, so the current polling loop is
kept short and isolated behind `tradingagents/dataflows/alpaca_realtime.py`.

References:

- [Alpaca placing orders](https://docs.alpaca.markets/docs/trading/orders/)
- [Alpaca market data FAQ](https://docs.alpaca.markets/docs/market-data-faq)
- [Alpaca latest trades endpoint](https://docs.alpaca.markets/reference/stocklatesttrades-1)
- [Alpaca real-time stock data](https://docs.alpaca.markets/docs/real-time-stock-pricing-data)
- [Twilio Messages API for WhatsApp](https://www.twilio.com/docs/messaging/api/message-resource)
