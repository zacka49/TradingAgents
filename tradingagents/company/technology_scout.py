from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.util import find_spec
import os
from pathlib import Path
from typing import Iterable, List

import requests


@dataclass(frozen=True)
class TechnologyCapability:
    name: str
    category: str
    adoption: str
    local_status: str
    business_value: str
    next_step: str
    source: str


def _has_module(module_name: str) -> bool:
    return find_spec(module_name) is not None


def _env_present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _ollama_models(base_url: str, timeout: int = 3) -> List[str]:
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        resp.raise_for_status()
        return [str(model.get("name")) for model in resp.json().get("models", [])]
    except Exception:
        return []


def build_technology_capabilities(
    *,
    project_root: str | Path,
    ollama_base_url: str = "http://localhost:11434",
) -> List[TechnologyCapability]:
    root = Path(project_root)
    knowledge_present = (root / "knowledge").exists()
    skill_present = (root / ".agents" / "skills").exists()
    ollama_models = _ollama_models(ollama_base_url)

    capabilities = [
        TechnologyCapability(
            name="TradingAgents upstream architecture",
            category="multi_agent_research",
            adoption="adopted",
            local_status="expanded locally",
            business_value="Specialist analyst, debate, trader, risk, and portfolio roles.",
            next_step="Keep full graph for deep research; use Codex CEO runner for daily paper operations.",
            source="https://github.com/TauricResearch/TradingAgents",
        ),
        TechnologyCapability(
            name="LangGraph persistence",
            category="durability",
            adoption="adopted",
            local_status="checkpoint support present",
            business_value="Checkpointing, resume, time-travel debugging, and fault tolerance for long graph runs.",
            next_step="Enable checkpointing for long deep-research jobs; keep lightweight artifacts for daily runs.",
            source="https://docs.langchain.com/oss/python/langgraph/persistence",
        ),
        TechnologyCapability(
            name="Backtrader",
            category="backtesting",
            adoption="adopt_now",
            local_status="installed" if _has_module("backtrader") else "missing",
            business_value="Local backtesting, indicators, analyzers, broker simulation, and sizers.",
            next_step="Backtest Lab now smoke-tests candidates before target weights are selected.",
            source="https://github.com/mementum/backtrader",
        ),
        TechnologyCapability(
            name="OpenBB Platform",
            category="data_platform",
            adoption="prototype_next",
            local_status="installed" if _has_module("openbb") else "not installed",
            business_value="Unified financial data API for broader research and dashboards.",
            next_step="Prototype as an optional adapter; do not make it required yet.",
            source="https://docs.openbb.co/",
        ),
        TechnologyCapability(
            name="QuantConnect LEAN",
            category="algorithm_engine",
            adoption="watch",
            local_status="external",
            business_value="Professional modular engine for universe, alpha, portfolio, execution, and risk models.",
            next_step="Borrow architecture now; integrate only if lightweight runner becomes limiting.",
            source="https://www.lean.io/",
        ),
        TechnologyCapability(
            name="FinRobot",
            category="financial_agents",
            adoption="prototype_next",
            local_status="external",
            business_value="Financial agent platform pattern combining LLMs, quant analytics, and risk.",
            next_step="Borrow role patterns and financial report templates before adding dependencies.",
            source="https://github.com/AI4Finance-Foundation/FinRobot",
        ),
        TechnologyCapability(
            name="FinGPT",
            category="financial_llm",
            adoption="watch",
            local_status="external",
            business_value="Finance-specific LLM/data pipeline ideas for sentiment and forecasting.",
            next_step="Use as a reference; local fine-tuning is too heavy for current machine.",
            source="https://github.com/AI4Finance-Foundation/FinGPT",
        ),
        TechnologyCapability(
            name="OpenAI Agents/Responses architecture",
            category="agent_platform",
            adoption="prototype_next",
            local_status="api key present" if _env_present("OPENAI_API_KEY") else "no api key",
            business_value="Tools, handoffs, tracing, file search, web search, and stateful agent runs.",
            next_step="Mirror tracing/file-search locally now; optionally add API-powered deep research later.",
            source="https://platform.openai.com/docs/guides/agents-sdk/",
        ),
        TechnologyCapability(
            name="Local Ollama staff models",
            category="local_llm",
            adoption="adopted",
            local_status=", ".join(ollama_models) if ollama_models else "not reachable",
            business_value="Cheap local staff memos without cloud quota pressure.",
            next_step="Keep calls short; reserve Codex for CEO/CIO synthesis and code changes.",
            source="https://ollama.com/",
        ),
        TechnologyCapability(
            name="Repo knowledge and skills",
            category="memory",
            adoption="adopted",
            local_status=(
                "knowledge+skills present"
                if knowledge_present and skill_present
                else "incomplete"
            ),
            business_value="Durable operating knowledge for future Codex runs.",
            next_step="Add a local search/index step over knowledge files before major research changes.",
            source="local repository",
        ),
    ]
    return capabilities


def render_technology_scout_report(capabilities: Iterable[TechnologyCapability]) -> str:
    rows = list(capabilities)
    lines = [
        "# Technology Scout Report",
        "",
        "## Adopt Now",
    ]
    for capability in rows:
        if capability.adoption not in {"adopted", "adopt_now"}:
            continue
        lines.extend(_capability_block(capability))

    lines.extend(["", "## Prototype Next"])
    for capability in rows:
        if capability.adoption != "prototype_next":
            continue
        lines.extend(_capability_block(capability))

    lines.extend(["", "## Watch List"])
    for capability in rows:
        if capability.adoption != "watch":
            continue
        lines.extend(_capability_block(capability))

    lines.extend(
        [
            "",
            "## Capability Matrix",
            "| Capability | Category | Adoption | Local Status |",
            "| --- | --- | --- | --- |",
        ]
    )
    for capability in rows:
        lines.append(
            f"| {capability.name} | {capability.category} | "
            f"{capability.adoption} | {capability.local_status} |"
        )
    return "\n".join(lines)


def capabilities_as_dicts(
    capabilities: Iterable[TechnologyCapability],
) -> List[dict]:
    return [asdict(capability) for capability in capabilities]


def _capability_block(capability: TechnologyCapability) -> List[str]:
    return [
        "",
        f"### {capability.name}",
        f"- Category: {capability.category}",
        f"- Local status: {capability.local_status}",
        f"- Business value: {capability.business_value}",
        f"- Next step: {capability.next_step}",
        f"- Source: {capability.source}",
    ]
