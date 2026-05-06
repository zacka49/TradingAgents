from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Dict

from dotenv import load_dotenv

from tradingagents.company import (
    AutonomousCEOSettings,
    AutonomousPaperCEOAgent,
    parse_universe,
    profiles_from_choice,
)


DEFAULT_UNIVERSE = "AMD,NVDA,INTC,COIN,QQQ,SPY,PLTR,MU,TSLA,HOOD"
DEFAULT_RESULTS_DIR = "results/autonomous_day_trader"
DEFAULT_LOG_DIR = "results/autonomous_day_trader/live_logs"
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_POSITION_MONITOR_SECONDS = 5
REPO_ROOT = Path(__file__).resolve().parent


class SessionLogger:
    """Write bot events to both the VS Code terminal and a JSONL log file."""

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.log_path.open("a", encoding="utf-8", buffering=1)

    def close(self) -> None:
        self._handle.close()

    def event(self, payload: Dict[str, Any]) -> None:
        logged_at = datetime.now(UTC).isoformat()
        wrapped = {"logged_at": logged_at, **payload}
        self._handle.write(json.dumps(wrapped, default=str) + "\n")

        print(f"[{logged_at}] {terminal_message(payload)}")
        sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full autonomous Alpaca paper day-trader bot from VS Code."
        )
    )
    parser.add_argument("--strategy", choices=["safe", "risky", "both"], default="both")
    parser.add_argument("--universe", default=DEFAULT_UNIVERSE)
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument(
        "--position-monitor-seconds",
        type=int,
        default=DEFAULT_POSITION_MONITOR_SECONDS,
    )
    parser.add_argument("--results-dir", default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--max-wait-open-seconds", type=int, default=43200)
    parser.add_argument("--max-deploy-usd", type=float, default=None)
    parser.add_argument("--max-order-notional-usd", type=float, default=None)
    parser.add_argument("--target-positions", type=int, default=None)
    parser.add_argument("--liquidate-non-targets", action="store_true")
    parser.add_argument("--with-staff-memo", action="store_true")
    parser.add_argument("--with-tech-scout", action="store_true")
    return parser


def settings_from_args(args: argparse.Namespace) -> AutonomousCEOSettings:
    return AutonomousCEOSettings(
        profiles=profiles_from_choice(args.strategy),
        universe=parse_universe(args.universe),
        interval_seconds=args.interval_seconds,
        run_until_close=not args.once,
        once=bool(args.once),
        max_wait_open_seconds=args.max_wait_open_seconds,
        max_cycles=args.max_cycles,
        position_monitor_seconds=args.position_monitor_seconds,
        results_dir=str(resolve_repo_path(args.results_dir)),
        max_deploy_usd=args.max_deploy_usd,
        max_order_notional_usd=args.max_order_notional_usd,
        target_positions=args.target_positions,
        liquidate_non_targets=bool(args.liquidate_non_targets),
        ollama_staff_memo_enabled=bool(args.with_staff_memo),
        technology_scout_enabled=bool(args.with_tech_scout),
    )


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def build_log_path(log_dir: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return resolve_repo_path(log_dir) / f"day_trader_bot_{stamp}.jsonl"


def env_status() -> Dict[str, bool]:
    keys = [
        "APCA_API_KEY_ID",
        "APCA_API_SECRET_KEY",
        "APCA_API_BASE_URL",
        "ALPACA_STOCK_FEED",
    ]
    return {key: bool(os.getenv(key)) for key in keys}


def terminal_message(payload: Dict[str, Any]) -> str:
    event = payload.get("event")
    if event == "day_trader_bot_start":
        settings = payload.get("settings", {})
        return (
            "CEO online. I am running the Alpaca paper day trader now. "
            f"Universe: {', '.join(settings.get('universe', []))}. "
            f"Profiles: {', '.join(settings.get('profiles', []))}. "
            f"Strategy scan every {settings.get('interval_seconds')} seconds, "
            f"position monitor every {settings.get('position_monitor_seconds')} seconds. "
            f"Log: {payload.get('log_file')}."
        )
    if event == "waiting_for_market_open":
        wait_minutes = int(payload.get("wait_seconds", 0)) // 60
        return (
            "Market is closed. I am waiting for the US session to open "
            f"in about {wait_minutes} minutes."
        )
    if event == "market_closed_once_skip":
        return "Market is closed, so I am not running a one-off scan."
    if event == "market_closed_stop":
        return "Market is closed. I am standing the trading desk down."
    if event == "market_closed_next_open_too_far":
        return "The next market open is too far away for this run, so I am stopping."
    if event == "autonomous_ceo_cycle_start":
        cycle = payload.get("cycle")
        universe = payload.get("universe", [])
        return (
            f"Cycle {cycle}: running research across {len(universe)} live symbols. "
            "I am checking price, volume, momentum, spread, and risk gates quickly."
        )
    if event == "autonomous_ceo_profile_start":
        profile = payload.get("strategy_profile")
        return (
            f"Running {profile} strategy desk. Research, strategy selection, "
            "risk checks, and order planning are moving now."
        )
    if event == "autonomous_ceo_profile_complete":
        profile = payload.get("strategy_profile")
        top = ", ".join(payload.get("top_candidates", [])[:5]) or "none"
        targets = payload.get("target_weights", {})
        if targets:
            target_text = ", ".join(
                f"{ticker} {float(weight):.1%}" for ticker, weight in targets.items()
            )
            action = f"Target book: {target_text}."
        else:
            action = "No clean entry cleared the gates this pass."
        return (
            f"{profile} desk finished. Top live candidates: {top}. {action} "
            f"Submitted {payload.get('submitted_orders', 0)} order(s), "
            f"blocked {payload.get('blocked_orders', 0)}."
        )
    if event == "autonomous_ceo_trade_submitted":
        return (
            "Placing trade complete. "
            f"{str(payload.get('side', '')).upper()} {payload.get('quantity')} "
            f"{payload.get('ticker')} for about "
            f"${float(payload.get('estimated_notional_usd', 0)):.2f} via "
            f"{payload.get('strategy_profile')} / {payload.get('strategy')}."
        )
    if event == "autonomous_ceo_trade_not_placed":
        return (
            "Trade desk reviewed an order but did not place it. "
            f"{str(payload.get('side', '')).upper()} {payload.get('ticker')} "
            f"was blocked because {payload.get('blocked_reason') or 'risk rules'}."
        )
    if event == "autonomous_ceo_cycle":
        return (
            f"Cycle {payload.get('cycle')} complete. I have written the run "
            "artifacts and am ready for the next fast scan."
        )
    if event == "autonomous_ceo_sleep":
        return (
            f"Deep strategy scan finished. I will run the next full scan in "
            f"{payload.get('sleep_seconds')} seconds, while the live position "
            "monitor keeps watching open trades."
        )
    if event == "autonomous_ceo_position_monitor":
        positions_count = payload.get("positions_count", 0)
        open_orders_count = payload.get("open_orders_count", 0)
        if positions_count:
            symbols = ", ".join(
                str(position.get("symbol"))
                for position in payload.get("positions", [])
                if position.get("symbol")
            )
            return (
                "Monitoring live risk. "
                f"Open positions: {positions_count} ({symbols}). "
                f"Open orders/brackets: {open_orders_count}. "
                f"Next full strategy scan in {payload.get('seconds_to_next_cycle')}s."
            )
        return (
            "Monitoring live risk. No open positions right now. "
            f"Open orders/brackets: {open_orders_count}. "
            f"Next full strategy scan in {payload.get('seconds_to_next_cycle')}s."
        )
    if event == "autonomous_ceo_position_monitor_error":
        return (
            "Live risk monitor could not read positions this tick: "
            f"{payload.get('error_type')}: {payload.get('error')}."
        )
    if event == "day_trader_bot_stop":
        return f"CEO stopped cleanly with exit code {payload.get('exit_code')}."
    if event == "day_trader_bot_interrupted_by_user":
        return "Run interrupted from the terminal. CEO is standing down."
    if event == "day_trader_bot_error":
        return (
            f"CEO hit an error: {payload.get('error_type')}: "
            f"{payload.get('error')}. Full traceback is in the JSONL log."
        )
    return f"{event or 'event'}: {json.dumps(payload, default=str)}"


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env", override=True)
    args = build_parser().parse_args(argv)
    settings = settings_from_args(args)
    logger = SessionLogger(build_log_path(args.log_dir))

    try:
        logger.event(
            {
                "event": "day_trader_bot_start",
                "mode": "alpaca_paper",
                "cwd": str(Path.cwd()),
                "log_file": str(logger.log_path),
                "settings": asdict(settings),
                "environment": env_status(),
            }
        )
        exit_code = AutonomousPaperCEOAgent(settings).run(event_sink=logger.event)
        logger.event({"event": "day_trader_bot_stop", "exit_code": exit_code})
        return exit_code
    except KeyboardInterrupt:
        logger.event({"event": "day_trader_bot_interrupted_by_user"})
        return 130
    except Exception as exc:
        logger.event(
            {
                "event": "day_trader_bot_error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        return 1
    finally:
        logger.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
