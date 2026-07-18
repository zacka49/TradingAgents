"""Build the one-page daily digest the CEO reads instead of raw run artifacts.

Pure formatting lives here so it can be unit tested without subprocesses or
live Ollama/Alpaca calls; ``gather_daily_digest_inputs`` does the I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fix_tickets import list_fix_tickets  # noqa: E402
from opslib import (  # noqa: E402
    list_day_trader_sessions_for_date,
    ops_root,
    read_heartbeat,
    strategy_library_freshness,
    utc_now,
)

GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


@dataclass
class DigestInputs:
    trade_date: str
    premarket: dict[str, Any] | None
    t1_heartbeat: dict[str, Any] | None
    t2_heartbeat: dict[str, Any] | None
    day_trader_sessions: list[dict[str, Any]]
    ceo_summary: dict[str, Any] | None
    ceo_error: str | None
    post_market_review: dict[str, Any] | None
    post_market_error: str | None
    strategy_library: dict[str, Any] = field(default_factory=dict)
    open_fix_tickets: list[dict[str, Any]] = field(default_factory=list)
    pnl_attribution: dict[str, Any] | None = None


def gather_daily_digest_inputs(
    *,
    trade_date: str,
    ops_results_dir: str = "results/ops",
    day_trader_results_dir: str = "results/autonomous_day_trader",
    ceo_summary: dict[str, Any] | None = None,
    ceo_error: str | None = None,
    post_market_review: dict[str, Any] | None = None,
    post_market_error: str | None = None,
    pnl_attribution: dict[str, Any] | None = None,
) -> DigestInputs:
    ops_dir = ops_root(ops_results_dir)
    premarket = _read_json(ops_dir / "premarket" / f"{trade_date}.json")
    return DigestInputs(
        trade_date=trade_date,
        premarket=premarket,
        t1_heartbeat=read_heartbeat("T1_premarket", trade_date, ops_results_dir),
        t2_heartbeat=read_heartbeat("T2_trading_session", trade_date, ops_results_dir),
        day_trader_sessions=list_day_trader_sessions_for_date(trade_date, day_trader_results_dir),
        ceo_summary=ceo_summary,
        ceo_error=ceo_error,
        post_market_review=post_market_review,
        post_market_error=post_market_error,
        strategy_library=strategy_library_freshness(),
        open_fix_tickets=list_fix_tickets(ops_results_dir, status="open"),
        pnl_attribution=pnl_attribution,
    )


def _session_line(session: dict[str, Any]) -> str:
    summary = session.get("session", session)
    initial = summary.get("initial_equity")
    final = summary.get("final_equity")
    change = None
    if isinstance(initial, (int, float)) and isinstance(final, (int, float)):
        change = final - initial
    change_str = f"${change:+.2f}" if change is not None else "n/a"
    return (
        f"- session `{summary.get('session_id', '?')}`: cycles={summary.get('cycles_completed', '?')}, "
        f"P&L={change_str}, positions={summary.get('positions_count', '?')}, "
        f"open_orders={summary.get('open_orders_count', '?')}"
    )


def build_daily_digest(inputs: DigestInputs) -> str:
    lines: list[str] = []
    lines.append(f"# Daily Digest - {inputs.trade_date}")
    lines.append("")
    lines.append(f"Generated: {utc_now().isoformat()}")
    lines.append("")
    lines.append("Paper account only. Operational record, not financial advice.")
    lines.append("")

    attention: list[str] = []

    # --- Status at a glance ---
    lines.append("## Status At A Glance")
    t1_status = (inputs.t1_heartbeat or {}).get("status", "MISSING")
    t2_status = (inputs.t2_heartbeat or {}).get("status", "MISSING")
    review_ok = inputs.post_market_review is not None and not inputs.post_market_error
    avg_score = (inputs.post_market_review or {}).get("average_score")
    ready = (inputs.premarket or {}).get("ready_for_trading")

    lines.append(f"- Pre-market (T1): **{t1_status}** (ready_for_trading={ready})")
    lines.append(f"- Trading session (T2): **{t2_status}**")
    lines.append(
        f"- Post-market review (T3): **{'ok' if review_ok else 'error'}**"
        + (f", average scorecard {avg_score}" if avg_score is not None else "")
    )
    lines.append(f"- Strategy library: {'STALE' if inputs.strategy_library.get('stale') else 'fresh'}")
    lines.append(f"- Open fix tickets: {len(inputs.open_fix_tickets)}")
    lines.append("")

    if t1_status == "MISSING":
        attention.append("T1 pre-market prep did not run today (no heartbeat found).")
    if t2_status == "MISSING":
        attention.append("T2 trading session did not run today (no heartbeat found).")
    elif t2_status == "error":
        attention.append("T2 trading session ended with an error - check results/ops/heartbeat.")
    if inputs.strategy_library.get("stale"):
        attention.append("Strategy library is stale - run scripts/run_strategy_research_department.py.")
    if inputs.ceo_error:
        attention.append(f"CEO briefing run failed: {inputs.ceo_error}")
    if inputs.post_market_error:
        attention.append(f"Post-market review failed: {inputs.post_market_error}")

    # --- Trading session detail ---
    lines.append("## Trading Session")
    if inputs.t2_heartbeat:
        details = inputs.t2_heartbeat.get("details", {})
        breaker = details.get("circuit_breaker")
        if breaker:
            lines.append(
                f"- Weekly circuit breaker: breached={breaker.get('breached')}, "
                f"week P&L={breaker.get('cumulative_pnl_pct')}% "
                f"(limit -1.5%), sessions counted this week={breaker.get('sessions_counted')}"
            )
            if breaker.get("breached"):
                attention.append("Weekly circuit breaker is BREACHED - trading is paused this week.")
        if details.get("reason") == "weekly_circuit_breaker_breached":
            lines.append("- Session skipped: weekly circuit breaker breached.")
    if inputs.day_trader_sessions:
        for session in inputs.day_trader_sessions:
            lines.append(_session_line(session))
    else:
        lines.append("- No day-trader session recorded for this date.")
    lines.append("")

    # --- CEO briefing (research only) ---
    lines.append("## CEO Briefing (research only, no orders)")
    if inputs.ceo_summary:
        top = inputs.ceo_summary.get("top_candidates", [])
        blocked = inputs.ceo_summary.get("blocked_orders", [])
        lines.append(f"- Market open at run time: {inputs.ceo_summary.get('market_open')}")
        lines.append(f"- Top candidates: {', '.join(top) if top else 'none'}")
        lines.append(f"- Blocked order plans: {len(blocked) if isinstance(blocked, list) else blocked}")
    else:
        lines.append(f"- Not available{f': {inputs.ceo_error}' if inputs.ceo_error else ''}")
    lines.append("")

    # --- Scorecards ---
    lines.append("## AI Agent Scorecards")
    scorecards = (inputs.post_market_review or {}).get("scorecards") if inputs.post_market_review else None
    if scorecards:
        lines.append("| Agent | Score | Grade | Top Gap |")
        lines.append("| --- | ---: | --- | --- |")
        for card in scorecards:
            gaps = card.get("gaps") or []
            lines.append(
                f"| {card.get('agent')} | {card.get('score')} | {card.get('grade')} | "
                f"{gaps[0] if gaps else 'none'} |"
            )
            if GRADE_ORDER.get(str(card.get("grade")), 4) <= GRADE_ORDER["D"]:
                attention.append(f"{card.get('agent')} scored {card.get('grade')} - {', '.join(gaps) or 'no detail'}")
    else:
        lines.append("- No scorecards available for this date.")
    lines.append("")

    # --- P&L attribution ---
    if inputs.pnl_attribution:
        lines.append("## P&L Attribution")
        lines.append(
            f"- Session rows added today: {inputs.pnl_attribution.get('session_rows_added', 0)}, "
            f"exit-event rows added: {inputs.pnl_attribution.get('exit_event_rows_added', 0)}"
        )
        lines.append(f"- Rolling log: `{inputs.pnl_attribution.get('sessions_csv', '')}`")
        lines.append("")

    # --- Fix tickets ---
    lines.append("## Open Fix Tickets")
    if inputs.open_fix_tickets:
        lines.append("| Severity | Subject | Occurrences | Summary |")
        lines.append("| --- | --- | ---: | --- |")
        for ticket in inputs.open_fix_tickets:
            lines.append(
                f"| {ticket.get('severity')} | {ticket.get('subject')} | "
                f"{ticket.get('occurrences')} | {ticket.get('summary')} |"
            )
            if ticket.get("severity") == "high":
                attention.append(f"Open high-severity ticket: {ticket.get('id')} - {ticket.get('summary')}")
    else:
        lines.append("- No open tickets.")
    lines.append("")

    # --- Attention needed ---
    lines.append("## Attention Needed")
    if attention:
        for item in attention:
            lines.append(f"- {item}")
    else:
        lines.append("- Nothing flagged.")
    lines.append("")

    return "\n".join(lines)


def write_daily_digest(inputs: DigestInputs, ops_results_dir: str = "results/ops") -> tuple[Path, Path]:
    markdown = build_daily_digest(inputs)
    output_dir = ops_root(ops_results_dir) / "digests"
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / f"{inputs.trade_date}.md"
    json_path = output_dir / f"{inputs.trade_date}.json"
    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "trade_date": inputs.trade_date,
                "premarket": inputs.premarket,
                "t1_heartbeat": inputs.t1_heartbeat,
                "t2_heartbeat": inputs.t2_heartbeat,
                "day_trader_sessions": inputs.day_trader_sessions,
                "ceo_summary": inputs.ceo_summary,
                "post_market_review": inputs.post_market_review,
                "strategy_library": inputs.strategy_library,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return md_path, json_path
