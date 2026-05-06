from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from tradingagents.company import (
    AutonomousCEOSettings,
    AutonomousPaperCEOAgent,
    parse_universe,
    profiles_from_choice,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the self-running CEO agent for Alpaca paper day trading."
    )
    parser.add_argument("--strategy", choices=["safe", "risky", "both"], default="both")
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--position-monitor-seconds", type=int, default=5)
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
    parser.add_argument("--with-staff-memo", action="store_true")
    parser.add_argument("--with-tech-scout", action="store_true")
    return parser


def settings_from_args(args: argparse.Namespace) -> AutonomousCEOSettings:
    return AutonomousCEOSettings(
        profiles=profiles_from_choice(args.strategy),
        universe=parse_universe(args.universe) if args.universe else tuple(),
        interval_seconds=args.interval_seconds,
        run_until_close=bool(args.run_until_close),
        once=bool(args.once),
        max_wait_open_seconds=args.max_wait_open_seconds,
        max_cycles=args.max_cycles,
        position_monitor_seconds=args.position_monitor_seconds,
        results_dir=args.results_dir,
        max_deploy_usd=args.max_deploy_usd,
        max_order_notional_usd=args.max_order_notional_usd,
        target_positions=args.target_positions,
        liquidate_non_targets=bool(args.liquidate_non_targets),
        ollama_staff_memo_enabled=bool(args.with_staff_memo),
        technology_scout_enabled=bool(args.with_tech_scout),
    )


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env", override=True)
    args = build_parser().parse_args(argv)
    return AutonomousPaperCEOAgent(settings_from_args(args)).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
