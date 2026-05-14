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


DEFAULT_UNIVERSE = ",".join(
    [
        "AMD",
        "NVDA",
        "INTC",
        "COIN",
        "QQQ",
        "SPY",
        "PLTR",
        "MU",
        "TSLA",
        "HOOD",
        "AAPL",
        "MSFT",
        "META",
        "AMZN",
        "GOOGL",
        "AVGO",
        "ARM",
        "SMCI",
        "CRWD",
        "PANW",
        "JPM",
        "BAC",
        "GS",
        "XLF",
        "LLY",
        "NVO",
        "UNH",
        "XLV",
        "XOM",
        "CVX",
        "XLE",
        "LMT",
        "NOC",
        "RTX",
        "ITA",
        "TLT",
        "GLD",
        "UUP",
        "FXE",
        "FXY",
        "FXB",
        "FXA",
        "FXC",
        "IWM",
        "SOXX",
        "IBIT",
    ]
)
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
    parser.add_argument(
        "--stop-file",
        default=None,
        help=(
            "Optional stop-request file. Defaults to "
            "<results-dir>/control/stop_requested.json."
        ),
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--max-wait-open-seconds", type=int, default=43200)
    parser.add_argument("--max-deploy-usd", type=float, default=None)
    parser.add_argument("--max-order-notional-usd", type=float, default=None)
    parser.add_argument("--target-positions", type=int, default=None)
    parser.add_argument("--liquidate-non-targets", action="store_true")
    parser.add_argument("--with-staff-memo", action="store_true")
    parser.add_argument("--with-tech-scout", action="store_true")
    parser.add_argument("--disable-flatten-at-close", action="store_true")
    parser.add_argument("--flatten-minutes-before-close", type=int, default=5)
    parser.add_argument("--stop-new-entries-minutes-before-close", type=int, default=15)
    parser.add_argument("--no-flatten-on-max-cycles", action="store_true")
    parser.add_argument("--disable-profit-protection", action="store_true")
    parser.add_argument("--profit-protection-min-gain-pct", type=float, default=0.50)
    parser.add_argument("--profit-protection-max-giveback-pct", type=float, default=0.45)
    parser.add_argument("--profit-protection-max-giveback-fraction", type=float, default=0.40)
    parser.add_argument("--disable-momentum-decay-exit", action="store_true")
    parser.add_argument("--momentum-decay-min-minutes", type=int, default=20)
    parser.add_argument("--momentum-decay-min-gain-pct", type=float, default=0.15)
    parser.add_argument("--momentum-decay-max-loss-pct", type=float, default=0.30)
    parser.add_argument("--disable-early-adverse-exit", action="store_true")
    parser.add_argument("--early-adverse-min-minutes", type=int, default=5)
    parser.add_argument("--early-adverse-max-loss-pct", type=float, default=0.30)
    parser.add_argument("--early-adverse-max-high-gain-pct", type=float, default=0.15)
    parser.add_argument("--disable-stale-loser-exit", action="store_true")
    parser.add_argument("--stale-loser-max-loss-pct", type=float, default=0.75)
    parser.add_argument("--stale-loser-cooldown-minutes", type=int, default=30)
    parser.add_argument("--disable-unprotected-position-exit", action="store_true")
    parser.add_argument("--unprotected-position-grace-seconds", type=int, default=60)
    parser.add_argument("--max-session-loss-usd", type=float, default=750.0)
    parser.add_argument("--max-session-drawdown-pct", type=float, default=1.0)
    parser.add_argument("--disable-session-risk-flatten", action="store_true")
    parser.add_argument("--disable-news-politics", action="store_true")
    parser.add_argument("--disable-premarket-research", action="store_true")
    parser.add_argument("--news-max-symbols", type=int, default=None)
    parser.add_argument(
        "--news-query",
        action="append",
        default=[],
        help="Additional news/policy query. Can be passed more than once.",
    )
    parser.add_argument(
        "--alpaca-stock-feed",
        choices=["iex", "sip", "delayed_sip", "boats", "overnight", "otc"],
        default=None,
        help="Override ALPACA_STOCK_FEED for this run.",
    )
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
        stop_file=str(resolve_repo_path(args.stop_file)) if args.stop_file else None,
        max_deploy_usd=args.max_deploy_usd,
        max_order_notional_usd=args.max_order_notional_usd,
        target_positions=args.target_positions,
        liquidate_non_targets=bool(args.liquidate_non_targets),
        ollama_staff_memo_enabled=bool(args.with_staff_memo),
        technology_scout_enabled=bool(args.with_tech_scout),
        news_politics_scan_enabled=not bool(args.disable_news_politics),
        news_politics_max_symbols=args.news_max_symbols,
        news_politics_queries=tuple(args.news_query or []),
        premarket_research_enabled=not bool(args.disable_premarket_research),
        alpaca_stock_feed=args.alpaca_stock_feed,
        flatten_at_close=not bool(args.disable_flatten_at_close),
        flatten_minutes_before_close=args.flatten_minutes_before_close,
        stop_new_entries_minutes_before_close=args.stop_new_entries_minutes_before_close,
        flatten_on_max_cycles=not bool(args.no_flatten_on_max_cycles),
        protect_intraday_profits=not bool(args.disable_profit_protection),
        profit_protection_min_gain_pct=args.profit_protection_min_gain_pct,
        profit_protection_max_giveback_pct=args.profit_protection_max_giveback_pct,
        profit_protection_max_giveback_fraction=args.profit_protection_max_giveback_fraction,
        exit_momentum_decay=not bool(args.disable_momentum_decay_exit),
        momentum_decay_min_minutes=args.momentum_decay_min_minutes,
        momentum_decay_min_gain_pct=args.momentum_decay_min_gain_pct,
        momentum_decay_max_loss_pct=args.momentum_decay_max_loss_pct,
        exit_early_adverse_moves=not bool(args.disable_early_adverse_exit),
        early_adverse_min_minutes=args.early_adverse_min_minutes,
        early_adverse_max_loss_pct=args.early_adverse_max_loss_pct,
        early_adverse_max_high_gain_pct=args.early_adverse_max_high_gain_pct,
        exit_stale_losers=not bool(args.disable_stale_loser_exit),
        stale_loser_max_loss_pct=args.stale_loser_max_loss_pct,
        stale_loser_cooldown_minutes=args.stale_loser_cooldown_minutes,
        exit_unprotected_positions=not bool(args.disable_unprotected_position_exit),
        unprotected_position_grace_seconds=args.unprotected_position_grace_seconds,
        max_session_loss_usd=args.max_session_loss_usd,
        max_session_drawdown_pct=args.max_session_drawdown_pct,
        flatten_on_session_risk_halt=not bool(args.disable_session_risk_flatten),
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
            f"News/policy expansion: {settings.get('news_politics_scan_enabled')}. "
            f"Pre-open research: {settings.get('premarket_research_enabled')}. "
            f"Flatten before close: {settings.get('flatten_at_close')}. "
            f"Stop file: {settings.get('stop_file') or 'default control file'}. "
            f"Log: {payload.get('log_file')}."
        )
    if event == "autonomous_ceo_session_start":
        return (
            f"Trading session {payload.get('session_id')} started. "
            f"Initial equity: ${float(payload.get('initial_equity') or 0):.2f}. "
            f"Positions: {payload.get('positions_count', 0)}, "
            f"open orders: {payload.get('open_orders_count', 0)}."
        )
    if event == "autonomous_ceo_session_end":
        risk = payload.get("session_risk", {})
        return (
            f"Trading session {payload.get('session_id')} ended after "
            f"{payload.get('cycles_completed', 0)} cycle(s). "
            f"Final equity: ${float(payload.get('final_equity') or 0):.2f}. "
            f"Session loss: ${float(risk.get('loss_usd') or 0):.2f} "
            f"({float(risk.get('drawdown_pct') or 0):.3f}%)."
        )
    if event == "autonomous_ceo_session_risk_halt":
        reasons = ", ".join(payload.get("breach_reasons", [])) or "session risk limit"
        return (
            "Session risk halt triggered. "
            f"Reason: {reasons}. "
            f"Loss: ${float(payload.get('loss_usd') or 0):.2f}, "
            f"drawdown {float(payload.get('drawdown_pct') or 0):.3f}%."
        )
    if event == "manual_stop_request_received":
        action = payload.get("action")
        return (
            "Manual stop requested. "
            f"Action: {action}. Reason: {payload.get('reason')}."
        )
    if event == "manual_stop_request_file_removed":
        return "Manual stop request acknowledged and cleared."
    if event == "manual_stop_request_file_remove_error":
        return (
            "Manual stop request was read, but I could not clear the control file. "
            f"{payload.get('error_type')}: {payload.get('error')}."
        )
    if event == "manual_stop_request_completed":
        return (
            "Manual stop completed. "
            f"Action: {payload.get('action')}. CEO is standing down cleanly."
        )
    if event == "premarket_research_complete":
        top = ", ".join(payload.get("top_candidates", [])[:5]) or "none"
        queue = payload.get("research_queue", [])
        queue_text = ", ".join(
            str(item.get("symbol"))
            for item in queue[:5]
            if isinstance(item, dict) and item.get("symbol")
        ) or "none"
        return (
            "Pre-open research complete. "
            f"Research queue: {queue_text}. Top candidates: {top}. "
            f"Briefing: {payload.get('artifact_dir')}."
        )
    if event == "premarket_research_error":
        return (
            "Pre-open research failed, so I will continue with the base universe. "
            f"{payload.get('error_type')}: {payload.get('error')}."
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
            "I am checking price, volume, momentum, spread, news/policy catalysts, "
            "and risk gates quickly."
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
    if event == "autonomous_ceo_no_new_entries_window":
        return (
            "Close-risk window is active. I am not opening new trades now; "
            f"market close is in {payload.get('seconds_to_close')}s and "
            f"flattening starts in {payload.get('wait_seconds')}s."
        )
    if event == "autonomous_ceo_eod_flatten_start":
        return (
            "End-of-day flatten is starting. I am cancelling open orders and "
            f"liquidating {payload.get('positions_count', 0)} position(s) "
            f"because {payload.get('reason')}."
        )
    if event == "autonomous_ceo_eod_flatten_complete":
        return (
            "End-of-day flatten request completed in Alpaca paper. "
            f"Reason: {payload.get('reason')}."
        )
    if event == "autonomous_ceo_eod_flatten_skipped":
        return "End-of-day flatten checked the account; there were no positions or open orders."
    if event == "autonomous_ceo_eod_flatten_error":
        return (
            "End-of-day flatten failed. "
            f"{payload.get('stage')}: {payload.get('error_type')}: {payload.get('error')}."
        )
    if event == "autonomous_ceo_position_monitor":
        positions_count = payload.get("positions_count", 0)
        open_orders_count = payload.get("open_orders_count", 0)
        exits = payload.get("risk_exits", [])
        exit_text = ""
        if exits:
            submitted = [
                f"{exit_event.get('symbol')} ({exit_event.get('reason')})"
                for exit_event in exits
                if exit_event.get("submitted")
            ]
            if submitted:
                exit_text = f" Risk monitor submitted exits: {', '.join(submitted)}."
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
                f"{exit_text}"
            )
        return (
            "Monitoring live risk. No open positions right now. "
            f"Open orders/brackets: {open_orders_count}. "
            f"Next full strategy scan in {payload.get('seconds_to_next_cycle')}s."
            f"{exit_text}"
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
