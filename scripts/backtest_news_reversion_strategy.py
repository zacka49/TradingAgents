from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

from tradingagents.company.news_reversion_desk import (
    POPULAR_NEWS_REVERSION_UNIVERSE,
    run_news_reversion_event_study,
    write_news_reversion_artifacts,
)


def _parse_universe(raw: str) -> list[str]:
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest the News Reversion Desk with recent dated headlines and daily closes."
    )
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    parser.add_argument("--universe", default="")
    parser.add_argument("--lookback-days", type=int, default=21)
    parser.add_argument("--max-events-per-symbol", type=int, default=3)
    parser.add_argument("--min-event-move-pct", type=float, default=1.0)
    parser.add_argument("--min-reversion-capture-pct", type=float, default=35.0)
    parser.add_argument("--results-dir", default="results/news_reversion_desk")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env")
    args = build_parser().parse_args(argv)
    universe = _parse_universe(args.universe) if args.universe else POPULAR_NEWS_REVERSION_UNIVERSE
    report = run_news_reversion_event_study(
        universe=universe,
        lookback_days=args.lookback_days,
        max_events_per_symbol=args.max_events_per_symbol,
        min_event_move_pct=args.min_event_move_pct,
        min_reversion_capture_pct=args.min_reversion_capture_pct,
    )
    output_dir = Path(args.results_dir) / args.date
    paths = write_news_reversion_artifacts(report, output_dir=output_dir)
    summary = {
        "verdict": report.verdict,
        "verdict_note": report.verdict_note,
        "events": report.event_count,
        "eligible_events": report.eligible_event_count,
        "reverted_events": report.reverted_event_count,
        "win_rate_pct": report.win_rate_pct,
        "avg_fade_return_pct": report.avg_fade_return_pct,
        "avg_reversion_capture_pct": report.avg_reversion_capture_pct,
        "artifact_paths": paths,
        "top_symbols": [asdict(row) for row in report.symbol_summaries[:5]],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
