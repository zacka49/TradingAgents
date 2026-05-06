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

        print(f"\n[{logged_at}] {payload.get('event', 'event')}")
        print(json.dumps(payload, indent=2, default=str))
        sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full autonomous Alpaca paper day-trader bot from VS Code."
        )
    )
    parser.add_argument("--strategy", choices=["safe", "risky", "both"], default="both")
    parser.add_argument("--universe", default=DEFAULT_UNIVERSE)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--results-dir", default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--max-wait-open-seconds", type=int, default=43200)
    parser.add_argument("--max-deploy-usd", type=float, default=None)
    parser.add_argument("--max-order-notional-usd", type=float, default=None)
    parser.add_argument("--target-positions", type=int, default=None)
    parser.add_argument("--liquidate-non-targets", action="store_true")
    parser.add_argument("--no-whatsapp", action="store_true")
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
        results_dir=str(resolve_repo_path(args.results_dir)),
        max_deploy_usd=args.max_deploy_usd,
        max_order_notional_usd=args.max_order_notional_usd,
        target_positions=args.target_positions,
        liquidate_non_targets=bool(args.liquidate_non_targets),
        whatsapp_enabled=not bool(args.no_whatsapp),
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
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_FROM",
        "WHATSAPP_TO",
    ]
    return {key: bool(os.getenv(key)) for key in keys}


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
