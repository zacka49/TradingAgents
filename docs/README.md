# TradingAgents Business Documentation

This repo now has two related surfaces:

- The original TradingAgents multi-agent research graph for single-ticker
  analysis.
- A paper-only AI trading business that uses Codex CEO Company mode, specialist
  desks, quant strategy research, portfolio/risk governance, and guarded Alpaca
  paper execution.

## Operating Map

```text
Opportunity and desk research
-> Strategy Research Department
-> Data Quality And Strategy Governance
-> Portfolio/Risk Office
-> Alpaca paper execution controller
-> Evaluation and Training/Development
```

Only the execution controller can submit paper orders. Research desks can
discover and recommend, but autonomous trading needs both a promoted strategy
and portfolio/risk approval.

## Start Here

- [multi_desk_business_model.md](multi_desk_business_model.md) - organagram,
  desks, capital caps, and execution readiness.
- [strategy_research_department.md](strategy_research_department.md) - quant
  strategy generation, evidence scoring, and promotion stages.
- [codex_ceo_company.md](codex_ceo_company.md) - daily CEO operating runner,
  briefing artifacts, and Alpaca paper planning.
- [autonomous_day_trader.md](autonomous_day_trader.md) - market-hours paper
  trading loop, close discipline, monitoring, and stop controls.
- [research_department.md](research_department.md) - AI research roles and
  provider/data guidance.
- [news_reversion_desk.md](news_reversion_desk.md) - news event-study workflow.
- [agent_skill_training_matrix.md](agent_skill_training_matrix.md) - every AI
  agent, assigned skills, drills, and success criteria.
- [local_first_compute_policy.md](local_first_compute_policy.md) - local-first
  model guardrails to avoid unwanted hosted LLM usage.
- [setup_local_ollama_and_paper.md](setup_local_ollama_and_paper.md) - local
  LLM and Alpaca paper setup.
- [expansion_plan.md](expansion_plan.md) - current roadmap after the
  autonomous paper business implementation.

## Current Strategy Library

Generated artifacts live in `knowledge/strategy_library/`.

Current autonomous paper-trading status:

- `opening_range_breakout_15m`: approved paper strategy.
- `momentum_breakout`: approved paper strategy.
- `relative_strength_continuation`: paper trade candidate.
- `news_reversion_event_study`: research-only.
- `crypto_momentum`: research-only until crypto execution and 24/7 risk policy
  exist.
- `vwap_reclaim` and `range_reversion_to_vwap`: blocked or retired until
  evidence improves.

Refresh the library:

```powershell
.\.venv\Scripts\python.exe scripts\run_strategy_research_department.py `
  --evidence-root results `
  --output-dir knowledge/strategy_library
```

## Paper-Only Rule

This business is intentionally paper-only. Live trading is not enabled by
default and should be treated as a separate project with a dedicated risk,
broker, compliance, and approval process.
