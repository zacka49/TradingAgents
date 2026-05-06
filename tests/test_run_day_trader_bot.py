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
