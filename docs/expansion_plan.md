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
1. Stock Discovery Researcher:
   - Pre-market 10-stock watchlist for the rest of the business to consider
2. Current News Scout:
   - Company, sector, macro, regulatory, and earnings-adjacent catalysts
3. Strategy Researcher:
   - Testable strategy candidates with triggers, confirmations, invalidation, and paper-test notes
4. Copy Trading Researcher:
   - Politician trades, SEC disclosure filings, insider transactions, and large-holder snapshots
5. GitHub Researcher:
   - Popular open-source financial AI, trading, data, agent, and backtesting repo lessons
6. Research Director:
   - CEO-ready synthesis that feeds the bull/bear debate, trader, risk desk, and portfolio manager

Current evaluation steps:
1. Track decision impact via artifact-level A/B cohorts.
2. Add richer politician data providers if a stable free API is selected.
3. Use GitHub Researcher findings to prioritize optional OpenBB, vectorized backtest, and monitoring prototypes.
4. Keep strategy backtest scoring current through the Strategy Research Department and generated strategy library.

## Phase 6: Business Department Expansion (Now Implemented)

Objective: Expand the rest of the company into specialist AI departments with clear hand-offs, like the research department.

Implemented departments:
1. Investment Committee:
   - Chief Investment Officer reviews research before the Trader acts
2. Trading Desk:
   - Trading Desk Strategist translates trader intent into execution guidance
3. Risk Office:
   - Risk Office Guardian frames stress scenarios and guardrails before risk debate
4. Portfolio Office:
   - Portfolio Office Allocator turns the final decision into allocation guidance
5. Operations and Compliance:
   - Operations Compliance Auditor checks data freshness, disclosure lag, and readiness
6. Evaluation Department:
   - Evaluation Analyst defines benchmarks, metrics, A/B tests, and learning notes

Next hardening steps:
1. Split each department into multiple debating specialists once baseline costs are understood.
2. Add deterministic policy checks beside each AI memo so hard limits cannot be waived by language.
3. Store department-level scores in run artifacts for A/B evaluation across model/provider choices.

## Phase 3: Portfolio Construction + Risk Controls (Now Implemented For Paper Mode)

Objective: Move from single-ticker recommendations to portfolio-aware actions.

Implemented:
1. Position sizing and deploy caps in Codex CEO Company mode and autonomous day-trader profiles.
2. Centralized multi-desk allocation governance in `tradingagents/company/business_governance.py`.
3. Strategy promotion gates in `tradingagents/company/strategy_research_department.py`.
4. Execution guardrails for market-open state, order notional, buying power, duplicate open orders, spread, stale data, confidence, and session loss.
5. Day-trading close discipline, bracket exits, stale-loser exits, profit protection, and cooldowns.

## Phase 4: Paper Trading Integration (Now Implemented For Alpaca Paper)

Objective: Route approved decisions to a paper brokerage account.

Implemented:
1. `PaperBroker` interface and `AlpacaPaperBroker` adapter.
2. `OrderIntent` planning and policy checks.
3. Codex CEO dry-run and guarded paper submission paths.
4. Autonomous paper day-trader loop with safe/risky profiles.
5. Broker responses, order diagnostics, session logs, and briefing artifacts.

Remaining hardening:
1. Add deeper P&L attribution by desk, strategy ID, ticker, risk flag, and blocker reason.
2. Add a dedicated crypto adapter before crypto strategies can leave research-only status.
3. Add a dedicated forex broker/data adapter before direct FX execution can be considered.
4. Add walk-forward/out-of-sample strategy promotion jobs before increasing paper allocation.

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

1. P&L attribution by desk and strategy.
2. Walk-forward strategy research jobs.
3. Crypto paper adapter and 24/7 risk policy.
4. Control room monitoring hardening.
5. A/B evaluation runner across promoted strategies.
