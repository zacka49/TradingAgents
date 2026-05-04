# TradingAgents Expansion Plan (Execution-Oriented)

This plan is designed to evolve TradingAgents from a multi-agent research prototype into an extensible "AI trading firm" platform with measurable paper-trading performance.

## Phase 1: Reliable Run Artifacts (Now Implemented)

Objective: Every run should be reproducible and auditable.

Implemented:
- Per-run artifact bundles are now saved automatically by `TradingAgentsGraph`.
- Artifacts are stored under:
  - `results_dir/<ticker>/<trade_date>/run_<UTC timestamp>/`
- Saved files:
  - `final_state.json`
  - `final_decision.md`
  - `signal.txt`
  - `metadata.json`
  - `reports/*.md` (market, sentiment, news, fundamentals, investment plan, trader plan, final decision)

Value:
- Faster debugging of agent behavior drift
- Easier strategy retrospective analysis
- Better foundation for benchmarking new departments/agents

## Phase 2: Research Department Expansion (Now Implemented)

Objective: Add specialized teams that contribute targeted alpha signals.

Implemented sub-teams:
1. Current News Scout:
   - Company, sector, macro, regulatory, and earnings-adjacent catalysts
2. Strategy Researcher:
   - Testable strategy candidates with triggers, confirmations, invalidation, and paper-test notes
3. Copy Trading Researcher:
   - Politician trades, SEC disclosure filings, insider transactions, and large-holder snapshots
4. Research Director:
   - CEO-ready synthesis that feeds the bull/bear debate, trader, risk desk, and portfolio manager

Next evaluation steps:
1. Track decision impact via artifact-level A/B cohorts.
2. Add richer politician data providers if a stable free API is selected.
3. Add strategy backtest scoring so Strategy Researcher ideas can be promoted or retired quantitatively.

## Phase 3: Portfolio Construction + Risk Controls

Objective: Move from single-ticker recommendations to portfolio-aware actions.

Deliverables:
1. Position sizing policy:
   - Max position %, sector caps, gross/net exposure caps
2. Risk controls:
   - Volatility targeting, drawdown guard, liquidity threshold
3. Execution guardrails:
   - Block orders when confidence is low or data freshness checks fail

## Phase 4: Paper Trading Integration

Objective: Route approved decisions to a paper brokerage account.

Current groundwork:
- Added execution interface in:
  - `tradingagents/execution/paper_broker.py`

Next implementation steps:
1. Add `AlpacaPaperBroker` (or chosen broker) adapter implementing `PaperBroker`.
2. Parse portfolio decisions into `OrderIntent`.
3. Add pre-trade validation:
   - ticker tradability
   - buying power
   - market session/open checks
4. Submit order + persist broker response into run artifacts.
5. Add daily reconciliation job:
   - broker fills
   - PnL snapshots
   - realized vs unrealized performance

## Phase 5: Evaluation Framework

Objective: Continuously measure whether new agents improve outcomes.

Metrics:
1. Decision quality:
   - hit rate, risk-adjusted return, alpha vs SPY
2. Stability:
   - variance across reruns and model/provider choices
3. Operational health:
   - API error rate, retry rate, run duration, missing-data rate

Protocol:
1. Freeze baseline config for 2-4 weeks.
2. Run candidate variant in parallel.
3. Compare via artifact bundles + paper trading PnL.
4. Promote only when statistically and operationally better.

## Suggested Build Order

1. Macro research team
2. Order intent parser from portfolio decision
3. Single broker paper adapter
4. Position sizing/risk policy layer
5. A/B evaluation runner
