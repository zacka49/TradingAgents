from __future__ import annotations

import argparse
from pathlib import Path
import sys

from tradingagents.company.agent_skill_registry import render_agent_skill_matrix_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render the TradingAgents AI agent skill training matrix."
    )
    parser.add_argument(
        "--output",
        default="docs/agent_skill_training_matrix.md",
        help="Markdown output path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_agent_skill_matrix_markdown(), encoding="utf-8")
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
