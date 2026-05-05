from __future__ import annotations

from datetime import datetime, UTC
import os
from typing import Annotated, Any

import requests
from langchain_core.tools import tool


GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

CURATED_FINANCIAL_AI_REPOS = [
    {
        "full_name": "TauricResearch/TradingAgents",
        "html_url": "https://github.com/TauricResearch/TradingAgents",
        "description": "Multi-agent LLM financial trading framework.",
        "stars": None,
        "language": "Python",
        "license": "Apache-2.0",
        "topics": ["trading", "agents", "llm", "finance"],
        "lesson": "Keep specialist roles, debate, risk review, and durable artifacts.",
    },
    {
        "full_name": "AI4Finance-Foundation/FinRobot",
        "html_url": "https://github.com/AI4Finance-Foundation/FinRobot",
        "description": "Open-source financial AI agent platform.",
        "stars": None,
        "language": "Python",
        "license": "Apache-2.0",
        "topics": ["finance", "ai-agent", "llm", "research"],
        "lesson": "Borrow layered agent workflows and equity report structure.",
    },
    {
        "full_name": "AI4Finance-Foundation/FinGPT",
        "html_url": "https://github.com/AI4Finance-Foundation/FinGPT",
        "description": "Open-source financial LLM framework.",
        "stars": None,
        "language": "Python",
        "license": "MIT",
        "topics": ["finance", "llm", "sentiment-analysis"],
        "lesson": "Use finance-specific NLP ideas before attempting local fine-tuning.",
    },
    {
        "full_name": "AI4Finance-Foundation/FinRL",
        "html_url": "https://github.com/AI4Finance-Foundation/FinRL",
        "description": "Financial reinforcement learning framework.",
        "stars": None,
        "language": "Python",
        "license": "MIT",
        "topics": ["reinforcement-learning", "finance", "portfolio"],
        "lesson": "Watch for portfolio/rebalance evaluation ideas; keep RL out of live paper flow for now.",
    },
    {
        "full_name": "OpenBB-finance/OpenBB",
        "html_url": "https://github.com/OpenBB-finance/OpenBB",
        "description": "Open financial data and research platform.",
        "stars": None,
        "language": "Python",
        "license": "AGPL-3.0",
        "topics": ["finance", "data", "research"],
        "lesson": "Prototype optional data adapters; avoid hard dependency until signal improves.",
    },
    {
        "full_name": "QuantConnect/Lean",
        "html_url": "https://github.com/QuantConnect/Lean",
        "description": "Open-source algorithmic trading engine.",
        "stars": None,
        "language": "C#",
        "license": "Apache-2.0",
        "topics": ["algorithmic-trading", "backtesting", "live-trading"],
        "lesson": "Mirror universe, alpha, portfolio, execution, risk, and result-processing boundaries.",
    },
    {
        "full_name": "mementum/backtrader",
        "html_url": "https://github.com/mementum/backtrader",
        "description": "Python backtesting library for trading strategies.",
        "stars": None,
        "language": "Python",
        "license": "GPL-3.0",
        "topics": ["backtesting", "trading", "indicators"],
        "lesson": "Keep using it for lightweight local candidate validation.",
    },
    {
        "full_name": "polakowo/vectorbt",
        "html_url": "https://github.com/polakowo/vectorbt",
        "description": "Vectorized backtesting and quant research.",
        "stars": None,
        "language": "Python",
        "license": "Apache-2.0",
        "topics": ["backtesting", "quant", "vectorized"],
        "lesson": "Consider for fast batch strategy research if Backtest Lab becomes too slow.",
    },
    {
        "full_name": "kernc/backtesting.py",
        "html_url": "https://github.com/kernc/backtesting.py",
        "description": "Small Python framework for backtesting trading strategies.",
        "stars": None,
        "language": "Python",
        "license": "AGPL-3.0",
        "topics": ["backtesting", "trading-strategies"],
        "lesson": "Study simple strategy APIs and plotting; check license before reuse.",
    },
    {
        "full_name": "freqtrade/freqtrade",
        "html_url": "https://github.com/freqtrade/freqtrade",
        "description": "Free open-source crypto trading bot with dry-run, backtesting, and optimization.",
        "stars": None,
        "language": "Python",
        "license": "GPL-3.0",
        "topics": ["trading-bot", "backtesting", "optimization"],
        "lesson": "Borrow dry-run discipline, lookahead checks, and operational status reporting concepts.",
    },
]


