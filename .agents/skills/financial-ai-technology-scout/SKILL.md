---
name: financial-ai-technology-scout
description: Research external financial AI, agent frameworks, trading engines, data platforms, backtesting systems, RAG/memory tools, observability, and open-source repos; use when Codex should improve the TradingAgents business architecture or convert outside projects into practical workflow upgrades.
---

# Financial AI Technology Scout

## Workflow

1. Read `references/technology-scouting-playbook.md`.
2. Use primary sources: official docs, GitHub repos, research papers, and vendor docs.
3. Classify each finding as `adopt_now`, `prototype_next`, `watch`, or `reject_for_now`.
4. Prefer low-compute, low-dependency changes first: registry entries, artifacts, tests, optional adapters, and knowledge files.
5. Keep live/paper execution safety rails separate from research autonomy.
6. Write durable findings to `knowledge/` and implementation hooks into `tradingagents/company/` when useful.

## Adoption Heuristics

- Adopt now: improves safety, observability, reproducibility, or local operations without heavy dependencies.
- Prototype next: needs extra service/API/dependency but has clear value.
- Watch: promising but too heavy, immature, or not needed for the current paper business.
- Reject for now: incompatible license, too risky, too expensive, or duplicates existing behavior.

## Current Local Hooks

- `tradingagents/company/technology_scout.py` writes a technology-scout report into each Codex CEO run.
- `tradingagents/company/backtest_lab.py` uses Backtrader for lightweight candidate evidence.
- `tradingagents/agents/research_department/github_researcher.py` monitors popular GitHub repos for reusable lessons.
- `knowledge/financial_ai_technology_scouting.md` stores the current research synthesis.
- `knowledge/github_repository_research.md` stores the GitHub research seed list and operating rules.
- `docs/codex_ceo_company.md` documents operational commands and safety gates.
