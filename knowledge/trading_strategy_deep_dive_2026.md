# Trading Strategy Deep Dive: Research Doctrine for the Autonomous Paper Business

Updated: 2026-05-05

Scope: This document is the strategy doctrine for TradingAgents' autonomous
paper-trading business. It is not investment advice and must not be treated as
permission to trade live capital. The near-term implementation target is Alpaca
paper trading during regular US market hours with hard execution guardrails.

## Executive Summary

The central finding is simple but important: a trading strategy is not an
indicator. A usable strategy is a complete operating loop:

1. Regime classification
2. Instrument selection
3. Entry trigger
4. Confirmation filter
5. Invalidation/stop
6. Position sizing
7. Execution method
8. Exit logic
9. Post-trade review

The business should keep autonomous execution narrow. The evidence supports
long-side, high-liquidity, short-horizon paper trades built around:

- `momentum_breakout`
- `opening_range_breakout_15m`
- selective `relative_strength_continuation`

The following should remain research/watch-only until the system has stronger
evidence, cleaner data, and better execution tooling:

- broad `vwap_reclaim`
- broad `range_reversion_to_vwap`
- fading/news-shock reversal
- scalping
- short selling
- low-float momentum
- options
- overnight gap strategies

## Research Sources And What They Teach

### Regulatory And Risk Sources

FINRA defines day trading as buying and selling, or selling and buying, the same
security on the same day in a margin account. FINRA also explains pattern day
trader rules, including the four-or-more day-trade threshold and the $25,000
minimum equity requirement for margin accounts. This matters even when the
current implementation is paper-only because the software must avoid teaching
or reinforcing behavior that would break real brokerage constraints.

SEC investor guidance stresses that day trading is highly risky, often
stressful, expensive, and dependent on rapid decisions. The SEC specifically
warns that many day traders suffer severe losses early. The operational lesson
for this repo is that the system should use tiny paper sizing, bracket exits,
audit logs, and a learning loop before any live-capital discussion.

Sources:

- FINRA day trading overview: https://www.finra.org/investors/investing/investment-products/stocks/day-trading
- SEC day-trading risk publication: https://www.sec.gov/about/reports-publications/investor-publications/day-trading-your-dollars-at-risk
- Investor.gov pattern day trader glossary: https://www.investor.gov/index.php/introduction-investing/investing-basics/glossary/pattern-day-trader

### Academic / Quantitative Strategy Sources

Lo, Mamaysky, and Wang show that technical analysis can be studied
systematically instead of subjectively. Their practical lesson is not "chart
patterns always work"; it is that patterns must be encoded, tested, and compared
against unconditional returns.

Jegadeesh and Titman document intermediate-horizon momentum in equities. The
day-trading lesson is narrower: momentum exists as a broad phenomenon, but
intraday implementation must add liquidity, volume, spread, and stop controls.

Hurst, Ooi, and Pedersen review trend-following over a very long historical
sample and find positive average results across market environments. This
supports trend/momentum as a research pillar, but not blind minute-by-minute
chasing.

Order-flow research finds that order-flow imbalance contains information over
short horizons, especially with limit-order-book data. TradingAgents currently
uses Alpaca L1 trades/quotes, not true depth. Therefore order flow should be a
confirmation filter, not a standalone alpha source, until a depth provider is
added.

Opening-range breakout research has empirical support in the literature, and
the project's own 60-day 5-minute backtest ranked `opening_range_breakout_15m`
highly on AMD/NVDA. This justifies promoting the setup into the live paper
runner, but only for liquid names and only with volume/spread confirmation.

Sources:

- Lo, Mamaysky, Wang, "Foundations of Technical Analysis": https://www.nber.org/papers/w7613
- Hurst, Ooi, Pedersen, "A Century of Evidence on Trend-Following Investing": https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
- Jegadeesh/Titman momentum paper listing: https://www.researchgate.net/publication/4992307_Returns_to_Buying_Winners_and_Selling_Losers_Implications_for_Stock_Market_Efficiency
- Opening-range breakout study: https://www.sciencedirect.com/science/article/pii/S1544612312000438
- Deep order-flow imbalance: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3900141
- Multi-level order-flow imbalance: https://ideas.repec.org/p/arx/papers/1907.06230.html