@tool
def get_popular_financial_ai_repos(
    query: Annotated[
        str,
        "GitHub search query. Leave blank to use financial AI, agent, and backtesting defaults.",
    ] = "",
    limit: Annotated[int, "Maximum repositories to return"] = 12,
) -> str:
    """Return popular open-source repos relevant to financial AI and trading.

    The tool uses GitHub public search when reachable and falls back to a
    curated list of known finance/trading AI repositories. It is a scouting
    aid, not a license approval or dependency recommendation.
    """
    limit = max(3, min(int(limit), 20))
    queries = [query.strip()] if query.strip() else _default_queries()
    repos = _curated_rows()
    source_notes = ["curated seed list loaded"]

    for search_query in queries:
        try:
            payload = _github_search(search_query, per_page=limit)
            items = payload.get("items", [])
            source_notes.append(f"GitHub search `{search_query}` returned {len(items)} rows")
            repos.extend(_normalise_github_item(item) for item in items)
        except Exception as exc:
            source_notes.append(f"GitHub search `{search_query}` unavailable: {exc}")

    ranked = _dedupe_and_rank(repos)[:limit]
    lines = [
        f"# GitHub financial AI repository scout ({datetime.now(UTC).date()})",
        "Source status: " + "; ".join(source_notes),
        "| Rank | Repository | Stars | Language | License | Topics | Reusable lesson |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for rank, repo in enumerate(ranked, start=1):
        lines.append(
            "| {rank} | [{full_name}]({html_url}) | {stars} | {language} | "
            "{license} | {topics} | {lesson} |".format(
                rank=rank,
                **{key: _table_cell(value) for key, value in repo.items()},
            )
        )
    return "\n".join(lines)


def _default_queries() -> list[str]:
    return [
        "topic:algorithmic-trading stars:>1000",
        "topic:backtesting stars:>1000",
        '"financial ai" agent trading',
    ]


def _github_search(query: str, per_page: int) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "TradingAgents-GitHub-Researcher",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(
        GITHUB_SEARCH_URL,
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
        },
        headers=headers,
        timeout=12,
    )
    response.raise_for_status()
    return response.json()


def _curated_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in CURATED_FINANCIAL_AI_REPOS]


def _normalise_github_item(item: dict[str, Any]) -> dict[str, Any]:
    license_payload = item.get("license") or {}
    return {
        "full_name": item.get("full_name", ""),
        "html_url": item.get("html_url", ""),
        "description": item.get("description") or "",
        "stars": item.get("stargazers_count"),
        "language": item.get("language") or "",
        "license": license_payload.get("spdx_id") or "unknown",
        "topics": item.get("topics") or [],
        "lesson": _lesson_for_repo(item),
    }


def _lesson_for_repo(item: dict[str, Any]) -> str:
    topics = {str(topic).lower() for topic in item.get("topics") or []}
    description = str(item.get("description") or "").lower()
    if "backtesting" in topics or "backtest" in description:
        return "Review validation, slippage, fee, and no-lookahead checks."
    if "trading-bot" in topics or "bot" in description:
        return "Review dry-run, monitoring, configuration, and failure-handling patterns."
    if "agent" in description or "ai-agent" in topics:
        return "Review agent roles, tool boundaries, memory, and reporting artifacts."
    if "finance" in topics or "financial" in description:
        return "Review data adapters and financial report structure."
    return "Review architecture only; adopt nothing without tests and license review."


def _dedupe_and_rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        full_name = str(row.get("full_name", "")).strip()
        if not full_name:
            continue
        existing = seen.get(full_name)
        if existing is None or _stars(row) > _stars(existing):
            seen[full_name] = row
    return sorted(
        seen.values(),
        key=lambda row: (_stars(row), str(row.get("full_name", ""))),
        reverse=True,
    )


def _stars(row: dict[str, Any]) -> int:
    try:
        return int(row.get("stars") or 0)
    except (TypeError, ValueError):
        return 0


def _table_cell(value: Any) -> str:
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value[:6])
    if value is None:
        return ""
    return str(value).replace("|", "/").replace("\n", " ").strip()
