# C1 Grounding Audit — 2026-07-29

- `strategy_researcher`: no strategy-library rows were injected before C2; it received only static doctrine at `tradingagents/agents/research_department/strategy_researcher.py:28`.
- `market_analyst`: no strategy-library rows were injected before C2; its prompt ended with discovery/training context at `tradingagents/agents/analysts/market_analyst.py:71-83`.
- `specialist_memory_dir`: specialist lessons were written by `tradingagents/company/agent_learning.py:42-79` and read by the Codex CEO staff workflow, not either graph analyst prompt.
- `strategy_library_dir`: library rows were read by `tradingagents/company/codex_ceo_company.py:1337-1364`, not by the graph analyst constructors in `tradingagents/graph/setup.py:71-106`.
- C2 action: reuse the existing agent prompt-utility layer for bounded local JSON injection; add no vector database, embedding model, online call, or order authority.
