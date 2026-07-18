"""T1 - pre-market prep.

Runs before the trading session. Checks Alpaca/env readiness, Ollama health,
and strategy-library freshness, then writes one status file the trading
session (T2) and the daily digest (T3) both read.

A non-flat account or stale positions are informational here, not a hard
block: T2 always launches with ``--flatten-existing-at-start``, which is the
fix for the deadlock that stalled the business from 2026-06-04 to 2026-07-08
(see docs/incident_postmortem_stale_book_deadlock.md). Hard blockers are
things T2 cannot work around: missing credentials, a blocked/inactive
account, or a stale manual stop request.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opslib import ops_root, strategy_library_freshness, today_str, write_heartbeat  # noqa: E402
from check_ollama_health import check_ollama_health  # noqa: E402
from preflight_market_open import run_preflight  # noqa: E402

HARD_BLOCK_CHECKS = (
    "env_present",
    "account_active",
    "trading_not_blocked",
    "account_not_blocked",
    "no_stale_stop_file",
)


def run_premarket_prep(*, results_dir: str, day_trader_results_dir: str, trade_date: str) -> dict:
    preflight = run_preflight(results_dir=Path(day_trader_results_dir))
    ollama = check_ollama_health()
    library = strategy_library_freshness()

    hard_blockers = [
        name for name in HARD_BLOCK_CHECKS if not preflight["checks"].get(name, False)
    ]
    ready_for_trading = not hard_blockers

    warnings = []
    if not preflight["checks"].get("flat_positions", True):
        warnings.append(
            f"account not flat at pre-market check ({preflight['positions_count']} positions); "
            "T2 will flatten via --flatten-existing-at-start"
        )
    if not preflight["checks"].get("no_open_orders", True):
        warnings.append(
            f"{preflight['open_orders_count']} open order(s) at pre-market check; "
            "T2 cancels working orders before flatten"
        )
    if ollama["status"] != "ok":
        warnings.append(f"ollama: {ollama['summary']}")
    if library.get("stale"):
        warnings.append(f"strategy library stale: {library}")

    status = "ok" if ready_for_trading and not warnings else ("error" if not ready_for_trading else "degraded")

    report = {
        "trade_date": trade_date,
        "status": status,
        "ready_for_trading": ready_for_trading,
        "hard_blockers": hard_blockers,
        "warnings": warnings,
        "preflight": preflight,
        "ollama": ollama,
        "strategy_library": library,
    }

    output_dir = ops_root(results_dir) / "premarket"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{trade_date}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    write_heartbeat(
        "T1_premarket",
        status,
        trade_date=trade_date,
        results_dir=results_dir,
        details={"ready_for_trading": ready_for_trading, "warning_count": len(warnings)},
    )

    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="T1 pre-market readiness check.")
    parser.add_argument("--results-dir", default="results/ops")
    parser.add_argument("--day-trader-results-dir", default="results/autonomous_day_trader")
    parser.add_argument("--date", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env")
    args = build_parser().parse_args(argv)
    trade_date = args.date or today_str()

    report = run_premarket_prep(
        results_dir=args.results_dir,
        day_trader_results_dir=args.day_trader_results_dir,
        trade_date=trade_date,
    )
    print(json.dumps(report, indent=2))
    print(f"[{report['status'].upper()}] ready_for_trading={report['ready_for_trading']}", file=sys.stderr)
    return 0 if report["ready_for_trading"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
