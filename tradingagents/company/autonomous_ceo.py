from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence

from tradingagents.company.codex_ceo_company import CodexCEOCompanyRunner
from tradingagents.company.strategy_profiles import apply_day_trader_profile
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution import AlpacaPaperBroker
from tradingagents.notifications import send_trade_notification


EventSink = Callable[[Dict[str, Any]], None]
RunnerFactory = Callable[[Dict[str, Any], AlpacaPaperBroker], CodexCEOCompanyRunner]
SleepFn = Callable[[float], None]
NowFn = Callable[[], datetime]


@dataclass(frozen=True)
class AutonomousCEOSettings:
    """Configuration for the self-running paper-trading CEO agent."""

    profiles: Sequence[str] = ("safe", "risky")
    universe: Sequence[str] = field(default_factory=tuple)
    interval_seconds: int = 300
    run_until_close: bool = True
    once: bool = False
    max_wait_open_seconds: int = 7200
    max_cycles: int = 0
    results_dir: str = "results/autonomous_day_trader"
    max_deploy_usd: float | None = None
    max_order_notional_usd: float | None = None
    target_positions: int | None = None
    liquidate_non_targets: bool = False
    whatsapp_enabled: bool = True
    ollama_staff_memo_enabled: bool = False
    technology_scout_enabled: bool = False


class AutonomousPaperCEOAgent:
    """Self-running CEO agent for Alpaca paper day trading.

    This class owns the market-clock wait, profile orchestration, paper-trading
    cycles, artifact logging, and trade notifications. It lets a local process
    run the company without Codex manually supervising every cycle.
    """

    def __init__(
        self,
        settings: AutonomousCEOSettings,
        *,
        broker: AlpacaPaperBroker | None = None,
        base_config: Dict[str, Any] | None = None,
        runner_factory: RunnerFactory | None = None,
        sleep_fn: SleepFn = time.sleep,
        now_fn: NowFn | None = None,
    ) -> None:
        self.settings = settings
        self.broker = broker or AlpacaPaperBroker()
        self.base_config = (base_config or DEFAULT_CONFIG).copy()
        self.runner_factory = runner_factory or (
            lambda config, broker: CodexCEOCompanyRunner(config, broker=broker)
        )
        self.sleep_fn = sleep_fn
        self.now_fn = now_fn or (lambda: datetime.now(UTC))

    def run(self, event_sink: EventSink | None = None) -> int:
        sink = event_sink or print_json_event
        cycle = 0

        while True:
            if not self.wait_until_open_or_exit(sink):
                return 0

            cycle += 1
            sink(self.run_cycle(cycle))

            if self.settings.once or not self.settings.run_until_close:
                return 0
            if self.settings.max_cycles and cycle >= self.settings.max_cycles:
                return 0

            clock = self.broker.get_clock()
            if not clock.get("is_open"):
                sink({"event": "market_closed_stop", "clock": clock})
                return 0

            sleep_seconds = max(30, int(self.settings.interval_seconds))
            next_close = parse_alpaca_time(clock.get("next_close"))
            if next_close is not None:
                seconds_to_close = int((next_close - self.now_fn()).total_seconds())
                if seconds_to_close <= 0:
                    return 0
                sleep_seconds = min(sleep_seconds, max(1, seconds_to_close))
            self.sleep_fn(sleep_seconds)

    def wait_until_open_or_exit(self, sink: EventSink) -> bool:
        clock = self.broker.get_clock()
        if clock.get("is_open"):
            return True
        if self.settings.once:
            sink({"event": "market_closed_once_skip", "clock": clock})
            return False

        next_open = parse_alpaca_time(clock.get("next_open"))
        if next_open is None:
            sink({"event": "market_closed_no_next_open", "clock": clock})
            return False

        wait_seconds = int((next_open - self.now_fn()).total_seconds())
        if wait_seconds > self.settings.max_wait_open_seconds:
            sink(
                {
                    "event": "market_closed_next_open_too_far",
                    "wait_seconds": wait_seconds,
                    "clock": clock,
                }
            )
            return False

        if wait_seconds > 0:
            sink(
                {
                    "event": "waiting_for_market_open",
                    "wait_seconds": wait_seconds,
                    "next_open": clock.get("next_open"),
                }
            )
            self.sleep_fn(min(wait_seconds, self.settings.max_wait_open_seconds))
        return bool(self.broker.get_clock().get("is_open"))

    def run_cycle(self, cycle: int) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "event": "autonomous_ceo_cycle",
            "cycle": cycle,
            "started_at": self.now_fn().isoformat(),
            "profiles": [],
        }
        for profile in self.settings.profiles:
            payload["profiles"].append(self.run_profile(profile))
        payload["finished_at"] = self.now_fn().isoformat()
        return payload

    def run_profile(self, profile: str) -> Dict[str, Any]:
        config = self._profile_config(profile)
        runner = self.runner_factory(config, self.broker)
        result = runner.run(
            trade_date=self.now_fn().strftime("%Y-%m-%d"),
            universe=list(self.settings.universe) if self.settings.universe else None,
            submit=True,
            ceo_approved=True,
        )

        notification_results = []
        if self.settings.whatsapp_enabled:
            account = self.broker.get_account()
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

    def _profile_config(self, profile: str) -> Dict[str, Any]:
        config = apply_day_trader_profile(self.base_config, profile)
        config["results_dir"] = str(Path(self.settings.results_dir) / profile)
        config["portfolio_liquidate_non_targets"] = bool(
            self.settings.liquidate_non_targets
        )
        config["ollama_staff_memo_enabled"] = bool(
            self.settings.ollama_staff_memo_enabled
        )
        config["technology_scout_enabled"] = bool(
            self.settings.technology_scout_enabled
        )
        config["refresh_live_prices_before_submit"] = True
        config["enforce_market_open"] = True
        if self.settings.max_deploy_usd is not None:
            config["portfolio_max_deploy_usd"] = self.settings.max_deploy_usd
        if self.settings.max_order_notional_usd is not None:
            config["max_order_notional_usd"] = self.settings.max_order_notional_usd
        if self.settings.target_positions is not None:
            config["portfolio_target_positions"] = self.settings.target_positions
        return config


def parse_alpaca_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def print_json_event(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))
    sys.stdout.flush()


def profiles_from_choice(choice: str) -> List[str]:
    if choice == "both":
        return ["safe", "risky"]
    return [choice]


def parse_universe(raw: str) -> List[str]:
    return [item.strip().upper() for item in raw.split(",") if item.strip()]

