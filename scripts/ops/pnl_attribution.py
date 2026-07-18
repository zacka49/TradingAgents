"""P&L attribution rollup (Phase 2.2, docs/business_recovery_plan.md).

Honest scope note: the day trader's session reports do not currently tag a
position with the strategy ID that opened it, so this module cannot yet
attribute P&L *by strategy* (opening_range_breakout_15m vs momentum_breakout)
-- only by session (date) and by symbol/exit-reason, from
``risk_exit_events``. Strategy-level attribution, which the scaling ladder in
docs/business_recovery_plan.md needs, requires tagging positions with their
originating strategy at entry time in ``tradingagents/company/autonomous_ceo.py``.
That is a change to the trading engine itself, not the ops layer, and is
deliberately left for a dedicated follow-up rather than bolted on here.

What this *does* give: a rolling, deduplicated record of session-level P&L
and per-exit-event outcomes, so a human (or a future automated pass) can see
trends over weeks instead of re-deriving them from scattered JSON files.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opslib import list_day_trader_sessions_for_date, ops_root, today_str  # noqa: E402

SESSIONS_CSV_HEADER = [
    "trade_date",
    "session_id",
    "initial_equity",
    "final_equity",
    "pnl_usd",
    "pnl_pct",
    "cycles_completed",
    "positions_count",
    "open_orders_count",
    "risk_exit_count",
]

EXIT_EVENTS_CSV_HEADER = [
    "trade_date",
    "session_id",
    "symbol",
    "reason",
    "unrealized_pl_at_exit",
    "unrealized_plpc_at_exit",
    "held_minutes",
]


def _read_existing_keys(csv_path: Path, key_columns: list[str]) -> set[tuple]:
    if not csv_path.exists():
        return set()
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {tuple(row.get(col, "") for col in key_columns) for row in reader}


def _append_rows(csv_path: Path, header: list[str], rows: list[dict]) -> int:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def append_session_pnl(*, trade_date: str, day_trader_results_dir: str, ops_results_dir: str) -> int:
    csv_path = ops_root(ops_results_dir) / "pnl_attribution" / "sessions.csv"
    existing = _read_existing_keys(csv_path, ["session_id"])

    rows = []
    for payload in list_day_trader_sessions_for_date(trade_date, day_trader_results_dir):
        summary = payload.get("session", payload)
        session_id = summary.get("session_id", "")
        if (session_id,) in existing:
            continue
        initial_equity = summary.get("initial_equity")
        final_equity = summary.get("final_equity")
        pnl_usd = None
        pnl_pct = None
        if isinstance(initial_equity, (int, float)) and isinstance(final_equity, (int, float)):
            pnl_usd = round(final_equity - initial_equity, 2)
            pnl_pct = round((pnl_usd / initial_equity) * 100.0, 4) if initial_equity else 0.0
        rows.append(
            {
                "trade_date": trade_date,
                "session_id": session_id,
                "initial_equity": initial_equity,
                "final_equity": final_equity,
                "pnl_usd": pnl_usd,
                "pnl_pct": pnl_pct,
                "cycles_completed": summary.get("cycles_completed"),
                "positions_count": summary.get("positions_count"),
                "open_orders_count": summary.get("open_orders_count"),
                "risk_exit_count": len(payload.get("risk_exit_events") or []),
            }
        )

    return _append_rows(csv_path, SESSIONS_CSV_HEADER, rows)


def append_exit_events(*, trade_date: str, day_trader_results_dir: str, ops_results_dir: str) -> int:
    csv_path = ops_root(ops_results_dir) / "pnl_attribution" / "exit_events.csv"
    existing = _read_existing_keys(csv_path, ["session_id", "symbol", "reason", "held_minutes"])

    rows = []
    for payload in list_day_trader_sessions_for_date(trade_date, day_trader_results_dir):
        summary = payload.get("session", payload)
        session_id = summary.get("session_id", "")
        for event in payload.get("risk_exit_events") or []:
            key = (session_id, str(event.get("symbol", "")), str(event.get("reason", "")), str(event.get("held_minutes", "")))
            if key in existing:
                continue
            rows.append(
                {
                    "trade_date": trade_date,
                    "session_id": session_id,
                    "symbol": event.get("symbol", ""),
                    "reason": event.get("reason", ""),
                    "unrealized_pl_at_exit": event.get("unrealized_pl"),
                    "unrealized_plpc_at_exit": event.get("unrealized_plpc"),
                    "held_minutes": event.get("held_minutes"),
                }
            )

    return _append_rows(csv_path, EXIT_EVENTS_CSV_HEADER, rows)


def run_pnl_attribution(*, trade_date: str, day_trader_results_dir: str, ops_results_dir: str) -> dict:
    sessions_added = append_session_pnl(
        trade_date=trade_date,
        day_trader_results_dir=day_trader_results_dir,
        ops_results_dir=ops_results_dir,
    )
    exit_events_added = append_exit_events(
        trade_date=trade_date,
        day_trader_results_dir=day_trader_results_dir,
        ops_results_dir=ops_results_dir,
    )
    return {
        "trade_date": trade_date,
        "session_rows_added": sessions_added,
        "exit_event_rows_added": exit_events_added,
        "sessions_csv": str(ops_root(ops_results_dir) / "pnl_attribution" / "sessions.csv"),
        "exit_events_csv": str(ops_root(ops_results_dir) / "pnl_attribution" / "exit_events.csv"),
        "note": (
            "Strategy-level attribution is not yet available: session reports do not "
            "tag positions with the originating strategy ID."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Append today's day-trader P&L to the rolling attribution CSVs.")
    parser.add_argument("--results-dir", default="results/ops")
    parser.add_argument("--day-trader-results-dir", default="results/autonomous_day_trader")
    parser.add_argument("--date", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    import json

    args = build_parser().parse_args(argv)
    trade_date = args.date or today_str()
    report = run_pnl_attribution(
        trade_date=trade_date,
        day_trader_results_dir=args.day_trader_results_dir,
        ops_results_dir=args.results_dir,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
