"""Shared helpers for the scheduled operations layer (T1-T4).

These scripts are the operations function the business review found missing:
something has to run the CEO cycle on a schedule, record whether it ran, and
give the CEO one place to see what happened without reading run artifacts by
hand. Nothing here submits orders; that stays in
``tradingagents.execution`` / ``tradingagents.company``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


def today_str() -> str:
    return utc_now().strftime("%Y-%m-%d")


def ops_root(results_dir: str | Path = "results/ops") -> Path:
    root = Path(results_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def heartbeat_path(task: str, trade_date: str, results_dir: str | Path = "results/ops") -> Path:
    return ops_root(results_dir) / "heartbeat" / f"{task}_{trade_date}.json"


def write_heartbeat(
    task: str,
    status: str,
    *,
    trade_date: str | None = None,
    results_dir: str | Path = "results/ops",
    details: dict[str, Any] | None = None,
) -> Path:
    """Record that a scheduled task ran. ``status`` is one of ok/degraded/error/skipped."""
    trade_date = trade_date or today_str()
    path = heartbeat_path(task, trade_date, results_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": task,
        "status": status,
        "trade_date": trade_date,
        "recorded_at": utc_now().isoformat(),
        "details": details or {},
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    return path


def read_heartbeat(
    task: str, trade_date: str, results_dir: str | Path = "results/ops"
) -> dict[str, Any] | None:
    path = heartbeat_path(task, trade_date, results_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_day_trader_sessions_for_date(
    trade_date: str, results_dir: str | Path = "results/autonomous_day_trader"
) -> list[dict[str, Any]]:
    """Load final session-report JSON payloads whose session id starts with the UTC date."""
    reports_dir = Path(results_dir) / "session_reports"
    if not reports_dir.exists():
        return []
    prefix_date = trade_date.replace("-", "")
    sessions: list[dict[str, Any]] = []
    for path in sorted(reports_dir.glob("daytrader_*_final.json")):
        match = re.search(r"daytrader_(\d{8})T\d{6}Z_final\.json$", path.name)
        if not match or match.group(1) != prefix_date:
            continue
        try:
            sessions.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return sessions


def week_start(as_of: date) -> date:
    """Monday of the ISO week containing ``as_of``."""
    return as_of - timedelta(days=as_of.weekday())


def trading_days_in_week(as_of: date) -> list[str]:
    start = week_start(as_of)
    return [(start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(5)]


@dataclass
class CircuitBreakerStatus:
    breached: bool
    week_start: str
    sessions_counted: int
    baseline_equity: float | None
    cumulative_pnl_usd: float
    cumulative_pnl_pct: float
    reason: str


def weekly_circuit_breaker_status(
    *,
    as_of: date | None = None,
    results_dir: str | Path = "results/autonomous_day_trader",
    weekly_loss_limit_pct: float = 1.5,
) -> CircuitBreakerStatus:
    """Sum this week's realized day-trader session P&L against a loss limit.

    Baseline equity is the ``initial_equity`` of the first session recorded
    this week; if no sessions have run yet this week there is nothing to
    breach.
    """
    as_of = as_of or utc_now().date()
    days = [day for day in trading_days_in_week(as_of) if day <= as_of.strftime("%Y-%m-%d")]

    baseline_equity: float | None = None
    cumulative_pnl = 0.0
    sessions_counted = 0
    for day in days:
        for session in list_day_trader_sessions_for_date(day, results_dir):
            summary = session.get("session", session)
            initial_equity = summary.get("initial_equity")
            final_equity = summary.get("final_equity")
            if initial_equity is None or final_equity is None:
                continue
            if baseline_equity is None:
                baseline_equity = float(initial_equity)
            cumulative_pnl += float(final_equity) - float(initial_equity)
            sessions_counted += 1

    if baseline_equity is None or sessions_counted == 0:
        return CircuitBreakerStatus(
            breached=False,
            week_start=week_start(as_of).strftime("%Y-%m-%d"),
            sessions_counted=0,
            baseline_equity=None,
            cumulative_pnl_usd=0.0,
            cumulative_pnl_pct=0.0,
            reason="no_sessions_recorded_this_week",
        )

    cumulative_pnl_pct = (cumulative_pnl / baseline_equity) * 100.0
    breached = cumulative_pnl_pct <= -abs(weekly_loss_limit_pct)
    reason = (
        f"weekly loss {cumulative_pnl_pct:.2f}% breaches -{weekly_loss_limit_pct:.2f}% limit"
        if breached
        else "within_weekly_loss_limit"
    )
    return CircuitBreakerStatus(
        breached=breached,
        week_start=week_start(as_of).strftime("%Y-%m-%d"),
        sessions_counted=sessions_counted,
        baseline_equity=baseline_equity,
        cumulative_pnl_usd=round(cumulative_pnl, 2),
        cumulative_pnl_pct=round(cumulative_pnl_pct, 3),
        reason=reason,
    )


def weekly_pnl_breakdown(
    *,
    as_of: date | None = None,
    results_dir: str | Path = "results/autonomous_day_trader",
) -> list[dict[str, Any]]:
    """Per-day session count and realized P&L for the ISO week containing ``as_of``."""
    as_of = as_of or utc_now().date()
    rows: list[dict[str, Any]] = []
    for day in trading_days_in_week(as_of):
        sessions = list_day_trader_sessions_for_date(day, results_dir)
        day_pnl = 0.0
        counted = 0
        for session in sessions:
            summary = session.get("session", session)
            initial_equity = summary.get("initial_equity")
            final_equity = summary.get("final_equity")
            if initial_equity is None or final_equity is None:
                continue
            day_pnl += float(final_equity) - float(initial_equity)
            counted += 1
        rows.append(
            {
                "date": day,
                "sessions": len(sessions),
                "sessions_with_pnl": counted,
                "pnl_usd": round(day_pnl, 2),
            }
        )
    return rows


def strategy_library_freshness(
    report_path: str | Path = "knowledge/strategy_library/strategy_research_report.md",
    max_age_days: int = 7,
) -> dict[str, Any]:
    path = Path(report_path)
    if not path.exists():
        return {"present": False, "stale": True, "reason": "report_missing"}

    generated_at = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.search(r"Generated:\s*(\S+)", line)
        if match:
            generated_at = match.group(1)
            break

    if not generated_at:
        return {"present": True, "stale": True, "reason": "no_generated_timestamp_found"}

    try:
        generated_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return {"present": True, "stale": True, "reason": f"unparseable_timestamp:{generated_at}"}

    if generated_dt.tzinfo is None:
        generated_dt = generated_dt.replace(tzinfo=UTC)
    age_days = (utc_now() - generated_dt).total_seconds() / 86400.0
    stale = age_days > max_age_days
    return {
        "present": True,
        "stale": stale,
        "generated_at": generated_at,
        "age_days": round(age_days, 2),
        "max_age_days": max_age_days,
    }