### Broker/Data Sources

Alpaca's market-data docs state that streaming market data is more accurate and
performant than polling latest historical endpoints. The current polling loop is
acceptable for paper validation, but the next serious real-time upgrade should
be a websocket process that maintains latest trade/quote/bar state.

Alpaca bracket orders support take-profit and stop-loss legs around an entry.
This maps directly to the doctrine: every autonomous buy should have an exit
plan at order creation.

Alpaca fractional trading allows small notional or fractional share orders for
eligible securities. That supports tiny paper experiments, but the app should
continue to cap notional exposure and avoid overtrading.

Sources:

- Alpaca real-time stock data: https://docs.alpaca.markets/docs/real-time-stock-pricing-data
- Alpaca order docs: https://docs.alpaca.markets/docs/trading/orders/
- Alpaca fractional trading: https://docs.alpaca.markets/v1.3/docs/fractional-trading

### Practitioner Sources

Schwab describes VWAP as an intraday price benchmark weighted by volume. VWAP is
valuable, but a benchmark is not an entry signal by itself. The lesson for
TradingAgents is to use VWAP as a location/confirmation tool: trend trades above
VWAP are cleaner than long trades below it; reclaim trades need separate proof.

Interactive Brokers educational material emphasizes volatility as a central
trading condition. The system should adapt stop width and position size to
volatility rather than using one fixed percentage for every stock.

Sources:

- Schwab VWAP guide: https://www.schwab.com/learn/story/how-to-use-volume-weighted-indicators-trading
- Interactive Brokers volatility education: https://www.interactivebrokers.com/campus/trading-lessons/volatility/

## Strategy Taxonomy

### 1. Momentum Breakout

Goal: capture continuation when price breaks above a recent intraday range with
volume confirmation.

Good conditions:

- Liquid large-cap or major ETF
- Fresh trade and clean spread
- Price above VWAP
- Price breaks a recent rolling high
- Short-term return is positive but not absurdly extended
- Relative volume is above baseline
- Broad market is aligned, especially QQQ/SPY for tech names

Avoid:

- Stale latest trade
- Wide spread
- Low volume
- Breakout after repeated failed attempts
- Strong news uncertainty without current source confirmation
- Large move with no volume

Execution:

- Enter only after confirmation, not before the breakout
- Use bracket order
- Stop below recent structure or a volatility-adjusted percentage
- Take profit around 1.5R-2R for safe profile, wider for risky profile

Autonomous status: deploy selectively in paper mode.

### 2. Opening-Range Breakout

Goal: use the first 15 minutes to define the initial auction range, then trade a
clean break of that range when volume confirms direction.

Good conditions:

- First 15-minute range is clear
- Break happens early enough that there is still intraday opportunity
- Price is above VWAP or not materially below it
- Relative volume confirms interest
- Spread is controlled

Avoid:

- Choppy first range with multiple failed breaks
- Breaks after late morning without fresh catalyst
- Thin stocks
- No market-index support

Execution:

- Define opening high/low from first three 5-minute bars or first fifteen
  1-minute bars
- Enter long only on high break with volume
- Stop inside or below the opening range
- Take profit at roughly 1.5R-2R unless live order flow suggests exhaustion

Autonomous status: deploy selectively in paper mode. Recent local backtest
strongly supported AMD and NVDA variants.

### 3. Relative-Strength Continuation

Goal: trade a name that is already outperforming and holding above intraday
fair-value references.

Good conditions:

- Stock positive on session while SPY/QQQ are neutral or positive
- Price above VWAP
- EMA9 above EMA20, or equivalent short-trend confirmation
- Pullbacks hold above VWAP/EMA
- Volume remains healthy

Avoid:

- Continuation after a parabolic move
- Price above VWAP but volume fading
- News exhaustion after earnings/guidance gap

Execution:

