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
    parser.add_argument(
        "--stop-file",
        default=None,
        help=(
            "Optional stop-request file. Defaults to "
            "<results-dir>/control/stop_requested.json."
        ),
    )
    parser.add_argument("--max-cycles", type=int, default=0)
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
    parser.add_argument("--news-query", action="append", default=[])
    parser.add_argument(
        "--alpaca-stock-feed",
        choices=["iex", "sip", "delayed_sip", "boats", "overnight", "otc"],
        default=None,
    )
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
        stop_file=args.stop_file,
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


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env", override=True)
    args = build_parser().parse_args(argv)
    return AutonomousPaperCEOAgent(settings_from_args(args)).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
