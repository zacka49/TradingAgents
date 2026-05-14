#!/usr/bin/env python3
"""Validate durable TradingAgents research assets and day-summary reports.

This is intentionally lightweight and stdlib-only. It mirrors the Claude
financial-services repo's habit of checking markdown/YAML-style operating
assets before they drift from the code.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    ".agents/skills/day-trading-research/SKILL.md",
    ".agents/skills/day-trading-research/references/day-trading-playbook.md",
    "docs/autonomous_day_trader.md",
    "docs/day_trader_managed_agent_cookbook.md",
    "knowledge/day_trader_ai_research_program_2026.md",
    "knowledge/day_trading_stock_selection_and_premarket_research_2026.md",
    "knowledge/famous_day_trader_playbook_backtests_2026.md",
    "knowledge/claude_financial_services_repo_analysis_2026.md",
]

REQUIRED_TEXT = {
    ".agents/skills/day-trading-research/SKILL.md": [
        "untrusted",
        "structured",
        "one-controller",
    ],
    ".agents/skills/day-trading-research/references/day-trading-playbook.md": [
        "Catalyst",
        "Thesis",
        "same-cycle",
    ],
    "docs/day_trader_managed_agent_cookbook.md": [
        "Security Tiers",
        "Structured Handoff Schemas",
        "Execution Controller",
    ],
    "knowledge/claude_financial_services_repo_analysis_2026.md": [
        "SWOT Analysis",
        "Things They Do That We Do Not",
        "Lessons Applied To TradingAgents",
    ],
    "knowledge/day_trading_stock_selection_and_premarket_research_2026.md": [
        "Pre-Open Way Of Working",
        "Liquidity",
        "ranked_research_queue",
    ],
}


def main() -> int:
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing required research asset: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"empty research asset: {rel}")
        for needle in REQUIRED_TEXT.get(rel, []):
            if needle not in text:
                errors.append(f"{rel}: missing required text {needle!r}")

    skill_path = ROOT / ".agents/skills/day-trading-research/SKILL.md"
    if skill_path.is_file():
        skill_text = skill_path.read_text(encoding="utf-8")
        if not skill_text.startswith("---"):
            errors.append("day-trading-research skill missing frontmatter")
        for key in ("name:", "description:"):
            if key not in skill_text.split("---", 2)[1]:
                errors.append(f"day-trading-research skill missing {key}")

    summaries_dir = ROOT / "results/autonomous_day_trader/day_summaries"
    if summaries_dir.exists():
        pattern = re.compile(r"^day(?P<day>\d+)_(?P<date>\d{4}-\d{2}-\d{2})\.md$")
        for summary in sorted(summaries_dir.glob("*.md")):
            match = pattern.match(summary.name)
            if not match:
                errors.append(f"day summary has unexpected filename: {summary}")
                continue
            day = match.group("day")
            date = match.group("date")
            first_line = summary.read_text(encoding="utf-8").splitlines()[0].strip()
            expected = f"# Day {day} Summary - {date}"
            if first_line != expected:
                errors.append(
                    f"{summary.name}: first heading {first_line!r} != {expected!r}"
                )

    if errors:
        print(f"FAIL - {len(errors)} issue(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("OK - research assets and day summaries are coherent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
