from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_launcher_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "run_day_trader_bot.py"
    spec = importlib.util.spec_from_file_location("run_day_trader_bot", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_vs_code_launcher_defaults_run_full_bot_until_close():
    launcher = _load_launcher_module()
    args = launcher.build_parser().parse_args([])
    settings = launcher.settings_from_args(args)

    assert args.universe == launcher.DEFAULT_UNIVERSE
    assert settings.profiles == ["safe", "risky"]
    assert settings.run_until_close is True
    assert settings.once is False
    assert settings.interval_seconds == launcher.DEFAULT_INTERVAL_SECONDS
    assert settings.position_monitor_seconds == launcher.DEFAULT_POSITION_MONITOR_SECONDS
    assert settings.flatten_at_close is True
    assert settings.flatten_minutes_before_close == 5
    assert settings.stop_new_entries_minutes_before_close == 15
    assert settings.protect_intraday_profits is True
    assert settings.profit_protection_min_gain_pct == 0.50
    assert settings.profit_protection_max_giveback_pct == 0.45
    assert settings.profit_protection_max_giveback_fraction == 0.40
    assert settings.exit_momentum_decay is True
    assert settings.momentum_decay_min_minutes == 20
    assert settings.momentum_decay_min_gain_pct == 0.15
    assert settings.momentum_decay_max_loss_pct == 0.30
    assert settings.exit_early_adverse_moves is True
    assert settings.early_adverse_min_minutes == 5
    assert settings.early_adverse_max_loss_pct == 0.30
    assert settings.early_adverse_max_high_gain_pct == 0.15
    assert settings.exit_unprotected_positions is True
    assert settings.stale_loser_cooldown_minutes == 30
    assert settings.max_session_loss_usd == 750.0
    assert settings.max_session_drawdown_pct == 1.0
    assert settings.flatten_on_session_risk_halt is True
    assert settings.premarket_research_enabled is True
    assert settings.stop_file is None
    assert "QQQ" in settings.universe
    assert "SPY" in settings.universe
    assert "UUP" in settings.universe
    assert settings.results_dir == str(
        launcher.REPO_ROOT / launcher.DEFAULT_RESULTS_DIR
    )


def test_vs_code_launcher_once_mode_only_runs_one_cycle():
    launcher = _load_launcher_module()
    args = launcher.build_parser().parse_args(
        ["--once", "--strategy", "safe", "--universe", "SPY, QQQ"]
    )
    settings = launcher.settings_from_args(args)

    assert settings.profiles == ["safe"]
    assert settings.universe == ["SPY", "QQQ"]
    assert settings.run_until_close is False
    assert settings.once is True


def test_vs_code_launcher_terminal_messages_are_plain_english():
    launcher = _load_launcher_module()
    message = launcher.terminal_message(
        {
            "event": "autonomous_ceo_profile_complete",
            "strategy_profile": "safe",
            "top_candidates": ["SPY", "QQQ", "NVDA"],
            "target_weights": {"SPY": 0.08},
            "submitted_orders": 1,
            "blocked_orders": 0,
        }
    )

    assert "safe desk finished" in message
    assert "Top live candidates: SPY, QQQ, NVDA" in message
    assert "Submitted 1 order" in message


def test_vs_code_launcher_terminal_message_mentions_live_monitor():
    launcher = _load_launcher_module()
    message = launcher.terminal_message(
        {
            "event": "autonomous_ceo_position_monitor",
            "positions_count": 1,
            "open_orders_count": 2,
            "positions": [{"symbol": "NVDA"}],
            "seconds_to_next_cycle": 5.0,
        }
    )

    assert "Monitoring live risk" in message
    assert "NVDA" in message
    assert "Next full strategy scan in 5.0s" in message


def test_vs_code_launcher_terminal_message_mentions_profit_exit():
    launcher = _load_launcher_module()
    message = launcher.terminal_message(
        {
            "event": "autonomous_ceo_position_monitor",
            "positions_count": 1,
            "open_orders_count": 1,
            "positions": [{"symbol": "NVDA"}],
            "seconds_to_next_cycle": 5.0,
            "risk_exits": [
                {
                    "symbol": "NVDA",
                    "reason": "profit_giveback",
                    "submitted": True,
                }
            ],
        }
    )

    assert "Risk monitor submitted exits: NVDA (profit_giveback)" in message


def test_vs_code_launcher_terminal_message_mentions_manual_stop():
    launcher = _load_launcher_module()
    message = launcher.terminal_message(
        {
            "event": "manual_stop_request_completed",
            "action": "flatten",
            "reason": "end session",
        }
    )

    assert "Manual stop completed" in message
    assert "flatten" in message


def test_vs_code_launcher_terminal_message_mentions_session_lifecycle():
    launcher = _load_launcher_module()
    start = launcher.terminal_message(
        {
            "event": "autonomous_ceo_session_start",
            "session_id": "daytrader_20260506T133000Z",
            "initial_equity": 100000,
            "positions_count": 2,
            "open_orders_count": 3,
        }
    )
    end = launcher.terminal_message(
        {
            "event": "autonomous_ceo_session_end",
            "session_id": "daytrader_20260506T133000Z",
            "cycles_completed": 7,
            "final_equity": 100050,
            "session_risk": {"loss_usd": 0, "drawdown_pct": 0},
        }
    )

    assert "Trading session daytrader_20260506T133000Z started" in start
    assert "Initial equity: $100000.00" in start
    assert "ended after 7 cycle" in end
    assert "Final equity: $100050.00" in end


def test_vs_code_launcher_terminal_message_mentions_session_risk_halt():
    launcher = _load_launcher_module()
    message = launcher.terminal_message(
        {
            "event": "autonomous_ceo_session_risk_halt",
            "breach_reasons": ["max_session_loss_usd"],
            "loss_usd": 760,
            "drawdown_pct": 0.76,
        }
    )

    assert "Session risk halt triggered" in message
    assert "max_session_loss_usd" in message
    assert "$760.00" in message
