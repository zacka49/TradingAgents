from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

from tradingagents.company.codex_ceo_company import CodexCEOCompanyRunner
from tradingagents.company.strategy_profiles import apply_day_trader_profile
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution import AlpacaPaperBroker, OrderIntent


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
    premarket_research_enabled: bool = True
    alpaca_stock_feed: str | None = None
    flatten_at_close: bool = True
    flatten_minutes_before_close: int = 5
    stop_new_entries_minutes_before_close: int = 15
    flatten_on_max_cycles: bool = True
    cancel_orders_before_flatten: bool = True
    protect_intraday_profits: bool = True
    profit_protection_min_gain_pct: float = 0.50
    profit_protection_max_giveback_pct: float = 0.45
    profit_protection_max_giveback_fraction: float = 0.40
    profit_protection_min_remaining_gain_pct: float = 0.05
    profit_protection_min_unrealized_pl_usd: float = 5.0
    profit_protection_min_notional_usd: float = 100.0
    exit_momentum_decay: bool = True
    momentum_decay_min_minutes: int = 20
    momentum_decay_min_gain_pct: float = 0.15
    momentum_decay_max_loss_pct: float = 0.30
    momentum_decay_min_notional_usd: float = 100.0
    exit_early_adverse_moves: bool = True
    early_adverse_min_minutes: int = 5
    early_adverse_max_loss_pct: float = 0.30
    early_adverse_max_high_gain_pct: float = 0.15
    early_adverse_min_notional_usd: float = 100.0
    exit_stale_losers: bool = True
    stale_loser_max_loss_pct: float = 0.75
    stale_loser_min_notional_usd: float = 100.0
    exit_unprotected_positions: bool = True
    unprotected_position_grace_seconds: int = 60
    open_sell_coverage_threshold: float = 0.95
    stale_loser_cooldown_minutes: int = 30
    max_session_loss_usd: float = 750.0
    max_session_drawdown_pct: float = 1.0
    flatten_on_session_risk_halt: bool = True
    stop_file: str | None = None


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
        self.position_highs: Dict[str, float] = {}
        self.position_seen_at: Dict[str, float] = {}
        self.unprotected_since: Dict[str, float] = {}
        self.exit_submitted_symbols: set[str] = set()
        self.last_premarket_research_date: str = ""
        self.session_id = self.now_fn().strftime("daytrader_%Y%m%dT%H%M%SZ")
        self.session_started_at = self.now_fn()
        self.session_initial_equity: float | None = None
        self.symbol_cooldowns: Dict[str, float] = {}

    def run(self, event_sink: EventSink | None = None) -> int:
        sink = event_sink or print_json_event
        cycle = 0

        self.start_session(sink)
        try:
            while True:
                if self.handle_stop_request(sink):
                    return 0
                if not self.wait_until_open_or_exit(sink):
                    return 0
                if self.handle_stop_request(sink):
                    return 0

                close_guard = self.handle_day_trader_close_guard(sink)
                if close_guard == "stop":
                    return 0
                if close_guard == "wait":
                    continue
                if self.handle_stop_request(sink):
                    return 0
                if self.handle_session_risk_guard(sink):
                    return 0

                cycle += 1
                sink(
                    {
                        "event": "autonomous_ceo_cycle_start",
                        "session_id": self.session_id,
                        "cycle": cycle,
                        "started_at": self.now_fn().isoformat(),
                        "profiles": list(self.settings.profiles),
                        "universe": list(self.settings.universe),
                        "interval_seconds": self.settings.interval_seconds,
                        "symbol_cooldowns": self.active_cooldown_payload(),
                    }
                )
                sink(self.run_cycle(cycle, event_sink=sink))
                if self.handle_stop_request(sink):
                    return 0
                if self.handle_session_risk_guard(sink):
                    return 0

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
                        "session_id": self.session_id,
                        "cycle": cycle,
                        "sleep_seconds": sleep_seconds,
                        "next_close": clock.get("next_close"),
                    }
                )
                if not self.monitor_positions_until_next_cycle(sleep_seconds, cycle, sink):
                    return 0
        finally:
            self.finish_session(sink, cycles_completed=cycle)

    def start_session(self, sink: EventSink) -> None:
        snapshot = self.broker_snapshot()
        account = snapshot.get("account", {})
        self.session_initial_equity = account_equity(account)
        sink(
            {
                "event": "autonomous_ceo_session_start",
                "session_id": self.session_id,
                "started_at": self.session_started_at.isoformat(),
                "paper_account_only": True,
                "profiles": list(self.settings.profiles),
                "universe": list(self.settings.universe),
                "initial_equity": self.session_initial_equity,
                "account": account,
                "positions_count": len(snapshot.get("positions", [])),
                "open_orders_count": len(snapshot.get("open_orders", [])),
                "positions": summarize_positions(snapshot.get("positions", [])),
                "open_orders": summarize_open_orders(snapshot.get("open_orders", [])),
                "clock": snapshot.get("clock", {}),
                "risk_limits": {
                    "max_session_loss_usd": self.settings.max_session_loss_usd,
                    "max_session_drawdown_pct": self.settings.max_session_drawdown_pct,
                    "flatten_on_session_risk_halt": self.settings.flatten_on_session_risk_halt,
                    "stale_loser_cooldown_minutes": self.settings.stale_loser_cooldown_minutes,
                    "early_adverse_min_minutes": self.settings.early_adverse_min_minutes,
                    "early_adverse_max_loss_pct": self.settings.early_adverse_max_loss_pct,
                    "early_adverse_max_high_gain_pct": self.settings.early_adverse_max_high_gain_pct,
                    "momentum_decay_min_minutes": self.settings.momentum_decay_min_minutes,
                    "momentum_decay_min_gain_pct": self.settings.momentum_decay_min_gain_pct,
                    "momentum_decay_max_loss_pct": self.settings.momentum_decay_max_loss_pct,
                },
            }
        )

    def finish_session(self, sink: EventSink, *, cycles_completed: int) -> None:
        snapshot = self.broker_snapshot()
        account = snapshot.get("account", {})
        sink(
            {
                "event": "autonomous_ceo_session_end",
                "session_id": self.session_id,
                "started_at": self.session_started_at.isoformat(),
                "finished_at": self.now_fn().isoformat(),
                "cycles_completed": cycles_completed,
                "initial_equity": self.session_initial_equity,
                "final_equity": account_equity(account),
                "session_risk": self.session_risk_snapshot(account),
                "positions_count": len(snapshot.get("positions", [])),
                "open_orders_count": len(snapshot.get("open_orders", [])),
                "positions": summarize_positions(snapshot.get("positions", [])),
                "open_orders": summarize_open_orders(snapshot.get("open_orders", [])),
                "symbol_cooldowns": self.active_cooldown_payload(),
                "clock": snapshot.get("clock", {}),
            }
        )

    def broker_snapshot(self) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {
            "account": {},
            "positions": [],
            "open_orders": [],
            "clock": {},
            "errors": [],
        }
        try:
            snapshot["account"] = self.broker.get_account()
        except Exception as exc:
            snapshot["errors"].append(
                {"stage": "get_account", "type": type(exc).__name__, "error": str(exc)}
            )
        try:
            snapshot["positions"] = list(self.broker.get_positions().get("positions", []))
        except Exception as exc:
            snapshot["errors"].append(
                {"stage": "get_positions", "type": type(exc).__name__, "error": str(exc)}
            )
        try:
            snapshot["open_orders"] = list(self.broker.get_orders("open").get("orders", []))
        except Exception as exc:
            snapshot["errors"].append(
                {"stage": "get_orders", "type": type(exc).__name__, "error": str(exc)}
            )
        try:
            snapshot["clock"] = self.broker.get_clock()
        except Exception as exc:
            snapshot["errors"].append(
                {"stage": "get_clock", "type": type(exc).__name__, "error": str(exc)}
            )
        return snapshot

    def wait_until_open_or_exit(self, sink: EventSink) -> bool:
        if self.handle_stop_request(sink):
            return False
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

        if self.settings.premarket_research_enabled:
            self.run_premarket_research(sink, next_open=next_open)

        if wait_seconds > 0:
            sink(
                {
                    "event": "waiting_for_market_open",
                    "wait_seconds": wait_seconds,
                    "next_open": clock.get("next_open"),
                }
            )
            deadline = self.now_fn().timestamp() + min(
                wait_seconds,
                self.settings.max_wait_open_seconds,
            )
            while True:
                if self.handle_stop_request(sink):
                    return False
                remaining = deadline - self.now_fn().timestamp()
                if remaining <= 0:
                    break
                self.sleep_fn(min(60, remaining))
        return bool(self.broker.get_clock().get("is_open"))

    def stop_request_path(self) -> Path:
        if self.settings.stop_file:
            return Path(self.settings.stop_file)
        return Path(self.settings.results_dir) / "control" / "stop_requested.json"

    def handle_stop_request(self, sink: EventSink) -> bool:
        path = self.stop_request_path()
        if not path.exists():
            return False

        request: Dict[str, Any] = {}
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    request = parsed
        except Exception as exc:
            request = {
                "action": "stop",
                "reason": "invalid_stop_request_file",
                "read_error_type": type(exc).__name__,
                "read_error": str(exc),
            }

        action = str(request.get("action") or "stop").strip().lower()
        if action not in {"stop", "flatten"}:
            action = "stop"
        reason = str(request.get("reason") or "manual_stop_requested")
        sink(
            {
                "event": "manual_stop_request_received",
                "action": action,
                "reason": reason,
                "stop_file": str(path),
            }
        )

        try:
            path.unlink()
            sink(
                {
                    "event": "manual_stop_request_file_removed",
                    "stop_file": str(path),
                }
            )
        except FileNotFoundError:
            pass
        except Exception as exc:
            sink(
                {
                    "event": "manual_stop_request_file_remove_error",
                    "stop_file": str(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

        if action == "flatten":
            self.flatten_day_trader_positions(
                sink,
                reason="manual_stop_requested",
            )
        sink(
            {
                "event": "manual_stop_request_completed",
                "action": action,
                "reason": reason,
            }
        )
        return True

    def run_premarket_research(self, sink: EventSink, *, next_open: datetime) -> None:
        research_date = next_open.strftime("%Y-%m-%d")
        if self.last_premarket_research_date == research_date:
            return
        self.last_premarket_research_date = research_date

        profile = self.settings.profiles[0] if self.settings.profiles else "safe"
        config = self._profile_config(profile)
        config["results_dir"] = str(
            Path(self.settings.results_dir) / "premarket_research" / profile
        )
        config["ollama_staff_memo_enabled"] = False
        runner = self.runner_factory(config, self.broker)
        try:
            result = runner.run(
                trade_date=research_date,
                universe=list(self.settings.universe) if self.settings.universe else None,
                submit=False,
                ceo_approved=False,
            )
        except Exception as exc:
            sink(
                {
                    "event": "premarket_research_error",
                    "research_date": research_date,
                    "profile": profile,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            return

        catalyst_context = getattr(runner, "_last_catalyst_context", {}) or {}
        sink(
            {
                "event": "premarket_research_complete",
                "research_date": research_date,
                "profile": profile,
                "artifact_dir": result.artifact_dir,
                "top_candidates": [candidate.ticker for candidate in result.candidates[:10]],
                "research_queue": catalyst_context.get("ranked_research_queue", [])[:10],
                "submitted_orders": result.submitted_orders,
            }
        )

    def handle_day_trader_close_guard(self, sink: EventSink) -> str:
        if self.handle_stop_request(sink):
            return "stop"
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

    def handle_session_risk_guard(self, sink: EventSink) -> bool:
        account: Dict[str, Any] = {}
        try:
            account = self.broker.get_account()
        except Exception as exc:
            sink(
                {
                    "event": "autonomous_ceo_session_risk_error",
                    "session_id": self.session_id,
                    "stage": "get_account",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            return False

        risk = self.session_risk_snapshot(account)
        if not risk.get("breached"):
            return False

        sink(
            {
                "event": "autonomous_ceo_session_risk_halt",
                "session_id": self.session_id,
                **risk,
            }
        )
        if self.settings.flatten_on_session_risk_halt:
            self.flatten_day_trader_positions(
                sink,
                reason="session_risk_halt",
            )
        return True

    def session_risk_snapshot(self, account: Dict[str, Any]) -> Dict[str, Any]:
        current_equity = account_equity(account)
        initial_equity = self.session_initial_equity
        if initial_equity is None or initial_equity <= 0 or current_equity <= 0:
            return {
                "initial_equity": initial_equity,
                "current_equity": current_equity,
                "loss_usd": 0.0,
                "drawdown_pct": 0.0,
                "breached": False,
                "breach_reasons": [],
            }

        loss_usd = max(0.0, initial_equity - current_equity)
        drawdown_pct = loss_usd / initial_equity * 100.0
        breach_reasons: List[str] = []
        max_loss = float(self.settings.max_session_loss_usd)
        max_drawdown_pct = float(self.settings.max_session_drawdown_pct)
        if max_loss > 0 and loss_usd >= max_loss:
            breach_reasons.append("max_session_loss_usd")
        if max_drawdown_pct > 0 and drawdown_pct >= max_drawdown_pct:
            breach_reasons.append("max_session_drawdown_pct")

        return {
            "initial_equity": round(initial_equity, 2),
            "current_equity": round(current_equity, 2),
            "loss_usd": round(loss_usd, 2),
            "drawdown_pct": round(drawdown_pct, 3),
            "max_session_loss_usd": max_loss,
            "max_session_drawdown_pct": max_drawdown_pct,
            "breached": bool(breach_reasons),
            "breach_reasons": breach_reasons,
        }

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
            "session_id": self.session_id,
            "cycle": cycle,
            "started_at": self.now_fn().isoformat(),
            "profiles": [],
        }
        cycle_buy_symbols: set[str] = set()
        for profile in self.settings.profiles:
            cooldown_symbols = self.active_cooldown_symbols()
            if event_sink:
                event_sink(
                    {
                        "event": "autonomous_ceo_profile_start",
                        "session_id": self.session_id,
                        "cycle": cycle,
                        "strategy_profile": profile,
                        "stage": "research_strategy_and_trade",
                        "blocked_new_buys": sorted(cycle_buy_symbols | cooldown_symbols),
                    }
                )
            profile_result = self.run_profile(
                profile,
                blocked_new_buys=cycle_buy_symbols | cooldown_symbols,
            )
            payload["profiles"].append(profile_result)
            cycle_buy_symbols.update(
                str(order.get("ticker", "")).upper()
                for order in profile_result.get("orders", [])
                if order.get("submitted") and str(order.get("side", "")).lower() == "buy"
            )
            if event_sink:
                event_sink(profile_stage_summary(cycle, profile_result))
                for order_event in profile_order_events(cycle, profile_result):
                    event_sink(order_event)
        payload["finished_at"] = self.now_fn().isoformat()
        payload["symbol_cooldowns"] = self.active_cooldown_payload()
        return payload

    def run_profile(
        self,
        profile: str,
        *,
        blocked_new_buys: set[str] | None = None,
    ) -> Dict[str, Any]:
        config = self._profile_config(profile)
        if blocked_new_buys:
            config["day_trade_block_new_buys_symbols"] = sorted(blocked_new_buys)
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
            "order_plan_diagnostics": list(
                getattr(runner, "_last_order_plan_diagnostics", [])
            ),
        }

    def monitor_positions_until_next_cycle(
        self, sleep_seconds: int, cycle: int, sink: EventSink
    ) -> bool:
        monitor_seconds = max(1, int(self.settings.position_monitor_seconds))
        deadline = self.now_fn().timestamp() + max(0, sleep_seconds)

        while True:
            if self.handle_stop_request(sink):
                return False
            remaining = deadline - self.now_fn().timestamp()
            if remaining <= 0:
                return True

            sink(self.position_monitor_event(cycle, remaining))
            if self.handle_session_risk_guard(sink):
                return False
            self.sleep_fn(min(monitor_seconds, remaining))

            if self.handle_stop_request(sink):
                return False
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

        event = {
            "event": "autonomous_ceo_position_monitor",
            "cycle": cycle,
            "seconds_to_next_cycle": round(max(0.0, seconds_to_next_cycle), 1),
            "positions_count": len(positions),
            "open_orders_count": len(open_orders),
            "positions": summarize_positions(positions),
            "open_orders": summarize_open_orders(open_orders),
        }
        risk_exits = self.apply_day_trader_exit_policy(positions, open_orders)
        if risk_exits:
            self.apply_risk_exit_cooldowns(risk_exits)
            event["risk_exits"] = risk_exits
        cooldowns = self.active_cooldown_payload()
        if cooldowns:
            event["symbol_cooldowns"] = cooldowns
        return event

    def apply_day_trader_exit_policy(
        self,
        positions: Sequence[Dict[str, Any]],
        open_orders: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not (
            self.settings.protect_intraday_profits
            or self.settings.exit_stale_losers
            or self.settings.exit_momentum_decay
            or self.settings.exit_early_adverse_moves
            or self.settings.exit_unprotected_positions
        ):
            return []

        try:
            clock = self.broker.get_clock()
        except Exception as exc:
            return [
                {
                    "event": "day_trader_exit_policy_error",
                    "stage": "get_clock",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            ]
        if not clock.get("is_open"):
            return []

        open_sell_qty = open_sell_quantity_by_symbol(open_orders)
        current_symbols = {
            str(position.get("symbol", "")).upper()
            for position in positions
            if position.get("symbol")
        }
        self.exit_submitted_symbols.intersection_update(current_symbols)
        for symbol in list(self.unprotected_since):
            if symbol not in current_symbols:
                self.unprotected_since.pop(symbol, None)
        for symbol in list(self.position_highs):
            if symbol not in current_symbols:
                self.position_highs.pop(symbol, None)
        for symbol in list(self.position_seen_at):
            if symbol not in current_symbols:
                self.position_seen_at.pop(symbol, None)

        exits: List[Dict[str, Any]] = []
        now_ts = self.now_fn().timestamp()
        for position in positions:
            symbol = str(position.get("symbol", "")).upper()
            if not symbol or symbol in self.exit_submitted_symbols:
                continue

            qty = abs(safe_float(position.get("qty")))
            current_price = safe_float(position.get("current_price"))
            market_value = abs(safe_float(position.get("market_value")))
            avg_entry = safe_float(position.get("avg_entry_price"))
            unrealized_pl = safe_float(position.get("unrealized_pl"))
            unrealized_plpc = safe_float(position.get("unrealized_plpc"))
            if qty <= 0 or current_price <= 0:
                continue
            if market_value <= 0:
                market_value = qty * current_price

            high = max(self.position_highs.get(symbol, 0.0), current_price, avg_entry)
            self.position_highs[symbol] = high
            first_seen_ts = self.position_seen_at.setdefault(symbol, now_ts)

            exit_event = self._profit_giveback_exit(
                symbol=symbol,
                qty=qty,
                current_price=current_price,
                market_value=market_value,
                avg_entry=avg_entry,
                high=high,
                unrealized_pl=unrealized_pl,
                open_orders=open_orders,
            )
            if exit_event is not None:
                exits.append(exit_event)
                continue

            exit_event = self._early_adverse_exit(
                symbol=symbol,
                qty=qty,
                current_price=current_price,
                market_value=market_value,
                avg_entry=avg_entry,
                high=high,
                unrealized_pl=unrealized_pl,
                unrealized_plpc=unrealized_plpc,
                open_orders=open_orders,
                now_ts=now_ts,
                first_seen_ts=first_seen_ts,
            )
            if exit_event is not None:
                exits.append(exit_event)
                continue

            exit_event = self._stale_loser_exit(
                symbol=symbol,
                qty=qty,
                current_price=current_price,
                market_value=market_value,
                avg_entry=avg_entry,
                unrealized_pl=unrealized_pl,
                unrealized_plpc=unrealized_plpc,
                open_orders=open_orders,
            )
            if exit_event is not None:
                exits.append(exit_event)
                continue

            exit_event = self._momentum_decay_exit(
                symbol=symbol,
                qty=qty,
                current_price=current_price,
                market_value=market_value,
                avg_entry=avg_entry,
                unrealized_pl=unrealized_pl,
                unrealized_plpc=unrealized_plpc,
                open_orders=open_orders,
                now_ts=now_ts,
                first_seen_ts=first_seen_ts,
            )
            if exit_event is not None:
                exits.append(exit_event)
                continue

            exit_event = self._unprotected_position_exit(
                symbol=symbol,
                qty=qty,
                current_price=current_price,
                market_value=market_value,
                protected_qty=open_sell_qty.get(symbol, 0.0),
                now_ts=now_ts,
            )
            if exit_event is not None:
                exits.append(exit_event)

        return exits

    def apply_risk_exit_cooldowns(self, risk_exits: Sequence[Dict[str, Any]]) -> None:
        cooldown_minutes = max(0, int(self.settings.stale_loser_cooldown_minutes))
        if cooldown_minutes <= 0:
            return
        cooldown_until = self.now_fn().timestamp() + cooldown_minutes * 60
        cooldown_iso = datetime.fromtimestamp(cooldown_until, tz=UTC).isoformat()
        for exit_event in risk_exits:
            if not exit_event.get("submitted"):
                continue
            if exit_event.get("reason") not in {
                "stale_loser",
                "momentum_decay",
                "early_adverse_move",
            }:
                continue
            symbol = str(exit_event.get("symbol", "")).upper()
            if not symbol:
                continue
            self.symbol_cooldowns[symbol] = max(
                cooldown_until,
                self.symbol_cooldowns.get(symbol, 0.0),
            )
            exit_event["cooldown_until"] = cooldown_iso

    def active_cooldown_symbols(self) -> set[str]:
        now_ts = self.now_fn().timestamp()
        for symbol in list(self.symbol_cooldowns):
            if self.symbol_cooldowns[symbol] <= now_ts:
                self.symbol_cooldowns.pop(symbol, None)
        return set(self.symbol_cooldowns)

    def active_cooldown_payload(self) -> List[Dict[str, Any]]:
        payload = []
        for symbol in sorted(self.active_cooldown_symbols()):
            payload.append(
                {
                    "symbol": symbol,
                    "cooldown_until": datetime.fromtimestamp(
                        self.symbol_cooldowns[symbol],
                        tz=UTC,
                    ).isoformat(),
                }
            )
        return payload

    def _profit_giveback_exit(
        self,
        *,
        symbol: str,
        qty: float,
        current_price: float,
        market_value: float,
        avg_entry: float,
        high: float,
        unrealized_pl: float,
        open_orders: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        if not self.settings.protect_intraday_profits:
            return None
        if avg_entry <= 0 or high <= avg_entry:
            return None
        if market_value < float(self.settings.profit_protection_min_notional_usd):
            return None
        if unrealized_pl < float(self.settings.profit_protection_min_unrealized_pl_usd):
            return None

        high_gain_pct = (high - avg_entry) / avg_entry * 100.0
        current_gain_pct = (current_price - avg_entry) / avg_entry * 100.0
        giveback_pct = (high - current_price) / high * 100.0 if high > 0 else 0.0
        giveback_fraction = (
            (high - current_price) / (high - avg_entry)
            if high > avg_entry
            else 0.0
        )

        if high_gain_pct < float(self.settings.profit_protection_min_gain_pct):
            return None
        if current_gain_pct < float(
            self.settings.profit_protection_min_remaining_gain_pct
        ):
            return None
        if not (
            giveback_pct >= float(self.settings.profit_protection_max_giveback_pct)
            or giveback_fraction
            >= float(self.settings.profit_protection_max_giveback_fraction)
        ):
            return None

        return self._submit_position_exit(
            symbol=symbol,
            qty=qty,
            current_price=current_price,
            reason="profit_giveback",
            cancel_symbol_orders=True,
            open_orders=open_orders,
            metrics={
                "avg_entry_price": round(avg_entry, 4),
                "high_watermark": round(high, 4),
                "high_gain_pct": round(high_gain_pct, 3),
                "current_gain_pct": round(current_gain_pct, 3),
                "giveback_from_high_pct": round(giveback_pct, 3),
                "giveback_fraction": round(giveback_fraction, 3),
                "unrealized_pl": round(unrealized_pl, 2),
            },
        )

    def _early_adverse_exit(
        self,
        *,
        symbol: str,
        qty: float,
        current_price: float,
        market_value: float,
        avg_entry: float,
        high: float,
        unrealized_pl: float,
        unrealized_plpc: float,
        open_orders: Sequence[Dict[str, Any]],
        now_ts: float,
        first_seen_ts: float,
    ) -> Dict[str, Any] | None:
        if not self.settings.exit_early_adverse_moves:
            return None
        if market_value < float(self.settings.early_adverse_min_notional_usd):
            return None
        if avg_entry <= 0:
            return None

        held_seconds = max(0.0, now_ts - first_seen_ts)
        min_seconds = max(0, int(self.settings.early_adverse_min_minutes)) * 60
        if held_seconds < min_seconds:
            return None

        loss_pct = abs(unrealized_plpc) * 100.0 if unrealized_pl < 0 else 0.0
        if loss_pct <= 0 and current_price < avg_entry:
            loss_pct = (avg_entry - current_price) / avg_entry * 100.0
        high_gain_pct = max(0.0, (high - avg_entry) / avg_entry * 100.0)

        max_loss_pct = float(self.settings.early_adverse_max_loss_pct)
        max_high_gain_pct = float(self.settings.early_adverse_max_high_gain_pct)
        if (
            unrealized_pl >= 0
            or loss_pct < max_loss_pct
            or high_gain_pct > max_high_gain_pct
        ):
            return None

        return self._submit_position_exit(
            symbol=symbol,
            qty=qty,
            current_price=current_price,
            reason="early_adverse_move",
            cancel_symbol_orders=True,
            open_orders=open_orders,
            metrics={
                "avg_entry_price": round(avg_entry, 4),
                "current_price": round(current_price, 4),
                "held_minutes": round(held_seconds / 60.0, 1),
                "min_hold_minutes": int(self.settings.early_adverse_min_minutes),
                "high_gain_pct": round(high_gain_pct, 3),
                "max_high_gain_pct": round(max_high_gain_pct, 3),
                "unrealized_pl": round(unrealized_pl, 2),
                "unrealized_loss_pct": round(loss_pct, 3),
                "max_loss_pct": round(max_loss_pct, 3),
            },
        )

    def _stale_loser_exit(
        self,
        *,
        symbol: str,
        qty: float,
        current_price: float,
        market_value: float,
        avg_entry: float,
        unrealized_pl: float,
        unrealized_plpc: float,
        open_orders: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any] | None:
        if not self.settings.exit_stale_losers:
            return None
        if market_value < float(self.settings.stale_loser_min_notional_usd):
            return None

        loss_pct = abs(unrealized_plpc) * 100.0
        if loss_pct <= 0 and avg_entry > 0 and current_price > 0:
            loss_pct = max(0.0, (avg_entry - current_price) / avg_entry * 100.0)
        if unrealized_pl >= 0 or loss_pct < float(self.settings.stale_loser_max_loss_pct):
            return None

        return self._submit_position_exit(
            symbol=symbol,
            qty=qty,
            current_price=current_price,
            reason="stale_loser",
            cancel_symbol_orders=True,
            open_orders=open_orders,
            metrics={
                "avg_entry_price": round(avg_entry, 4),
                "current_price": round(current_price, 4),
                "unrealized_pl": round(unrealized_pl, 2),
                "unrealized_loss_pct": round(loss_pct, 3),
            },
        )

    def _momentum_decay_exit(
        self,
        *,
        symbol: str,
        qty: float,
        current_price: float,
        market_value: float,
        avg_entry: float,
        unrealized_pl: float,
        unrealized_plpc: float,
        open_orders: Sequence[Dict[str, Any]],
        now_ts: float,
        first_seen_ts: float,
    ) -> Dict[str, Any] | None:
        if not self.settings.exit_momentum_decay:
            return None
        if market_value < float(self.settings.momentum_decay_min_notional_usd):
            return None
        if avg_entry <= 0:
            return None

        held_seconds = max(0.0, now_ts - first_seen_ts)
        min_seconds = max(0, int(self.settings.momentum_decay_min_minutes)) * 60
        if held_seconds < min_seconds:
            return None

        current_gain_pct = (current_price - avg_entry) / avg_entry * 100.0
        loss_pct = abs(unrealized_plpc) * 100.0 if unrealized_pl < 0 else 0.0
        if loss_pct <= 0 and current_price < avg_entry:
            loss_pct = (avg_entry - current_price) / avg_entry * 100.0

        min_gain_pct = float(self.settings.momentum_decay_min_gain_pct)
        max_loss_pct = float(self.settings.momentum_decay_max_loss_pct)
        if current_gain_pct >= min_gain_pct and loss_pct < max_loss_pct:
            return None

        return self._submit_position_exit(
            symbol=symbol,
            qty=qty,
            current_price=current_price,
            reason="momentum_decay",
            cancel_symbol_orders=True,
            open_orders=open_orders,
            metrics={
                "avg_entry_price": round(avg_entry, 4),
                "current_price": round(current_price, 4),
                "held_minutes": round(held_seconds / 60.0, 1),
                "min_hold_minutes": int(self.settings.momentum_decay_min_minutes),
                "current_gain_pct": round(current_gain_pct, 3),
                "min_gain_pct": round(min_gain_pct, 3),
                "unrealized_pl": round(unrealized_pl, 2),
                "unrealized_loss_pct": round(max(0.0, loss_pct), 3),
                "max_loss_pct": round(max_loss_pct, 3),
            },
        )

    def _unprotected_position_exit(
        self,
        *,
        symbol: str,
        qty: float,
        current_price: float,
        market_value: float,
        protected_qty: float,
        now_ts: float,
    ) -> Dict[str, Any] | None:
        if not self.settings.exit_unprotected_positions:
            self.unprotected_since.pop(symbol, None)
            return None
        threshold = max(0.0, min(1.0, float(self.settings.open_sell_coverage_threshold)))
        protected_fraction = protected_qty / qty if qty > 0 else 0.0
        if protected_fraction >= threshold:
            self.unprotected_since.pop(symbol, None)
            return None

        unprotected_qty = max(0.0, qty - protected_qty)
        if unprotected_qty <= 0:
            return None
        unprotected_notional = unprotected_qty * current_price
        if unprotected_notional < float(self.settings.profit_protection_min_notional_usd):
            return None

        first_seen = self.unprotected_since.setdefault(symbol, now_ts)
        grace = max(0, int(self.settings.unprotected_position_grace_seconds))
        unprotected_seconds = now_ts - first_seen
        if unprotected_seconds < grace:
            return None

        reason = "unprotected_position" if protected_qty <= 0 else "unprotected_remainder"
        return self._submit_position_exit(
            symbol=symbol,
            qty=unprotected_qty if protected_qty > 0 else qty,
            current_price=current_price,
            reason=reason,
            cancel_symbol_orders=False,
            open_orders=[],
            metrics={
                "position_qty": round(qty, 4),
                "protected_qty": round(protected_qty, 4),
                "protected_fraction": round(protected_fraction, 3),
                "unprotected_seconds": round(unprotected_seconds, 1),
            },
        )

    def _submit_position_exit(
        self,
        *,
        symbol: str,
        qty: float,
        current_price: float,
        reason: str,
        cancel_symbol_orders: bool,
        open_orders: Sequence[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        exit_qty = floor_quantity(qty)
        if exit_qty <= 0:
            return {
                "event": "day_trader_position_exit_skipped",
                "symbol": symbol,
                "reason": reason,
                "blocked_reason": "quantity_too_small",
                **metrics,
            }

        cancel_events: List[Dict[str, Any]] = []
        if cancel_symbol_orders:
            cancel_events = self._cancel_symbol_open_orders(symbol, open_orders)

        intent = OrderIntent(ticker=symbol, side="sell", quantity=exit_qty)
        event: Dict[str, Any] = {
            "event": "day_trader_position_exit_submitted",
            "symbol": symbol,
            "side": "sell",
            "quantity": exit_qty,
            "estimated_notional_usd": round(exit_qty * current_price, 2),
            "reason": reason,
            "cancelled_orders": cancel_events,
            **metrics,
        }
        try:
            response = self.broker.submit_order(intent)
            self.exit_submitted_symbols.add(symbol)
            self.unprotected_since.pop(symbol, None)
            self.position_seen_at.pop(symbol, None)
            event["submitted"] = True
            event["order_response"] = response
        except Exception as exc:
            event["submitted"] = False
            event["blocked_reason"] = f"submit_failed_{type(exc).__name__}"
            event["error"] = str(exc)
        return event

    def _cancel_symbol_open_orders(
        self,
        symbol: str,
        open_orders: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        cancel_order = getattr(self.broker, "cancel_order", None)
        if not callable(cancel_order):
            return [
                {
                    "symbol": symbol,
                    "status": "not_cancelled",
                    "reason": "broker_cancel_order_unavailable",
                }
            ]

        events = []
        for order in open_orders:
            if str(order.get("symbol", "")).upper() != symbol:
                continue
            order_id = order.get("id")
            if not order_id:
                continue
            try:
                response = cancel_order(str(order_id))
                events.append(
                    {
                        "id": str(order_id),
                        "symbol": symbol,
                        "status": "cancel_requested",
                        "response": response,
                    }
                )
            except Exception as exc:
                events.append(
                    {
                        "id": str(order_id),
                        "symbol": symbol,
                        "status": "cancel_failed",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
        return events

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
            config["portfolio_max_active_positions"] = self.settings.target_positions
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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def account_equity(account: Dict[str, Any]) -> float:
    for key in ("equity", "portfolio_value", "last_equity"):
        value = safe_float(account.get(key))
        if value > 0:
            return value
    return 0.0


def floor_quantity(value: float, precision: int = 4) -> float:
    factor = 10**precision
    return math.floor(max(0.0, float(value)) * factor) / factor


def open_sell_quantity_by_symbol(
    orders: Sequence[Dict[str, Any]],
) -> Dict[str, float]:
    quantities: Dict[str, float] = {}
    open_like_statuses = {"accepted", "new", "pending_new", "partially_filled", "held"}
    for order in orders:
        symbol = str(order.get("symbol", "")).upper()
        if not symbol:
            continue
        candidates = order.get("legs") or [order]
        sell_quantities = []
        for candidate in candidates:
            side = str(candidate.get("side", "")).lower()
            status = str(candidate.get("status", "")).lower()
            if side == "sell" and status in open_like_statuses:
                sell_quantities.append(
                    max(
                        0.0,
                        safe_float(candidate.get("qty"))
                        - safe_float(candidate.get("filled_qty")),
                    )
                )
        if sell_quantities:
            quantities[symbol] = quantities.get(symbol, 0.0) + max(sell_quantities)
    return quantities


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