- Enter on continuation after a shallow pullback or fresh high
- Stop below VWAP/EMA or recent higher low
- Keep size smaller than pure breakout unless backtest is strong for that ticker

Autonomous status: safe profile may use it only on proven leaders; risky profile
may use it with lower confidence threshold.

### 4. VWAP Reclaim

Goal: trade a recovery when price loses VWAP, then reclaims it with volume.

What research says:

- VWAP is useful as a benchmark and location filter.
- VWAP alone is not enough.
- The repo's recent backtest showed broad VWAP reclaim underperformed.

Autonomous status: watch-only. It can become deployable if future backtests show
positive expectancy for specific tickers and regimes.

### 5. Range Reversion To VWAP

Goal: buy an oversold intraday move and exit near VWAP.

Problem:

- Mean reversion can produce many small winners but larger failed-trend losses.
- The recent local backtest had weak aggregate results despite a decent win
  rate, which is exactly the trap with unfiltered reversion.

Autonomous status: watch-only. Requires stronger regime detection, trend filter,
and max-loss discipline before deployment.

### 6. Fading / News Shock Reversal

Goal: trade against an overextended move.

Problem:

- Strong momentum can continue longer than expected.
- A delayed news feed can make the system fade real information.
- This requires current catalyst classification, halt awareness, and fast
  execution.

Autonomous status: research-only.

### 7. Scalping

Goal: capture very small moves over seconds to minutes.

Problem:

- Needs streaming data, very low latency, robust spread/queue modeling, and
  precise fee/slippage modeling.
- Current polling + paper flow is not enough.

Autonomous status: do not deploy.

### 8. Order-Flow Confirmation

Goal: use trade prints, quote imbalance, delta, large trades, and absorption to
confirm or reject a price setup.

Current limitation:

- Alpaca L1 trades/quotes can derive useful features, but true liquidity
  heatmaps require depth such as MBP-10/MBO.

Autonomous status: confirmation-only. Do not let order-flow delta alone create a
trade.

## Strategy Selection Matrix

| Regime | Preferred Strategy | Allowed Autonomously | Required Confirmation |
| --- | --- | --- | --- |
| Strong trend, high volume | Momentum breakout | Yes, paper | Breakout + rel volume + clean spread |
| Early session auction expansion | Opening-range breakout | Yes, paper | 15m high break + volume + VWAP |
| Strong leader holds intraday trend | Relative-strength continuation | Selective | Above VWAP/EMA + index alignment |
| Choppy/range-bound | Range reversion | No | Needs range model and proof |
| VWAP loss/reclaim | VWAP reclaim | No | Needs stronger ticker-specific evidence |
| News shock/overextension | Fade/watch | No | Needs live catalyst/halt awareness |
| Ultra-short scalp | Scalping | No | Needs streaming/depth/latency stack |

## Backtesting Doctrine

Every strategy candidate must be tested with:

- explicit entry and exit rules
- no lookahead
- regular-session filtering
- costs/slippage
- trade count
- win rate
- average return
- expectancy
- total return
- profit factor
- max drawdown
- ticker-level breakdown
- strategy-family aggregate
- out-of-sample or walk-forward plan before promotion

Do not promote a strategy because one ticker looks good once. Promotion requires
one of:

- broad strategy-family edge across liquid names, or
- strong ticker-specific evidence plus catalyst/liquidity reason to keep it in a
  curated watchlist.

Suggested promotion thresholds for paper mode:

- Minimum 8 ticker-strategy trades in recent intraday sample
- Positive total return
- Profit factor above 1.15
- Max drawdown below 5% for safe profile
- Max drawdown below 8% for risky profile
- Strategy must still pass live data quality gates

## Execution Doctrine

Autonomous paper orders must satisfy:

- market is open
- symbol is valid and liquid
- latest trade is fresh
- quote spread is below max threshold
- recent volume is sufficient
- no duplicate open order is working
- buying power is sufficient
- order notional is below cap
- position notional is below cap
- bracket exit can be built for buy orders
- strategy label is recorded
- artifact is written
- WhatsApp notification is attempted for submitted trades

Never:

