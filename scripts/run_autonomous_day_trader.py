from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, Iterable, List

from dotenv import load_dotenv

from tradingagents.company import CodexCEOCompanyRunner, apply_day_trader_profile
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution import AlpacaPaperBroker
from tradingagents.notifications import send_trade_notification


def _parse_universe(raw: str) -> list[str]:
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _parse_alpaca_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _profiles(strategy: str) -> List[str]:
    if strategy == "both":
        return ["safe", "risky"]
    return [strategy]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run autonomous Alpaca paper day-trading while the US market is open."
    )
    parser.add_argument("--strategy", choices=["safe", "risky", "both"], default="both")
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--run-until-close", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-wait-open-seconds", type=int, default=7200)
    parser.add_argument("--universe", default="")
    parser.add_argument("--results-dir", default="results/autonomous_day_trader")
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--max-deploy-usd", type=float, default=None)
    parser.add_argument("--max-order-notional-usd", type=float, default=None)
    parser.add_argument("--target-positions", type=int, default=None)
    parser.add_argument("--liquidate-non-targets", action="store_true")
    parser.add_argument("--no-whatsapp", action="store_true")
    parser.add_argument("--with-staff-memo", action="store_true")
    parser.add_argument("--with-tech-scout", action="store_true")
    return parser


def _base_config(args: argparse.Namespace, profile: str) -> Dict[str, Any]:
    config = apply_day_trader_profile(DEFAULT_CONFIG.copy(), profile)
    config["results_dir"] = str(Path(args.results_dir) / profile)
    config["portfolio_liquidate_non_targets"] = bool(args.liquidate_non_targets)
    config["ollama_staff_memo_enabled"] = bool(args.with_staff_memo)
    config["technology_scout_enabled"] = bool(args.with_tech_scout)
    config["refresh_live_prices_before_submit"] = True
    config["enforce_market_open"] = True
    if args.max_deploy_usd is not None:
        config["portfolio_max_deploy_usd"] = args.max_deploy_usd
    if args.max_order_notional_usd is not None:
        config["max_order_notional_usd"] = args.max_order_notional_usd
    if args.target_positions is not None:
        config["portfolio_target_positions"] = args.target_positions
    return config


def _run_profile(
    *,
    args: argparse.Namespace,
    profile: str,
    broker: AlpacaPaperBroker,
    universe: Iterable[str] | None,
) -> Dict[str, Any]:
    runner = CodexCEOCompanyRunner(_base_config(args, profile), broker=broker)
    result = runner.run(
        trade_date=datetime.now(UTC).strftime("%Y-%m-%d"),
        universe=list(universe) if universe else None,
        submit=True,
        ceo_approved=True,
    )

    account = broker.get_account()
    notification_results = []
    if not args.no_whatsapp:
        for order in result.order_plans:
            if order.submitted:
                notification_results.append(
                    asdict(
                        send_trade_notification(
                            strategy_profile=profile,
                            order=order,
                            account=account,
                        )
                    )
                )

    return {
        "strategy_profile": profile,
        "market_open": result.market_open,
        "artifact_dir": result.artifact_dir,
        "top_candidates": [candidate.ticker for candidate in result.candidates[:10]],
        "target_weights": result.target_weights,
        "submitted_orders": result.submitted_orders,
        "blocked_orders": result.blocked_orders,
        "orders": [asdict(order) for order in result.order_plans],
        "notifications": notification_results,
    }


def _print_event(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))
    sys.stdout.flush()


def _sleep_until_open_or_exit(
    *,
    broker: AlpacaPaperBroker,
    args: argparse.Namespace,
) -> bool:
    clock = broker.get_clock()
    if clock.get("is_open"):
        return True
    if args.once:
        _print_event({"event": "market_closed_once_skip", "clock": clock})
        return False

    next_open = _parse_alpaca_time(clock.get("next_open"))
    if next_open is None:
        _print_event({"event": "market_closed_no_next_open", "clock": clock})
        return False

    wait_seconds = int((next_open - datetime.now(UTC)).total_seconds())
    if wait_seconds > args.max_wait_open_seconds:
        _print_event(
            {
                "event": "market_closed_next_open_too_far",
                "wait_seconds": wait_seconds,
                "clock": clock,
            }
        )
        return False

    if wait_seconds > 0:
        _print_event(
            {
                "event": "waiting_for_market_open",
                "wait_seconds": wait_seconds,
                "next_open": clock.get("next_open"),
            }
        )
        time.sleep(min(wait_seconds, args.max_wait_open_seconds))
    return bool(broker.get_clock().get("is_open"))


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env", override=True)
    args = build_parser().parse_args(argv)
    broker = AlpacaPaperBroker()
    universe = _parse_universe(args.universe) if args.universe else None

    cycle = 0
    while True:
        if not _sleep_until_open_or_exit(broker=broker, args=args):
            return 0

        cycle += 1
        cycle_payload = {
            "event": "autonomous_cycle",
            "cycle": cycle,
            "started_at": datetime.now(UTC).isoformat(),
            "profiles": [],
        }
        for profile in _profiles(args.strategy):
            cycle_payload["profiles"].append(
                _run_profile(
                    args=args,
                    profile=profile,
                    broker=broker,
                    universe=universe,
                )
            )
        cycle_payload["finished_at"] = datetime.now(UTC).isoformat()
        _print_event(cycle_payload)

        if args.once or not args.run_until_close:
            return 0
        if args.max_cycles and cycle >= args.max_cycles:
            return 0

        clock = broker.get_clock()
        if not clock.get("is_open"):
            _print_event({"event": "market_closed_stop", "clock": clock})
            return 0

        next_close = _parse_alpaca_time(clock.get("next_close"))
        sleep_seconds = max(30, args.interval_seconds)
        if next_close is not None:
            seconds_to_close = int((next_close - datetime.now(UTC)).total_seconds())
            if seconds_to_close <= 0:
                return 0
            sleep_seconds = min(sleep_seconds, max(1, seconds_to_close))
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

