# Strategy Research Department

The Strategy Research Department is the quant research function of the
business. It does not trade. Its job is to generate, test, score, promote,
demote, and retire strategy ideas.

## Operating Split

```text
Strategy Research Department
├── Strategy Idea Generator
├── Market Regime Researcher
├── Backtest Lab
├── Event Study Lab
├── Experiment / Backtest Auditor
├── Strategy Promotion Committee
└── Strategy Library Maintainer

Trading Department
├── Trading Desk Strategist
├── Portfolio Office Allocator
├── Risk Office Guardian
└── Alpaca Paper Execution Controller
```

Quant research finds and proves edges. Trading can only act on strategy IDs
that Quant Research has promoted to `paper_trade_candidate` or
`approved_paper_strategy`.

## Strategy Promotion States

- `research_idea`: hypothesis only.
- `paper_watchlist`: interesting but not tradeable.
- `paper_trade_candidate`: tradeable in paper mode after live confirmation.
- `approved_paper_strategy`: preferred paper strategy with stronger evidence.
- `retired`: blocked from autonomous trading.
- `live_candidate`: out of scope unless explicitly approved as a separate live-broker project.

## Run Quant Research

```powershell
.\.venv\Scripts\python.exe scripts\run_strategy_research_department.py `
  --evidence-root results `
  --output-dir knowledge/strategy_library
```

Artifacts:

- `strategy_research_report.json`
- `strategy_research_report.md`
- `approved_paper_strategies.json`
- `research_ideas.json`
- `retired_strategies.json`

## Current Default Decisions

- `opening_range_breakout_15m`: approved paper strategy.
- `momentum_breakout`: approved paper strategy.
- `relative_strength_continuation`: paper trade candidate.
- `vwap_reclaim`: research idea until evidence improves.
- `range_reversion_to_vwap`: retired from autonomous execution.
- `news_reversion_event_study`: research idea.
- `crypto_momentum`: research idea until crypto adapter/risk controls exist.

The Codex CEO runner reads `knowledge/strategy_library/strategy_research_report.json`
when it exists. If no library exists, it uses conservative built-in defaults.
