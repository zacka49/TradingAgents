# Day-Trading Stock Selection And Pre-Open Research - 2026

Paper account only. This is operating research for the TradingAgents day-trader
business, not financial advice.

## What Makes A Stock Worth Day-Trading

A day-trading candidate should be interesting because it can be entered, exited,
and invalidated quickly. The business should prefer:

- Liquidity: high average volume, active current volume, tight bid/ask spread,
  and enough depth that exits are realistic.
- Usable volatility: enough movement to create reward, but not so much that
  stops become meaningless or sizing becomes reckless.
- Relative volume: current activity above the symbol's own baseline, especially
  when paired with a fresh catalyst.
- Directional attention: price strength or weakness versus `SPY`, `QQQ`, and
  the relevant sector/theme proxy.
- A clear catalyst when news is driving the move: earnings, guidance, analyst
  action, FDA/regulatory events, macro/policy changes, product/contracts,
  commodity/FX/crypto moves, or sector rotation.
- A tradeable setup: opening-range breakout, momentum breakout, relative
  strength continuation, pivotal-point volume breakout, or another named setup
  with stop, target, and invalidation.

The business should downgrade:

- Wide spreads, stale trades, weak recent volume, or no live quote.
- Huge unconfirmed moves with no catalyst.
- Buyouts, trading halts, bankruptcy/delisting, dilution/offering headlines,
  fraud/probe/lawsuit headlines, and guidance cuts.
- Generic "interesting company" stories that do not create same-day attention.

## Pre-Open Way Of Working

1. Catalyst Reader runs before the open and builds a research queue from news,
   politics, macro, policy, earnings/guidance, analyst-action, FDA/regulatory,
   commodity, FX, crypto, and sector/theme headlines.
2. Market Data Reader expands the base liquid universe with directly mentioned
   tickers and liquid theme proxies.
3. Strategy Lab scores each symbol for day-trade fit: liquidity, relative
   volume, useful volatility, meaningful move, and catalyst quality.
4. Risk Controller marks `risk_review` for halt/dilution/legal/buyout-style
   headlines and prevents those headlines from becoming automatic entries.
5. At the open, the live scanner must confirm trade, quote, spread, volume,
   opening-range/VWAP behavior, and backtest evidence before order planning.
6. Execution Controller may place Alpaca paper orders only after deterministic
   gates pass. News alone cannot authorize a trade.
7. Report Writer records the pre-open queue, catalyst tags, thesis, live
   candidates, blocked reasons, orders, and end-of-day results.

## Implementation Notes

- `tradingagents/dataflows/news_politics_discovery.py` now classifies catalysts
  into actionable day-trading tags and returns `ranked_research_queue`.
- `tradingagents/company/codex_ceo_company.py` carries pre-open research action,
  thesis, catalyst direction, news risk tags, and day-trade fit score into each
  candidate and the briefing report.
- `tradingagents/company/autonomous_ceo.py` can run a non-ordering premarket
  research pass while waiting for the next market open.
- `safe` and `risky` profiles now use the day-trade fit score when the scanner
  has enough evidence, and both profiles include `momentum_breakout` because the
  latest backtests ranked it as the best broad native strategy.

## Research Sources

- FINRA explains PDT/account-risk requirements and emphasizes that day trading
  creates meaningful intraday financial risk:
  https://www.finra.org/investors/investing/investment-products/stocks/day-trading
- Investor.gov summarizes the four-or-more day-trades in five business days PDT
  threshold:
  https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/margin
- Alpaca's Python market-data docs confirm access patterns for live/historical
  bars, trades, quotes, and real-time quote subscriptions:
  https://alpaca.markets/sdks/python/market_data.html
- Investopedia's intraday stock-selection guide emphasizes liquidity, volume,
  volatility, relative strength/weakness, spreads, and exit discipline:
  https://www.investopedia.com/day-trading/pick-stocks-intraday-trading/
- IBKR's volatility lesson frames volatility as a calculated risk/movement
  measure and notes that recent volatility is useful for short-term expectation:
  https://www.interactivebrokers.com/campus/trading-lessons/volatility/
- Warrior Trading's scanner/writeup is a practitioner source for relative
  volume, gap, float, and breaking-news watchlist behavior:
  https://www.warriortrading.com/day-trading--watch-list-top-stocks-to-watch/
