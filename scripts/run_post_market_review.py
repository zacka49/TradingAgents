from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

from tradingagents.company import write_post_market_review
from tradingagents.default_config import DEFAULT_CONFIG


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local post-market AI scorecards and specialist memories."
    )
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--memory-dir", default=None)
    parser.add_argument("--no-memory", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env")
    args = build_parser().parse_args(argv)

    config = DEFAULT_CONFIG.copy()
    if args.results_dir:
        config["results_dir"] = str(Path(args.results_dir))
    if args.memory_dir:
        config["specialist_memory_dir"] = str(Path(args.memory_dir))

    summary = write_post_market_review(
        results_dir=config["results_dir"],
        trade_date=args.date,
        output_dir=args.output_dir,
        memory_dir=config.get("specialist_memory_dir"),
        update_memory=not args.no_memory,
        max_memory_entries=int(config.get("specialist_memory_max_entries", 30)),
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
