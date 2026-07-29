from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv

# DEFAULT_CONFIG reads role-model overrides at import time.
load_dotenv(".env", override=True)

from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.execution import AlpacaPaperBroker  # noqa: E402
from tradingagents.llm_clients import apply_compute_policy  # noqa: E402


REQUIRED_ENV = [
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "APCA_API_BASE_URL",
    "ALPACA_STOCK_FEED",
]


def _count_items(payload: Any, key: str) -> int:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    if isinstance(payload, list):
        return len(payload)
    return 0


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _env_present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def run_preflight(*, results_dir: Path) -> dict[str, Any]:
    load_dotenv(".env", override=True)

    broker = AlpacaPaperBroker()
    clock = broker.get_clock()
    account = broker.get_account()
    positions = broker.get_positions()
    open_orders = broker.get_orders("open")
    config = apply_compute_policy(DEFAULT_CONFIG)

    stop_file = results_dir / "control" / "stop_requested.json"
    missing_env = [key for key in REQUIRED_ENV if not _env_present(key)]
    positions_count = _count_items(positions, "positions")
    open_orders_count = _count_items(open_orders, "orders")

    checks = {
        "env_present": not missing_env,
        "account_active": account.get("status") == "ACTIVE",
        "trading_not_blocked": not _truthy(account.get("trading_blocked")),
        "account_not_blocked": not _truthy(account.get("account_blocked")),
        "flat_positions": positions_count == 0,
        "no_open_orders": open_orders_count == 0,
        "no_stale_stop_file": not stop_file.exists(),
        "local_only_llm": config.get("llm_provider") == "ollama"
        and not config.get("hosted_llm_allowed", False),
        "quick_model_ready": config.get("quick_think_llm") in config.get(
            "compute_policy_report", {}
        ).get("installed_local_models", []),
        "deep_model_ready": config.get("deep_think_llm") in config.get(
            "compute_policy_report", {}
        ).get("installed_local_models", []),
        "close_discipline_enabled": bool(config.get("day_trader_flatten_at_close"))
        and int(config.get("day_trader_flatten_minutes_before_close", 0)) > 0
        and int(config.get("day_trader_stop_new_entries_minutes_before_close", 0)) > 0,
        "bracket_orders_enabled": bool(config.get("use_bracket_orders")),
    }

    ready = all(checks.values())
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "ready_for_market_open": ready,
        "checks": checks,
        "missing_env": missing_env,
        "clock": clock,
        "account_summary": {
            "status": account.get("status"),
            "trading_blocked": account.get("trading_blocked"),
            "account_blocked": account.get("account_blocked"),
            "equity": account.get("equity"),
            "cash": account.get("cash"),
            "buying_power": account.get("buying_power"),
            "daytrade_count": account.get("daytrade_count"),
            "long_market_value": account.get("long_market_value"),
            "short_market_value": account.get("short_market_value"),
        },
        "positions_count": positions_count,
        "open_orders_count": open_orders_count,
        "stop_file": str(stop_file),
        "llm_summary": {
            "provider": config.get("llm_provider"),
            "quick_model": config.get("quick_think_llm"),
            "deep_model": config.get("deep_think_llm"),
            "hosted_llm_allowed": config.get("hosted_llm_allowed"),
            "role_models": config.get("role_model_overrides", {}),
            "installed_local_models": config.get("compute_policy_report", {}).get(
                "installed_local_models", []
            ),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check Alpaca paper and local-model readiness before market open."
    )
    parser.add_argument(
        "--results-dir",
        default="results/autonomous_day_trader",
        help="Autonomous day trader results directory.",
    )
    parser.add_argument(
        "--output",
        default="results/autonomous_day_trader/preflight_latest.json",
        help="Where to write the JSON preflight report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_preflight(results_dir=Path(args.results_dir))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote {output}", file=sys.stderr)
    return 0 if report["ready_for_market_open"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
