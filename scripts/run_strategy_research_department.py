from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tradingagents.company.strategy_research_department import (
    build_strategy_research_report,
    write_strategy_library,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the quant-style Strategy Research Department and update the strategy library."
    )
    parser.add_argument(
        "--evidence-root",
        default="results",
        help="Root directory to scan for backtest and event-study artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default="knowledge/strategy_library",
        help="Directory where the strategy library artifacts are written.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_strategy_research_report(evidence_root=args.evidence_root)
    paths = write_strategy_library(report, output_dir=Path(args.output_dir))
    print(
        json.dumps(
            {
                "approved_strategy_ids": report.approved_strategy_ids,
                "paper_candidate_strategy_ids": report.paper_candidate_strategy_ids,
                "blocked_strategy_ids": report.blocked_strategy_ids,
                "paths": paths,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
