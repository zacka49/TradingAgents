"""T2 - the trading session.

Single-book rule: this is the only script that may submit paper orders. The
Codex CEO runner stays research/briefing-only (T3, T4). Always launches with
``--flatten-existing-at-start`` so a stale book can never deadlock the next
session again (see docs/incident_postmortem_stale_book_deadlock.md).

Risk policy v1 (approved 2026-07-18, docs/business_recovery_plan.md):
safe profile only, 15% max deployment (~$15k of a ~$100k paper account),
4 concurrent positions, $500 daily loss halt, 0.5% daily drawdown halt, and a
weekly circuit breaker (-1.5% of the week's starting equity) enforced here
before the day trader is even launched.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opslib import (  # noqa: E402
    list_day_trader_sessions_for_date,
    ops_root,
    today_str,
    weekly_circuit_breaker_status,
    write_heartbeat,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DAY_TRADER_SCRIPT = REPO_ROOT / "scripts" / "run_autonomous_day_trader.py"

DEFAULT_MAX_DEPLOY_USD = 15000.0
DEFAULT_MAX_ORDER_NOTIONAL_USD = 3000.0
DEFAULT_TARGET_POSITIONS = 4
DEFAULT_MAX_SESSION_LOSS_USD = 500.0
DEFAULT_MAX_SESSION_DRAWDOWN_PCT = 0.5
DEFAULT_WEEKLY_LOSS_LIMIT_PCT = 1.5
SUBPROCESS_TIMEOUT_SECONDS = 8 * 60 * 60  # safety net; the bot exits itself at/after close


def build_day_trader_command(
    *,
    python_exe: str,
    results_dir: str,
    max_deploy_usd: float,
    max_order_notional_usd: float,
    target_positions: int,
    max_session_loss_usd: float,
    max_session_drawdown_pct: float,
) -> list[str]:
    return [
        python_exe,
        str(DAY_TRADER_SCRIPT),
        "--strategy",
        "safe",
        "--run-until-close",
        "--flatten-existing-at-start",
        "--results-dir",
        results_dir,
        "--max-deploy-usd",
        str(max_deploy_usd),
        "--max-order-notional-usd",
        str(max_order_notional_usd),
        "--target-positions",
        str(target_positions),
        "--max-session-loss-usd",
        str(max_session_loss_usd),
        "--max-session-drawdown-pct",
        str(max_session_drawdown_pct),
    ]


def _premarket_ready(ops_results_dir: str, trade_date: str) -> tuple[bool, str]:
    """Read T1's status for today. Missing or hard-blocked premarket data
    means T2 refuses to launch, even if it would otherwise be scheduled."""
    path = ops_root(ops_results_dir) / "premarket" / f"{trade_date}.json"
    if not path.exists():
        return False, "premarket_status_missing"
    try:
        premarket = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False, "premarket_status_unreadable"
    if not premarket.get("ready_for_trading", False):
        blockers = ", ".join(premarket.get("hard_blockers", [])) or "unknown"
        return False, f"premarket_hard_blockers: {blockers}"
    return True, "ok"


def run_trading_session(
    *,
    ops_results_dir: str,
    day_trader_results_dir: str,
    trade_date: str,
    weekly_loss_limit_pct: float,
    max_deploy_usd: float,
    max_order_notional_usd: float,
    target_positions: int,
    max_session_loss_usd: float,
    max_session_drawdown_pct: float,
    dry_run: bool = False,
    require_premarket_ready: bool = True,
) -> dict:
    if require_premarket_ready:
        ready, reason = _premarket_ready(ops_results_dir, trade_date)
        if not ready:
            write_heartbeat(
                "T2_trading_session",
                "skipped",
                trade_date=trade_date,
                results_dir=ops_results_dir,
                details={"reason": reason},
            )
            return {"trade_date": trade_date, "status": "skipped", "reason": reason}

    breaker = weekly_circuit_breaker_status(weekly_loss_limit_pct=weekly_loss_limit_pct)

    if breaker.breached:
        details = {"circuit_breaker": breaker.__dict__}
        write_heartbeat(
            "T2_trading_session",
            "skipped",
            trade_date=trade_date,
            results_dir=ops_results_dir,
            details=details,
        )
        return {
            "trade_date": trade_date,
            "status": "skipped",
            "reason": "weekly_circuit_breaker_breached",
            "circuit_breaker": breaker.__dict__,
        }

    command = build_day_trader_command(
        python_exe=sys.executable,
        results_dir=day_trader_results_dir,
        max_deploy_usd=max_deploy_usd,
        max_order_notional_usd=max_order_notional_usd,
        target_positions=target_positions,
        max_session_loss_usd=max_session_loss_usd,
        max_session_drawdown_pct=max_session_drawdown_pct,
    )

    if dry_run:
        write_heartbeat(
            "T2_trading_session",
            "skipped",
            trade_date=trade_date,
            results_dir=ops_results_dir,
            details={"reason": "dry_run", "command": command},
        )
        return {
            "trade_date": trade_date,
            "status": "skipped",
            "reason": "dry_run",
            "command": command,
            "circuit_breaker": breaker.__dict__,
        }

    result = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=True,
        text=True,
    )

    sessions = list_day_trader_sessions_for_date(trade_date, day_trader_results_dir)
    status = "ok" if result.returncode == 0 else "error"

    write_heartbeat(
        "T2_trading_session",
        status,
        trade_date=trade_date,
        results_dir=ops_results_dir,
        details={
            "returncode": result.returncode,
            "circuit_breaker": breaker.__dict__,
            "sessions_recorded": len(sessions),
            "stderr_tail": result.stderr[-2000:] if result.stderr else "",
        },
    )

    return {
        "trade_date": trade_date,
        "status": status,
        "returncode": result.returncode,
        "command": command,
        "circuit_breaker": breaker.__dict__,
        "sessions_recorded": len(sessions),
        "sessions": sessions,
        "stdout_tail": result.stdout[-4000:] if result.stdout else "",
        "stderr_tail": result.stderr[-4000:] if result.stderr else "",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="T2 trading session (safe profile only).")
    parser.add_argument("--results-dir", default="results/ops")
    parser.add_argument("--day-trader-results-dir", default="results/autonomous_day_trader")
    parser.add_argument("--date", default=None)
    parser.add_argument("--weekly-loss-limit-pct", type=float, default=DEFAULT_WEEKLY_LOSS_LIMIT_PCT)
    parser.add_argument("--max-deploy-usd", type=float, default=DEFAULT_MAX_DEPLOY_USD)
    parser.add_argument("--max-order-notional-usd", type=float, default=DEFAULT_MAX_ORDER_NOTIONAL_USD)
    parser.add_argument("--target-positions", type=int, default=DEFAULT_TARGET_POSITIONS)
    parser.add_argument("--max-session-loss-usd", type=float, default=DEFAULT_MAX_SESSION_LOSS_USD)
    parser.add_argument(
        "--max-session-drawdown-pct", type=float, default=DEFAULT_MAX_SESSION_DRAWDOWN_PCT
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check the circuit breaker and print the command without launching the day trader.",
    )
    parser.add_argument(
        "--skip-premarket-check",
        action="store_true",
        help="Skip the requirement that T1 (premarket_prep.py) already ran and reported ready_for_trading.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env")
    args = build_parser().parse_args(argv)
    trade_date = args.date or today_str()

    report = run_trading_session(
        ops_results_dir=args.results_dir,
        day_trader_results_dir=args.day_trader_results_dir,
        trade_date=trade_date,
        weekly_loss_limit_pct=args.weekly_loss_limit_pct,
        max_deploy_usd=args.max_deploy_usd,
        max_order_notional_usd=args.max_order_notional_usd,
        target_positions=args.target_positions,
        max_session_loss_usd=args.max_session_loss_usd,
        max_session_drawdown_pct=args.max_session_drawdown_pct,
        dry_run=args.dry_run,
        require_premarket_ready=not args.skip_premarket_check,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
