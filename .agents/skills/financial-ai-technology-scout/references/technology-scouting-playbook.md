# Technology Scouting Playbook

Use this playbook to convert outside financial AI systems into useful,
low-risk improvements for the TradingAgents paper business.

## Current Source Anchors

- TradingAgents original project: https://github.com/TauricResearch/TradingAgents
- TradingAgents project page: https://tauricresearch.github.io/TradingAgents-AI.github.io/
- FinRobot: https://github.com/AI4Finance-Foundation/FinRobot
- FinGPT: https://github.com/AI4Finance-Foundation/FinGPT
- AI4Finance ecosystem: https://ai4finance.org/
- QuantConnect LEAN: https://www.lean.io/
- LEAN docs: https://www.quantconnect.com/docs/v2/lean-engine/getting-started
- Backtrader: https://github.com/mementum/backtrader
- OpenBB docs: https://docs.openbb.co/
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph durable execution: https://docs.langchain.com/oss/python/langgraph/durable-execution
- OpenAI Agents SDK: https://platform.openai.com/docs/guides/agents-sdk/
- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses
- GitHub repository search API: https://docs.github.com/en/rest/search/search

## Patterns To Reuse

### TradingAgents

Use specialist roles, debate, risk teams, memory, and structured artifacts. Avoid
blind full-graph runs for every paper rebalance because local LLM capacity is
limited.

### FinRobot / FinGPT

Use a layered finance AI stack: data source, data engineering, financial NLP,
agent reasoning, execution/risk. Prefer optional sentiment/catalyst adapters
before training or fine-tuning local finance models.

### LEAN

Adopt a modular architecture: universe selection, alpha generation, portfolio
construction, execution, risk management, and result processing. This maps
directly to `technology_scout.py` and the Codex CEO runner.

### Backtrader

Use it for lightweight local strategy testing because it is already in the
project dependencies. The Codex CEO Backtest Lab now reuses daily candidate bars
for a small momentum smoke test before target weights are selected.

### OpenBB

Prototype as an optional data adapter if the business needs broader financial
data. Do not make it a required dependency until the local workflow proves it
adds signal.

### LangGraph

Use checkpointing/durable execution when long-running agent graphs need resume,
replay, or human-in-the-loop review. Keep compute-light portfolio runs outside
the heavy graph.

### OpenAI Agents / Responses

Use the concepts of handoffs, tools, tracing, and file search as architecture
patterns. In this repo, implement local equivalents first: artifacts,
technology reports, decision logs, and optional OpenAI-powered research later.

### GitHub Researcher

Use popular repositories as architecture radar, not trading signals. Extract
patterns for validation, observability, dry-run discipline, data adapters, and
agent roles. Never copy code without license review, tests, and a business
reason.

## Adoption Queue

1. Adopt now: technology scout report, capability registry, artifact traces.
2. Adopt now: Backtest Lab evidence in the Codex CEO briefing pack.
3. Adopt now: GitHub Researcher memo in full research department runs.
4. Prototype next: OpenBB optional data source.
5. Prototype next: local RAG/knowledge index over `knowledge/` and `.agents/skills/`.
6. Watch: FinGPT local finance models; useful but likely too heavy for weak GPU/CPU.
7. Watch: LEAN integration; powerful but heavy compared with current paper needs.