- average down autonomously
- turn a failed breakout into a long-term hold
- trade on stale data
- trade low-liquidity names because a score is high
- ignore broad market alignment
- use news headlines without checking date freshness
- submit live-cash orders from this workflow

## Safe Profile

Purpose: minimize losses while still learning.

Allowed strategy families:

- `opening_range_breakout_15m`
- `relative_strength_continuation`

Default behavior:

- smaller order cap
- fewer positions
- higher confidence gate
- tighter stop
- lower take-profit multiple
- blocks high volatility, weak backtests, stale trades, and wide spreads

Preferred universe:

- AMD
- NVDA
- QQQ/SPY for market confirmation

## Risky Profile

Purpose: maximize paper upside while still respecting hard risk gates.

Allowed strategy families:

- `opening_range_breakout_15m`
- `momentum_breakout`
- `relative_strength_continuation`

Default behavior:

- larger order cap
- more positions
- lower confidence gate
- wider stop
- larger take-profit multiple
- still blocks stale trades and wide spreads

Preferred universe:

- AMD
- NVDA
- COIN
- INTC
- PLTR/MU only when live confirmation is strong

## Team Operating Instructions

### Research Department

The Strategy Researcher must output named setups, not generic bullish/bearish
language. Every proposed setup needs:

- regime
- trigger
- confirmation
- invalidation
- sizing thought
- known failure mode
- paper-test note

### Research Manager

The Research Manager should not pass a trade plan to the Trader unless the plan
contains a strategy label and evidence that the current regime matches the
strategy.

### Trader

The Trader must turn research into a concrete transaction proposal only when:

- the setup is named
- entry trigger is clear
- stop is clear
- size is clear
- there is a reason to act now rather than wait

### Chief Investment Officer

The CIO should block "interesting idea" trades that lack execution readiness.
The committee stance should say whether the trade is deployable, watch-only, or
research-only.

### Trading Desk

The Trading Desk should focus on:

- entry method
- order type
- liquidity/slippage
- time-of-day constraints
- stand-down conditions
- stop/take-profit handling

### Risk Office

The Risk Office should challenge:

- missing stops
- unbounded downside
- weak data freshness
- event/catalyst uncertainty
- crowded/extended trades
- position concentration
- strategy family not yet promoted

### Portfolio Office

The Portfolio Office should scale exposure by:

- strategy evidence
- current drawdown
- number of correlated open positions
- market regime
- safe/risky profile

### Operations And Compliance

Operations/Compliance should verify:

- paper-only mode
- correct ticker
- market-open gate
- data source freshness
- Alpaca feed limitations
- audit artifacts
- WhatsApp notification status
- human review requirement before live capital

## Current Code Upgrades Made From This Research

- Added a shared strategy doctrine prompt helper in
  `tradingagents/agents/utils/agent_utils.py`.
- Injected the doctrine into Strategy Researcher, Research Manager, Trader,
  CIO, Trading Desk, Risk Office, risk debaters, Portfolio Manager, Portfolio
  Office, and Operations/Compliance.
- Promoted `opening_range_breakout_15m` into autonomous paper strategy profiles.
- Kept VWAP reclaim/range reversion/fading/scalping out of autonomous execution.
- Preserved Alpaca paper-only workflow and bracket-order risk controls.

## Roadmap

Near term:

1. Add a daily post-trade review that compares realized paper P/L to strategy
   label, profile, and market regime.
2. Add walk-forward validation to the backtest notebook/script.
3. Add market-index alignment features to the live scanner.
4. Persist a strategy scorecard that promotes/demotes strategies automatically.

Medium term:

1. Move from polling to Alpaca websocket state for latest trade/quote/bar data.
2. Add a depth provider for true order-book imbalance and heatmap evidence.
3. Add halt/LULD/status gating from Alpaca streams where subscription permits.
4. Add volatility-adjusted sizing based on realized intraday ATR.

Do not do yet:

- live-cash execution
- autonomous shorting
- autonomous options
- low-float pump/momentum trading
- leverage/margin optimization
- reinforcement learning execution without strict offline validation

