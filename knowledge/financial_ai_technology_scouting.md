# Financial AI Technology Scouting

Updated: 2026-05-04

This file records external systems and architecture patterns that can improve
the TradingAgents paper-trading business.

## Findings

### TradingAgents

The upstream project validates the trading-firm metaphor: specialist analysts,
bull/bear debate, trader, risk team, and portfolio manager. It is a strong
research architecture, but full LLM runs can be expensive or quota-heavy. The
business should keep the full graph for deep research and use the Codex CEO
company runner for daily paper operations.

Sources:

- https://github.com/TauricResearch/TradingAgents
- https://tauricresearch.github.io/TradingAgents-AI.github.io/

### FinRobot and FinGPT

AI4Finance projects show a useful full-stack pattern: data curation, financial
NLP/sentiment, agents, quantitative analytics, and risk. The immediate lesson
is not to fine-tune models on this machine; it is to add optional adapters and
knowledge layers that can later use finance-specific models.

Sources:

- https://github.com/AI4Finance-Foundation/FinRobot
- https://github.com/AI4Finance-Foundation/FinGPT
- https://ai4finance.org/

### QuantConnect LEAN

LEAN’s architecture is the cleanest template for scaling the business:
universe selection, alpha creation, portfolio construction, execution, risk
management, and result processing. The Codex CEO runner now mirrors that
structure lightly through candidate screening, strategy classification, target
weights, paper execution, and artifacts.

Sources:

- https://www.lean.io/
- https://www.quantconnect.com/docs/v2/lean-engine/getting-started

### Backtrader

Backtrader is already in dependencies and supports multiple feeds, indicators,
broker simulation, sizers, analyzers, stop/limit/bracket-style concepts, and
schedulers. It is the best near-term backtesting path because it avoids adding
heavy new infrastructure. The Codex CEO workflow now uses it as a lightweight
Backtest Lab over already-loaded daily bars before target weights are selected.

Source:

- https://github.com/mementum/backtrader

### OpenBB

OpenBB can unify financial data access through Python, CLI, REST, Jupyter, and
other surfaces. It is a promising optional data adapter for future research,
but should remain optional until it proves useful for the daily paper workflow.

Source:

- https://docs.openbb.co/

### LangGraph

LangGraph persistence and durable execution support checkpoints, memory,
time-travel debugging, human-in-the-loop workflows, and fault tolerance. This
repo already has checkpoint support for the heavy graph; daily paper runs
should add lightweight artifacts instead of forcing every run through the
heavy graph.

Sources:

- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/durable-execution

### OpenAI Agents / Responses

OpenAI’s current agent architecture emphasizes tools, handoffs, tracing, file
search, web search, remote MCP, and structured stateful responses. The local
business should mirror these ideas with repo artifacts and skill/knowledge
files now, then optionally add OpenAI API-powered deep research later.

Sources:

- https://platform.openai.com/docs/guides/agents-sdk/
- https://platform.openai.com/docs/api-reference/responses
- https://openai.github.io/openai-agents-python/tracing/
- https://platform.openai.com/docs/guides/tools-file-search/

## Implemented From This Pass

- Repo-local skill: `.agents/skills/financial-ai-technology-scout/`
- Knowledge file: `knowledge/financial_ai_technology_scouting.md`
- Technology scout module: `tradingagents/company/technology_scout.py`
- Backtest Lab module: `tradingagents/company/backtest_lab.py`
- Codex CEO briefing now includes a technology scout report when enabled.
- Codex CEO briefing now includes candidate backtest evidence when enabled.

## Next Prototype Queue

1. Add an optional OpenBB adapter behind a feature flag.
2. Build a local knowledge index over `knowledge/` and `.agents/skills/`.
3. Add post-trade result processing that compares strategy labels against
   realized paper P/L.
4. Consider LEAN only when the strategy library outgrows the lightweight runner.
