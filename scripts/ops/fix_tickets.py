"""Fix-ticket tracking (Phase 2.1, docs/business_recovery_plan.md).

The business review found the learning loop open-circuit: scorecards and run
errors were produced every day but nothing converted them into something
that had to be dealt with, so the same failures (the CL=F crash, the flat
gate) sat unfixed for weeks. This module closes that loop: any scorecard
grade below C, or any run-level error, becomes a ticket that stays open
until someone (or a future run) resolves it.

Tickets are keyed by (source, subject) without the date, so a recurring
problem accumulates occurrences on one ticket instead of spawning a new one
every day -- the daily digest should get *quieter* as things get fixed, not
noisier.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opslib import ops_root, utc_now  # noqa: E402

GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
BELOW_C_THRESHOLD = GRADE_ORDER["C"]  # strictly below this value qualifies; C itself does not


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def ticket_id(source: str, subject: str) -> str:
    return f"{_slug(source)}--{_slug(subject)}"


def _ticket_path(ops_results_dir: str, tid: str) -> Path:
    return ops_root(ops_results_dir) / "fix_tickets" / f"{tid}.json"


def upsert_fix_ticket(
    ops_results_dir: str,
    *,
    source: str,
    subject: str,
    severity: str,
    summary: str,
    trade_date: str,
    detail: dict | None = None,
) -> dict:
    tid = ticket_id(source, subject)
    path = _ticket_path(ops_results_dir, tid)
    path.parent.mkdir(parents=True, exist_ok=True)

    now = utc_now().isoformat()
    if path.exists():
        try:
            ticket = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            ticket = {}
    else:
        ticket = {}

    trade_dates = ticket.get("trade_dates", [])
    if trade_date not in trade_dates:
        trade_dates.append(trade_date)

    ticket.update(
        {
            "id": tid,
            "source": source,
            "subject": subject,
            "severity": severity,
            "summary": summary,
            "detail": detail or {},
            "status": "open",  # recurrence reopens a previously resolved ticket
            "occurrences": ticket.get("occurrences", 0) + 1,
            "first_seen": ticket.get("first_seen", now),
            "last_seen": now,
            "trade_dates": trade_dates[-30:],
        }
    )

    path.write_text(json.dumps(ticket, indent=2), encoding="utf-8")
    return ticket


def resolve_fix_ticket(ops_results_dir: str, tid: str, *, note: str | None = None) -> dict | None:
    path = _ticket_path(ops_results_dir, tid)
    if not path.exists():
        return None
    ticket = json.loads(path.read_text(encoding="utf-8"))
    ticket["status"] = "resolved"
    ticket["resolved_at"] = utc_now().isoformat()
    if note:
        ticket["resolution_note"] = note
    path.write_text(json.dumps(ticket, indent=2), encoding="utf-8")
    return ticket


def list_fix_tickets(ops_results_dir: str, *, status: str | None = None) -> list[dict]:
    tickets_dir = ops_root(ops_results_dir) / "fix_tickets"
    if not tickets_dir.exists():
        return []
    tickets = []
    for path in sorted(tickets_dir.glob("*.json")):
        try:
            ticket = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if status is None or ticket.get("status") == status:
            tickets.append(ticket)
    return tickets


def generate_fix_tickets(
    *,
    ops_results_dir: str,
    trade_date: str,
    post_market_review: dict | None,
    ceo_error: str | None,
    post_market_error: str | None,
    t1_status: str | None = None,
    t2_status: str | None = None,
    t2_error_detail: str | None = None,
) -> list[dict]:
    created: list[dict] = []

    scorecards = (post_market_review or {}).get("scorecards") or []
    for card in scorecards:
        grade = str(card.get("grade", "A"))
        if GRADE_ORDER.get(grade, 4) < BELOW_C_THRESHOLD:
            agent = str(card.get("agent", "Unknown Agent"))
            gaps = card.get("gaps") or []
            created.append(
                upsert_fix_ticket(
                    ops_results_dir,
                    source="scorecard",
                    subject=agent,
                    severity="high" if grade == "F" else "medium",
                    summary=f"{agent} scored {grade} ({card.get('score')}): {', '.join(gaps) or 'no detail'}",
                    trade_date=trade_date,
                    detail={"grade": grade, "score": card.get("score"), "gaps": gaps},
                )
            )

    if ceo_error:
        created.append(
            upsert_fix_ticket(
                ops_results_dir,
                source="run_error",
                subject="ceo_briefing_run",
                severity="high",
                summary=f"CEO briefing run failed: {ceo_error[:200]}",
                trade_date=trade_date,
                detail={"error": ceo_error},
            )
        )

    if post_market_error:
        created.append(
            upsert_fix_ticket(
                ops_results_dir,
                source="run_error",
                subject="post_market_review",
                severity="high",
                summary=f"Post-market review failed: {post_market_error[:200]}",
                trade_date=trade_date,
                detail={"error": post_market_error},
            )
        )

    if t1_status == "error":
        created.append(
            upsert_fix_ticket(
                ops_results_dir,
                source="run_error",
                subject="t1_premarket",
                severity="high",
                summary="T1 pre-market prep reported a hard blocker.",
                trade_date=trade_date,
                detail={},
            )
        )

    if t2_status == "error":
        created.append(
            upsert_fix_ticket(
                ops_results_dir,
                source="run_error",
                subject="t2_trading_session",
                severity="high",
                summary=f"T2 trading session failed: {(t2_error_detail or '')[:200]}",
                trade_date=trade_date,
                detail={"error": t2_error_detail},
            )
        )

    return created


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List or resolve operational fix tickets.")
    parser.add_argument("--results-dir", default="results/ops")
    parser.add_argument("--list", action="store_true", help="List open tickets (default action).")
    parser.add_argument("--all", action="store_true", help="With --list, include resolved tickets too.")
    parser.add_argument("--resolve", default=None, help="Ticket id to mark resolved.")
    parser.add_argument("--note", default=None, help="Optional resolution note for --resolve.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.resolve:
        ticket = resolve_fix_ticket(args.results_dir, args.resolve, note=args.note)
        if ticket is None:
            print(f"No ticket found with id {args.resolve}", file=sys.stderr)
            return 1
        print(json.dumps(ticket, indent=2))
        return 0

    tickets = list_fix_tickets(args.results_dir, status=None if args.all else "open")
    print(json.dumps(tickets, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
