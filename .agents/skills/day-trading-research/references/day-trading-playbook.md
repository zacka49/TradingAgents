# Day Trading Strategy Playbook

This reference supports the TradingAgents Codex CEO paper-trading business.
It is educational operating knowledge for paper trading, not a guarantee of
profitability.

## Source Anchors

- FINRA day trading overview and PDT rules:
  https://www.finra.org/investors/investing/investment-products/stocks/day-trading
- Investor.gov pattern day trader definition:
  https://www.investor.gov/index.php/introduction-investing/investing-basics/glossary/pattern-day-trader
- SEC day-trading risk disclosure:
  https://www.sec.gov/about/reports-publications/investor-publications/day-trading-your-dollars-at-risk
- Charles Schwab volatile-market trading guidance:
  https://www.schwab.com/learn/story/how-traders-can-take-advantage-volatile-markets
- Charles Schwab technical filtering guide:
  https://www.schwab.com/learn/story/filtering-market-using-technical-analysis
- Charles Schwab VWAP guide:
  https://www.schwab.com/learn/story/how-to-use-volume-weighted-indicators-trading
- IBKR volatility lesson:
  https://www.interactivebrokers.com/campus/trading-lessons/volatility/
- Alpaca order and bracket order docs:
  https://docs.alpaca.markets/docs/trading/orders/
- Alpaca fractional trading docs:
  https://docs.alpaca.markets/v1.3/docs/fractional-trading

## Strategy Library

### Momentum Breakout

Use when price has strong 1-day and 5-day momentum with relative volume.
Confirmation should include volume above the recent average and no severe
latest-session reversal. This is the main autonomous paper setup.

Default paper controls:

- Stop: 3.5% to 4.5%
- Take profit: 7% to 9%
- Avoid if the move is extremely extended without fresh news review.

### Relative Strength Continuation

Use when 5-day and 20-day returns are strong but the latest session is not an
exhaustion spike. This is a slower version of momentum trading and is allowed
for autonomous paper mode when confidence is high.

Default paper controls:

- Stop: 3% to 4%
- Take profit: 6% to 8%

### Pullback Watch

Use when the 20-day trend is strong but the latest day is weak. This can become
a VWAP reclaim or support-bounce trade, but it should not auto-buy without
intraday confirmation.

### Range Reversion Watch

Use when price is volatile but lacks clear directional momentum. Trade only
after support/resistance levels are explicit and the position can be stopped
tightly. This is not currently autonomous.

### Fade or News Watch

Use when price is overextended or news-driven. Fading can work, but it is a
specialist setup because momentum can continue longer than expected. Do not
auto-trade without current catalyst review.

### Scalping

Scalping requires real-time spreads, fast execution, level 2/order-flow data,
and tight latency control. This business should not automate scalping from
delayed/free data.

## Risk Gates

- Paper account only.
- Enforce market open for autonomous submission.
- Cap deployed capital and order notional.
- Prefer liquid names with average volume above 1 million shares.
- Avoid autonomous entries when the strategy classifier returns watch-only.
- Record all blocked or failed orders in artifacts.
- Review PDT/margin implications before copying behavior to any live account.

## Current Implementation

The strategy classifier lives in:

`tradingagents/company/day_trading_strategy.py`

The autonomous paper runner lives in:

`scripts/run_codex_ceo_company.py`

Use:

```powershell
.\.venv\Scripts\python.exe scripts\run_codex_ceo_company.py `
  --results-dir results `
  --max-deploy-usd 1250 `
  --target-positions 5 `
  --max-order-notional-usd 250 `
  --liquidate-non-targets `
  --autonomous-paper
```
