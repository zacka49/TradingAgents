# Day-Trader AI Research Program - 2026

Paper account only. This is a research and training doctrine for autonomous
paper-trading agents, not financial advice.

## Operating Thesis

The day-trader system should behave like a small trading business:

- Research desk: find liquid intraday opportunities across equities, ETFs,
  sector/theme proxies, and broker-supported crypto where configured.
- Trading desk: convert only clean, named setups into orders.
- Risk office: veto poor liquidity, stale feeds, oversized exposure, excessive
  drawdown, near-close entries, and overnight carry in day-trading mode.
- Portfolio office: keep account-level exposure, concentration, and open-order
  state coherent.
- Operations desk: reconcile fills, cancel stale orders, flatten the account,
  and write daily summaries.
- Evaluation desk: label every trade, measure expectancy, and promote/demote
  strategies from evidence rather than vibes.

## Non-Negotiable Day-Trading Rules

- Flat by default: no overnight holdings in day-trading mode.
- Stop new entries before the closing window.
- Cancel open orders before flattening.
- Close all open intraday positions before the market close.
- Protect intraday winners: after a position has moved in favor, monitor its
  high-watermark and sell when the giveback breaches the configured threshold.
- Cut stale losers: do not wait for a distant take-profit if a day-trade
  position is already down beyond the configured intraday loss threshold.
- Do not leave unprotected remainders: fractional leftovers or positions without
  adequate open sell-order coverage should be exited in day-trading mode.
- Cap simultaneous active positions; if the book is full, new ideas stay on the
  watchlist until capital and attention are freed.
- Do not let multiple strategy desks build the same symbol in the same cycle;
  one fill should be reconciled before another desk adds to that ticker.
- Treat zero-trade backtests as no evidence, not approval.
- No autonomous trade without fresh price, clean spread, sufficient volume, and
  a named strategy.
- News and politics can expand the watchlist, but cannot authorize a trade by
  themselves.
- Pre-open research should create the day's interest list from catalysts,
  liquidity, relative volume, volatility, and market/sector attention; the open
  session must still confirm spreads, live volume, strategy, and risk gates.
- Avoid direct spot forex assumptions in the current Alpaca equity workflow.
  Use currency ETFs as tradable proxies unless a dedicated FX broker/data stack
  is integrated.

## Current Tradable Universe Policy

The default scanner should cover:

- Broad index ETFs: `SPY`, `QQQ`, `IWM`, `DIA`.
- Sector ETFs: `XLK`, `XLF`, `XLE`, `XLV`, `XLY`, `XLI`, `SOXX`.
- Rates/commodity/currency proxies: `TLT`, `GLD`, `UUP`, `FXE`, `FXY`, `FXB`,
  `FXA`, `FXC`.
- High-liquidity mega-cap and catalyst stocks: semis, AI/data-center names,
  banks, energy, healthcare, defense, crypto proxies, and selected high-volume
  retail/cyclical names.
- Crypto only when the account, jurisdiction, and broker asset class support
  it. Crypto does not share all equity/bracket-order assumptions.

## Strategy Curriculum

The agents should learn these as separate playbooks, each with entry trigger,
confirmation, invalidation, risk, sizing, and review labels:

- Pivotal-point volume breakout.
- NR7/compression-filtered opening range breakout.
- Volume-confirmed chart breakout.
- Opening range breakout.
- Momentum breakout.
- Relative-strength continuation.
- VWAP reclaim.
- Pullback-to-VWAP continuation.
- Range reversion.
- News shock continuation.
- News shock fade.
- Liquidity sweep/reclaim.
- Gap-and-go.
- Gap-fill attempt.
- Index-led sector rotation.
- Macro/rates-led ETF rotation.
- Earnings/analyst-action watch mode.
- Halt/resumption watch mode.

Only strategies with tests, live-data gates, and risk controls should be
eligible for autonomous paper execution.

## Famous Trader Playbook Translation

Reference report:
`knowledge/famous_day_trader_playbook_backtests_2026.md`.

The agents should study famous day traders as structured case studies, not as
heroes to copy. Public trader material becomes useful only after it is converted
into:

- A named setup.
- A measurable trigger.
- Confirmation gates.
- Invalidation and stop logic.
- Position sizing and account-risk limits.
- Holding-period rules.
- Post-trade review tags.

