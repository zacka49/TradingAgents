from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

from tradingagents.company.codex_ceo_company import CodexCEOCompanyRunner
from tradingagents.company.strategy_profiles import apply_day_trader_profile
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution import AlpacaPaperBroker


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
    position_monitor_seconds: int = 5
    results_dir: str = "results/autonomous_day_trader"
    max_deploy_usd: float | None = None
    max_order_notional_usd: float | None = None
    target_positions: int | None = None
    liquidate_non_targets: bool = False
    ollama_staff_memo_enabled: bool = False
    technology_scout_enabled: bool = False
    news_politics_scan_enabled: bool = True
    news_politics_max_symbols: int | None = None
    news_politics_queries: Sequence[str] = field(default_factory=tuple)
    alpaca_stock_feed: str | None = None
    flatten_at_close: bool = True
    flatten_minutes_before_close: int = 5
    stop_new_entries_minutes_before_close: int = 15
    flatten_on_max_cycles: bool = True
    cancel_orders_before_flatten: bool = True


class AutonomousPaperCEOAgent:
    """Self-running CEO agent for Alpaca paper day trading.

    This class owns the market-clock wait, profile orchestration, paper-trading
    cycles, and artifact logging. It lets a local process run the company
    without Codex manually supervising every cycle.
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

            close_guard = self.handle_day_trader_close_guard(sink)
            if close_guard == "stop":
                return 0
            if close_guard == "wait":
                continue

            cycle += 1
            sink(
                {
                    "event": "autonomous_ceo_cycle_start",
                    "cycle": cycle,
                    "started_at": self.now_fn().isoformat(),
                    "profiles": list(self.settings.profiles),
                    "universe": list(self.settings.universe),
                    "interval_seconds": self.settings.interval_seconds,
                }
            )
            sink(self.run_cycle(cycle, event_sink=sink))

            if self.settings.once or not self.settings.run_until_close:
                return 0
            if self.settings.max_cycles and cycle >= self.settings.max_cycles:
                if self.settings.flatten_on_max_cycles:
                    self.flatten_day_trader_positions(
                        sink,
                        reason="max_cycles_reached",
                    )
                return 0

            clock = self.broker.get_clock()
            if not clock.get("is_open"):
                sink({"event": "market_closed_stop", "clock": clock})
                return 0

            sleep_seconds = max(5, int(self.settings.interval_seconds))
            next_close = parse_alpaca_time(clock.get("next_close"))
            if next_close is not None:
                seconds_to_close = int((next_close - self.now_fn()).total_seconds())
                if seconds_to_close <= 0:
                    return 0
                if self.settings.flatten_at_close:
                    flatten_seconds = max(
                        0,
                        int(self.settings.flatten_minutes_before_close) * 60,
                    )
                    seconds_to_flatten = seconds_to_close - flatten_seconds
                    if seconds_to_flatten > 0:
                        sleep_seconds = min(sleep_seconds, seconds_to_flatten)
                sleep_seconds = min(sleep_seconds, max(1, seconds_to_close))
            sink(
                {
                    "event": "autonomous_ceo_sleep",
                    "cycle": cycle,
                    "sleep_seconds": sleep_seconds,
                    "next_close": clock.get("next_close"),
                }
            )
            if not self.monitor_positions_until_next_cycle(sleep_seconds, cycle, sink):
                return 0

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

    def handle_day_trader_close_guard(self, sink: EventSink) -> str:
        if not self.settings.flatten_at_close:
            return "run"

        clock = self.broker.get_clock()
        next_close = parse_alpaca_time(clock.get("next_close"))
        if next_close is None:
            return "run"

        seconds_to_close = int((next_close - self.now_fn()).total_seconds())
        if seconds_to_close <= 0 or not clock.get("is_open"):
            self.flatten_day_trader_positions(
                sink,
                reason="market_closed_or_closing",
            )
            sink({"event": "market_closed_stop", "clock": clock})
            return "stop"

        flatten_seconds = max(0, int(self.settings.flatten_minutes_before_close) * 60)
        no_new_entries_seconds = max(
            flatten_seconds,
            int(self.settings.stop_new_entries_minutes_before_close) * 60,
        )
        if seconds_to_close <= flatten_seconds:
            self.flatten_day_trader_positions(
                sink,
                reason="pre_close_flatten_window",
                seconds_to_close=seconds_to_close,
            )
            return "stop"

        if seconds_to_close <= no_new_entries_seconds:
            wait_seconds = max(1, seconds_to_close - flatten_seconds)
            sink(
                {
                    "event": "autonomous_ceo_no_new_entries_window",
                    "seconds_to_close": seconds_to_close,
                    "wait_seconds": wait_seconds,
                    "next_close": clock.get("next_close"),
                }
            )
            if not self.monitor_positions_until_next_cycle(wait_seconds, 0, sink):
                return "stop"
            return "wait"

        return "run"

    def flatten_day_trader_positions(
        self,
        sink: EventSink,
        *,
        reason: str,
        seconds_to_close: int | None = None,
    ) -> None:
        positions: List[Dict[str, Any]] = []
        open_orders: List[Dict[str, Any]] = []
        try:
            positions = list(self.broker.get_positions().get("positions", []))
        except Exception as exc:
            sink(
                {
                    "event": "autonomous_ceo_eod_flatten_error",
                    "stage": "get_positions",
                    "reason": reason,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            return

        try:
            open_orders = list(self.broker.get_orders("open").get("orders", []))
        except Exception:
            open_orders = []

        if not positions and not open_orders:
            sink(
                {
                    "event": "autonomous_ceo_eod_flatten_skipped",
                    "reason": reason,
                    "seconds_to_close": seconds_to_close,
                    "positions_count": 0,
                    "open_orders_count": 0,
                }
            )
            return

        sink(
            {
                "event": "autonomous_ceo_eod_flatten_start",
                "reason": reason,
                "seconds_to_close": seconds_to_close,
                "positions_count": len(positions),
                "open_orders_count": len(open_orders),
                "positions": summarize_positions(positions),
                "open_orders": summarize_open_orders(open_orders),
            }
        )

        try:
            response = self.broker.close_all_positions(
                cancel_orders=bool(self.settings.cancel_orders_before_flatten)
            )
            sink(
                {
                    "event": "autonomous_ceo_eod_flatten_complete",
                    "reason": reason,
                    "cancel_orders": bool(self.settings.cancel_orders_before_flatten),
                    "response": response,
                }
            )
        except Exception as exc:
            sink(
                {
                    "event": "autonomous_ceo_eod_flatten_error",
                    "stage": "close_all_positions",
                    "reason": reason,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    def run_cycle(
        self, cycle: int, event_sink: EventSink | None = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "event": "autonomous_ceo_cycle",
            "cycle": cycle,
            "started_at": self.now_fn().isoformat(),
            "profiles": [],
        }
        for profile in self.settings.profiles:
            if event_sink:
                event_sink(
                    {
                        "event": "autonomous_ceo_profile_start",
                        "cycle": cycle,
                        "strategy_profile": profile,
                        "stage": "research_strategy_and_trade",
                    }
                )
            profile_result = self.run_profile(profile)
            payload["profiles"].append(profile_result)
            if event_sink:
                event_sink(profile_stage_summary(cycle, profile_result))
                for order_event in profile_order_events(cycle, profile_result):
                    event_sink(order_event)
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

        return {
            "strategy_profile": profile,
            "market_open": result.market_open,
            "artifact_dir": result.artifact_dir,
            "top_candidates": [candidate.ticker for candidate in result.candidates[:10]],
            "target_weights": result.target_weights,
            "submitted_orders": result.submitted_orders,
            "blocked_orders": result.blocked_orders,
            "orders": [asdict(order) for order in result.order_plans],
        }

    def monitor_positions_until_next_cycle(
        self, sleep_seconds: int, cycle: int, sink: EventSink
    ) -> bool:
        monitor_seconds = max(1, int(self.settings.position_monitor_seconds))
        deadline = self.now_fn().timestamp() + max(0, sleep_seconds)

        while True:
            remaining = deadline - self.now_fn().timestamp()
            if remaining <= 0:
                return True

            sink(self.position_monitor_event(cycle, remaining))
            self.sleep_fn(min(monitor_seconds, remaining))

            clock = self.broker.get_clock()
            if not clock.get("is_open"):
                sink({"event": "market_closed_stop", "clock": clock})
                return False

    def position_monitor_event(
        self, cycle: int, seconds_to_next_cycle: float
    ) -> Dict[str, Any]:
        positions = []
        open_orders = []
        try:
            positions = list(self.broker.get_positions().get("positions", []))
        except Exception as exc:
            return {
                "event": "autonomous_ceo_position_monitor_error",
                "cycle": cycle,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "seconds_to_next_cycle": round(max(0.0, seconds_to_next_cycle), 1),
            }
        try:
            open_orders = list(self.broker.get_orders("open").get("orders", []))
        except Exception:
            open_orders = []

        return {
            "event": "autonomous_ceo_position_monitor",
            "cycle": cycle,
            "seconds_to_next_cycle": round(max(0.0, seconds_to_next_cycle), 1),
            "positions_count": len(positions),
            "open_orders_count": len(open_orders),
            "positions": summarize_positions(positions),
            "open_orders": summarize_open_orders(open_orders),
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
        config["codex_ceo_news_political_scan_enabled"] = bool(
            self.settings.news_politics_scan_enabled
        )
        config["day_trader_flatten_at_close"] = bool(self.settings.flatten_at_close)
        config["day_trader_flatten_minutes_before_close"] = int(
            self.settings.flatten_minutes_before_close
        )
        config["day_trader_stop_new_entries_minutes_before_close"] = int(
            self.settings.stop_new_entries_minutes_before_close
        )
        config["day_trader_flatten_on_max_cycles"] = bool(
            self.settings.flatten_on_max_cycles
        )
        config["day_trader_cancel_orders_before_flatten"] = bool(
            self.settings.cancel_orders_before_flatten
        )
        if self.settings.news_politics_max_symbols is not None:
            config["codex_ceo_news_political_max_symbols"] = int(
                self.settings.news_politics_max_symbols
            )
        if self.settings.news_politics_queries:
            config["codex_ceo_news_political_queries"] = list(
                self.settings.news_politics_queries
            )
        if self.settings.alpaca_stock_feed:
            config["alpaca_stock_feed"] = self.settings.alpaca_stock_feed
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


def profile_stage_summary(cycle: int, profile_result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event": "autonomous_ceo_profile_complete",
        "cycle": cycle,
        "strategy_profile": profile_result["strategy_profile"],
        "artifact_dir": profile_result["artifact_dir"],
        "top_candidates": profile_result["top_candidates"],
        "target_weights": profile_result["target_weights"],
        "submitted_orders": profile_result["submitted_orders"],
        "blocked_orders": profile_result["blocked_orders"],
    }


def profile_order_events(
    cycle: int, profile_result: Dict[str, Any]
) -> List[Dict[str, Any]]:
    events = []
    for order in profile_result["orders"]:
        events.append(
            {
                "event": (
                    "autonomous_ceo_trade_submitted"
                    if order["submitted"]
                    else "autonomous_ceo_trade_not_placed"
                ),
                "cycle": cycle,
                "strategy_profile": profile_result["strategy_profile"],
                "ticker": order["ticker"],
                "side": order["side"],
                "quantity": order["quantity"],
                "estimated_notional_usd": order["estimated_notional_usd"],
                "strategy": order.get("strategy"),
                "submitted": order["submitted"],
                "blocked_reason": order.get("blocked_reason"),
                "order_response": order.get("order_response"),
            }
        )
    return events


def summarize_positions(positions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary = []
    for position in positions[:10]:
        summary.append(
            {
                "symbol": position.get("symbol"),
                "qty": position.get("qty"),
                "market_value": position.get("market_value"),
                "unrealized_pl": position.get("unrealized_pl"),
                "unrealized_plpc": position.get("unrealized_plpc"),
                "current_price": position.get("current_price"),
            }
        )
    return summary


def summarize_open_orders(orders: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary = []
    for order in orders[:10]:
        summary.append(
            {
                "id": order.get("id"),
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "qty": order.get("qty"),
                "type": order.get("type") or order.get("order_type"),
                "order_class": order.get("order_class"),
                "status": order.get("status"),
                "limit_price": order.get("limit_price"),
                "stop_price": order.get("stop_price"),
            }
        )
    return summary


def profiles_from_choice(choice: str) -> List[str]:
    if choice == "both":
        return ["safe", "risky"]
    return [choice]


def parse_universe(raw: str) -> List[str]:
    return [item.strip().upper() for item in raw.split(",") if item.strip()]
