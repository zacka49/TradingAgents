# Day Trading Volatility Research

Updated: 2026-05-04

This knowledge file turns the day-trading research request into operating
guidance for the TradingAgents paper business.

## Core Finding

Day trading should not be treated as one strategy. The business should first
classify the market condition, then apply only the strategies suited to that
condition:

- Trending/high-volume: momentum breakout or relative-strength continuation.
- Trending but pulling back: watch for VWAP/support reclaim.
- Choppy/range-bound: range reversion only with explicit support/resistance.
- News shock/overextended move: news review or fade watch, not blind entry.
- Scalping: avoid until the system has real-time spreads/order-flow and low
  latency controls.

## Strategy Notes

### Scalping

Scalping tries to capture very small moves over seconds or minutes. It needs
fast execution, real-time data, tight spreads, and discipline. This is not a
good first automation strategy for the current hardware/data setup.

### Momentum Trading

Momentum trading looks for significant directional movement confirmed by
volume. The business now maps this to `momentum_breakout` and allows
autonomous paper trades only when price and volume conditions are strong.

### Range Trading

Range trading buys near support and sells near resistance. It can work in
choppy markets, but it requires explicit range boundaries. The business now
keeps this as `range_reversion_watch`, not auto-trade.

### News-Based Trading

News can create sharp moves, but delayed or stale news is dangerous. The
business should use news as a catalyst flag and defer to Codex/research review
unless a reliable current news feed is available.

### Breakout Trading

Breakouts can work well in volatile markets when price clears resistance with
volume. False breakouts reverse quickly, so autonomous entries need predefined
stops and capped position size.

### Fading

Fading trades against an overextended move. This is high-risk because strong
momentum can continue. The business should classify it as watch-only for now.

### Stop-Loss Orders

Every autonomous day-trading plan should include a predefined loss limit.
The paper runner now computes stop-loss and take-profit prices for buy plans
and attempts broker-supported protective exits where possible.

## Business Changes Made

- Added `day_trading_strategy.py` strategy classification.
- Added strategy labels and confidence to the CEO briefing pack.
- Added autonomous paper mode through `--autonomous-paper`.
- Kept hard gates: market open, order notional cap, deploy cap, liquidity
  filter, and paper-only execution.
- Added optional bracket-order payload fields to the Alpaca paper adapter.
- Added a repo-local Codex skill:
  `.agents/skills/day-trading-research/SKILL.md`

## Sources

- FINRA day trading/PDT overview:
  https://www.finra.org/investors/investing/investment-products/stocks/day-trading
- Investor.gov PDT glossary:
  https://www.investor.gov/index.php/introduction-investing/investing-basics/glossary/pattern-day-trader
- SEC risk publication:
  https://www.sec.gov/about/reports-publications/investor-publications/day-trading-your-dollars-at-risk
- Schwab volatile-market trading:
  https://www.schwab.com/learn/story/how-traders-can-take-advantage-volatile-markets
- Schwab technical filtering:
  https://www.schwab.com/learn/story/filtering-market-using-technical-analysis
- Schwab VWAP:
  https://www.schwab.com/learn/story/how-to-use-volume-weighted-indicators-trading
- IBKR volatility:
  https://www.interactivebrokers.com/campus/trading-lessons/volatility/
- Alpaca order docs:
  https://docs.alpaca.markets/docs/trading/orders/
- Alpaca fractional trading:
  https://docs.alpaca.markets/v1.3/docs/fractional-trading
