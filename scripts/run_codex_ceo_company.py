from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

from tradingagents.company import CodexCEOCompanyRunner
from tradingagents.default_config import DEFAULT_CONFIG


def _parse_universe(raw: str) -> list[str]:
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the compute-light Codex CEO company workflow."
    )
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    parser.add_argument("--universe", default="")
    parser.add_argument("--submit-paper", action="store_true")
    parser.add_argument("--ceo-approved", action="store_true")
    parser.add_argument("--autonomous-paper", action="store_true")
    parser.add_argument("--liquidate-non-targets", action="store_true")
    parser.add_argument("--disable-bracket-orders", action="store_true")
    parser.add_argument("--max-deploy-usd", type=float, default=None)
    parser.add_argument("--target-positions", type=int, default=None)
    parser.add_argument("--max-order-notional-usd", type=float, default=None)
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--no-ollama-staff", action="store_true")
    parser.add_argument("--no-backtest-lab", action="store_true")
    parser.add_argument("--allow-weak-backtests", action="store_true")
    parser.add_argument("--no-tech-scout", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env")
    args = build_parser().parse_args(argv)

    config = DEFAULT_CONFIG.copy()
    if args.results_dir:
        config["results_dir"] = str(Path(args.results_dir))
    if args.max_deploy_usd is not None:
        config["portfolio_max_deploy_usd"] = args.max_deploy_usd
    if args.target_positions is not None:
        config["portfolio_target_positions"] = args.target_positions
    if args.max_order_notional_usd is not None:
        config["max_order_notional_usd"] = args.max_order_notional_usd
    if args.no_ollama_staff:
        config["ollama_staff_memo_enabled"] = False
    if args.no_backtest_lab:
        config["backtest_lab_enabled"] = False
    if args.allow_weak_backtests:
        config["backtest_lab_gate_targets"] = False
    if args.no_tech_scout:
        config["technology_scout_enabled"] = False
    if args.autonomous_paper:
        config["autonomous_paper_trading_enabled"] = True
        config["ceo_approval_required"] = False
    if args.disable_bracket_orders:
        config["use_bracket_orders"] = False
    config["portfolio_liquidate_non_targets"] = bool(args.liquidate_non_targets)

    runner = CodexCEOCompanyRunner(config)
    result = runner.run(
        trade_date=args.date,
        universe=_parse_universe(args.universe) if args.universe else None,
        submit=bool(args.submit_paper or args.autonomous_paper),
        ceo_approved=bool(args.ceo_approved or args.autonomous_paper),
    )

    summary = {
        "account_status": result.account_status,
        "market_open": result.market_open,
        "artifact_dir": result.artifact_dir,
        "top_candidates": [candidate.ticker for candidate in result.candidates[:10]],
        "target_weights": result.target_weights,
        "orders": [asdict(order) for order in result.order_plans],
        "submitted_orders": result.submitted_orders,
        "blocked_orders": result.blocked_orders,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