The 2026-05-07 proxy backtest found the strongest recent long-only intraday
evidence in pivotal-point volume breakouts, NR7/compression-filtered ORB, and
volume-confirmed chart breakouts. Turtle Soup reclaim was positive but too
drawdown-heavy. Gap momentum, broad ORB/VWAP, loose price-action pullbacks, VCP,
Episodic Pivot, and TTM Squeeze proxies need tighter catalyst, regime, and
multi-timeframe filters before promotion.

Promotion rule of thumb: do not move a public playbook beyond paper-watch unless
it has positive expectancy, profit factor above 1.15, at least 50 trades, max
drawdown below 8%, and survives a different time window/universe.

## Data Curriculum

Minimum live context per candidate:

- Latest trade, latest quote, bid/ask size, spread, quote imbalance.
- Intraday bars, current minute bar, current daily bar, previous daily close.
- Recent volume versus baseline volume.
- VWAP and price relation to VWAP.
- Opening range high/low.
- Relative strength versus `SPY` and `QQQ`.
- Sector ETF alignment.
- Recent prints/order-flow features: volume profile, point of control, delta,
  large prints, and absorption flags.
- News/politics catalyst tags and recent headlines.
- Pre-open research action: `priority_research`, `confirm_at_open`,
  `risk_review`, or `watch`.
- Day-trade fit score: liquidity, relative volume, useful volatility,
  meaningful move, and spread when available.
- Account context: existing position, open orders, buying power, daytrade count,
  deployment, concentration, and time to close.

Preferred future data additions:

- Alpaca stock market-data WebSocket for lower-latency trades/quotes/bars.
- Trade-update stream for order/fill state instead of REST polling only.
- True order book/depth provider for L2/L3 heatmaps.
- Official economic calendar and central-bank calendar.
- Corporate-events calendar: earnings, splits, dividends, analyst actions.
- Halt/resumption feed.
- Options chain/open-interest/IV surfaces for watch mode before execution.

## Research Backlog

1. Validate the new pre-open catalyst queue against daily outcomes: what was in
   play at 09:30 ET, what actually moved, and what the bot ignored correctly.
2. Build a replayable intraday backtest harness using one-minute bars and
   recorded quote/order-flow snapshots.
3. Add walk-forward evaluation by market regime: trend day, range day, high-vol
   open, Fed/news day, low-volume holiday session.
4. Add pre-trade checklist scoring and post-trade labels.
5. Add daily flatness reconciliation: positions, orders, fills, P/L attribution,
   and strategy expectancy.
6. Add a strategy registry with promotion levels: research-only, paper-watch,
   paper-trade, live-eligible.
7. Add slippage and spread-cost modeling.
8. Add kill switches: daily loss, consecutive losers, stale data, widened
   spreads, API errors, late-session risk, and PDT/account restrictions.
9. Add currency/forex plan: decide whether to remain with ETF proxies or add a
   dedicated FX broker/data provider.
10. Add crypto plan: separate 24/7 risk model, no equity market-close assumption,
   and no unsupported bracket-order assumptions.
11. Add agent training evals: give each role historical cases and score whether
    it produced a correct veto, entry, exit, or stand-down.

## Primary Source Anchors

- FINRA day-trading overview:
  https://www.finra.org/investors/investing/investment-products/stocks/day-trading
- FINRA day-trading risk disclosure:
  https://www.finra.org/rules-guidance/rulebooks/finra-rules/2270
- Investor.gov pattern day trader glossary:
  https://www.investor.gov/index.php/introduction-investing/investing-basics/glossary/pattern-day-trader
- Alpaca close all positions:
  https://docs.alpaca.markets/reference/deleteallopenpositions-1
- Alpaca trading orders:
  https://docs.alpaca.markets/docs/trading/orders/
- Alpaca real-time stock data:
  https://docs.alpaca.markets/docs/real-time-stock-pricing-data
- Alpaca assets API:
  https://docs.alpaca.markets/reference/get-v2-assets-1
- Alpaca crypto trading:
  https://docs.alpaca.markets/docs/crypto-trading
- Alpaca options trading:
  https://docs.alpaca.markets/docs/options-trading

## Training Prompt Contract

Every trading agent should internalize this contract:

1. Start with market regime and data quality.
2. Treat news/politics as context, not a standalone entry.
3. Prefer liquid index/sector proxies when macro news is broad.
4. Require a named strategy and invalidation before order planning.
5. Size from account risk, not excitement.
6. Exit before the close in day-trading mode.
7. Write down what happened, why it happened, and what should change.
