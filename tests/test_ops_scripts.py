"""Tests for the scheduled operations layer (scripts/ops).

These scripts are the fix for the 2026-06-04 to 2026-07-08 deadlock: nothing
ran the CEO cycle on a schedule, so a stale book blocked the day trader
indefinitely. The weekly circuit breaker and heartbeat logic here are the
parts with real conditional behavior worth protecting.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ops"))

import opslib  # noqa: E402
from check_ollama_health import check_ollama_health  # noqa: E402
from digest import DigestInputs, build_daily_digest  # noqa: E402
import trading_session  # noqa: E402


def _write_session(
    results_dir: Path, session_id: str, *, initial_equity: float, final_equity: float
) -> None:
    reports_dir = results_dir / "session_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "session": {
            "session_id": session_id,
            "initial_equity": initial_equity,
            "final_equity": final_equity,
            "cycles_completed": 3,
            "positions_count": 2,
            "open_orders_count": 0,
        }
    }
    (reports_dir / f"{session_id}_final.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.unit
class TestHeartbeat:
    def test_round_trip(self, tmp_path):
        opslib.write_heartbeat("T1_premarket", "ok", trade_date="2026-07-20", results_dir=tmp_path)
        loaded = opslib.read_heartbeat("T1_premarket", "2026-07-20", results_dir=tmp_path)
        assert loaded["status"] == "ok"
        assert loaded["task"] == "T1_premarket"

    def test_missing_heartbeat_returns_none(self, tmp_path):
        assert opslib.read_heartbeat("T1_premarket", "2026-01-01", results_dir=tmp_path) is None


@pytest.mark.unit
class TestWeekHelpers:
    def test_week_start_is_monday(self):
        # 2026-07-18 is a Saturday; the ISO week it belongs to starts Monday 2026-07-13.
        assert opslib.week_start(date(2026, 7, 18)) == date(2026, 7, 13)

    def test_trading_days_in_week_is_mon_to_fri(self):
        days = opslib.trading_days_in_week(date(2026, 7, 18))
        assert days == [
            "2026-07-13",
            "2026-07-14",
            "2026-07-15",
            "2026-07-16",
            "2026-07-17",
        ]


@pytest.mark.unit
class TestWeeklyCircuitBreaker:
    def test_no_sessions_is_not_breached(self, tmp_path):
        status = opslib.weekly_circuit_breaker_status(as_of=date(2026, 7, 18), results_dir=tmp_path)
        assert status.breached is False
        assert status.sessions_counted == 0

    def test_small_loss_within_limit_not_breached(self, tmp_path):
        _write_session(tmp_path, "daytrader_20260713T140000Z", initial_equity=100000, final_equity=99500)
        status = opslib.weekly_circuit_breaker_status(
            as_of=date(2026, 7, 18), results_dir=tmp_path, weekly_loss_limit_pct=1.5
        )
        assert status.breached is False
        assert status.cumulative_pnl_usd == -500.0

    def test_loss_beyond_limit_is_breached(self, tmp_path):
        _write_session(tmp_path, "daytrader_20260713T140000Z", initial_equity=100000, final_equity=98000)
        status = opslib.weekly_circuit_breaker_status(
            as_of=date(2026, 7, 18), results_dir=tmp_path, weekly_loss_limit_pct=1.5
        )
        assert status.breached is True
        assert "breaches" in status.reason

    def test_gains_never_breach(self, tmp_path):
        _write_session(tmp_path, "daytrader_20260713T140000Z", initial_equity=100000, final_equity=105000)
        status = opslib.weekly_circuit_breaker_status(as_of=date(2026, 7, 18), results_dir=tmp_path)
        assert status.breached is False

    def test_sums_across_multiple_sessions_in_the_week(self, tmp_path):
        _write_session(tmp_path, "daytrader_20260713T140000Z", initial_equity=100000, final_equity=99800)
        _write_session(tmp_path, "daytrader_20260714T140000Z", initial_equity=99800, final_equity=99400)
        status = opslib.weekly_circuit_breaker_status(as_of=date(2026, 7, 18), results_dir=tmp_path)
        assert status.sessions_counted == 2
        assert status.cumulative_pnl_usd == -600.0

    def test_sessions_outside_the_week_are_excluded(self, tmp_path):
        # Prior week's Friday (2026-07-10) must not count toward this week.
        _write_session(tmp_path, "daytrader_20260710T140000Z", initial_equity=100000, final_equity=50000)
        status = opslib.weekly_circuit_breaker_status(as_of=date(2026, 7, 18), results_dir=tmp_path)
        assert status.sessions_counted == 0
        assert status.breached is False


@pytest.mark.unit
class TestWeeklyPnlBreakdown:
    def test_breaks_down_by_day(self, tmp_path):
        _write_session(tmp_path, "daytrader_20260713T140000Z", initial_equity=100000, final_equity=100100)
        _write_session(tmp_path, "daytrader_20260714T140000Z", initial_equity=100100, final_equity=99900)
        rows = opslib.weekly_pnl_breakdown(as_of=date(2026, 7, 18), results_dir=tmp_path)
        by_date = {row["date"]: row for row in rows}
        assert by_date["2026-07-13"]["pnl_usd"] == 100.0
        assert by_date["2026-07-14"]["pnl_usd"] == -200.0
        assert by_date["2026-07-15"]["sessions"] == 0


@pytest.mark.unit
class TestStrategyLibraryFreshness:
    def test_missing_report_is_stale(self, tmp_path):
        result = opslib.strategy_library_freshness(tmp_path / "does_not_exist.md")
        assert result["stale"] is True
        assert result["present"] is False

    def test_recent_report_is_fresh(self, tmp_path):
        report = tmp_path / "strategy_research_report.md"
        report.write_text(f"# Report\n\n- Generated: {opslib.utc_now().isoformat()}\n", encoding="utf-8")
        result = opslib.strategy_library_freshness(report, max_age_days=7)
        assert result["stale"] is False

    def test_old_report_is_stale(self, tmp_path):
        from datetime import timedelta

        old = opslib.utc_now() - timedelta(days=20)
        report = tmp_path / "strategy_research_report.md"
        report.write_text(f"# Report\n\n- Generated: {old.isoformat()}\n", encoding="utf-8")
        result = opslib.strategy_library_freshness(report, max_age_days=7)
        assert result["stale"] is True


@pytest.mark.unit
class TestOllamaHealthCheck:
    def test_unreachable_server_is_error(self, monkeypatch):
        import check_ollama_health as mod

        monkeypatch.setattr(mod, "list_local_ollama_models", lambda base_url, timeout_seconds=2.0: [])
        monkeypatch.setattr(mod, "_server_responds", lambda base_url: False)
        report = check_ollama_health({"quick_think_llm": "qwen3:0.6b", "deep_think_llm": "qwen3:0.6b"})
        assert report["status"] == "error"
        assert report["reachable"] is False

    def test_reachable_but_missing_model_is_degraded(self, monkeypatch):
        import check_ollama_health as mod

        monkeypatch.setattr(
            mod, "list_local_ollama_models", lambda base_url, timeout_seconds=2.0: ["llama3.2:latest"]
        )
        report = check_ollama_health({"quick_think_llm": "qwen3:0.6b", "deep_think_llm": "qwen3:0.6b"})
        assert report["status"] == "degraded"
        assert report["reachable"] is True

    def test_reachable_with_configured_models_is_ok(self, monkeypatch):
        import check_ollama_health as mod

        monkeypatch.setattr(
            mod, "list_local_ollama_models", lambda base_url, timeout_seconds=2.0: ["qwen3:0.6b"]
        )
        report = check_ollama_health({"quick_think_llm": "qwen3:0.6b", "deep_think_llm": "qwen3:0.6b"})
        assert report["status"] == "ok"


@pytest.mark.unit
class TestDailyDigest:
    def _inputs(self, **overrides) -> DigestInputs:
        defaults = dict(
            trade_date="2026-07-20",
            premarket={"ready_for_trading": True},
            t1_heartbeat={"status": "ok"},
            t2_heartbeat={"status": "ok", "details": {}},
            day_trader_sessions=[],
            ceo_summary={"market_open": True, "top_candidates": ["AAPL"], "blocked_orders": []},
            ceo_error=None,
            post_market_review={"average_score": 80, "scorecards": []},
            post_market_error=None,
            strategy_library={"stale": False},
        )
        defaults.update(overrides)
        return DigestInputs(**defaults)

    def test_missing_t2_heartbeat_is_flagged(self):
        inputs = self._inputs(t2_heartbeat=None)
        markdown = build_daily_digest(inputs)
        assert "T2 trading session did not run today" in markdown

    def test_stale_library_is_flagged(self):
        inputs = self._inputs(strategy_library={"stale": True})
        markdown = build_daily_digest(inputs)
        assert "Strategy library is stale" in markdown

    def test_low_scorecard_grade_is_flagged(self):
        inputs = self._inputs(
            post_market_review={
                "average_score": 55,
                "scorecards": [{"agent": "Risk Officer", "score": 40, "grade": "F", "gaps": ["no data"]}],
            }
        )
        markdown = build_daily_digest(inputs)
        assert "Risk Officer scored F" in markdown

    def test_circuit_breaker_breach_is_flagged(self):
        inputs = self._inputs(
            t2_heartbeat={
                "status": "skipped",
                "details": {
                    "reason": "weekly_circuit_breaker_breached",
                    "circuit_breaker": {"breached": True, "cumulative_pnl_pct": -2.1, "sessions_counted": 3},
                },
            }
        )
        markdown = build_daily_digest(inputs)
        assert "circuit breaker is BREACHED" in markdown

    def test_clean_week_has_nothing_flagged(self):
        inputs = self._inputs()
        markdown = build_daily_digest(inputs)
        assert "Nothing flagged." in markdown


@pytest.mark.unit
class TestTradingSessionCommand:
    def test_command_matches_approved_risk_policy(self):
        command = trading_session.build_day_trader_command(
            python_exe="python.exe",
            results_dir="results/autonomous_day_trader",
            max_deploy_usd=15000.0,
            max_order_notional_usd=3000.0,
            target_positions=4,
            max_session_loss_usd=500.0,
            max_session_drawdown_pct=0.5,
        )
        assert "--strategy" in command and command[command.index("--strategy") + 1] == "safe"
        assert "--flatten-existing-at-start" in command
        assert "--run-until-close" in command
        assert command[command.index("--max-deploy-usd") + 1] == "15000.0"
        assert command[command.index("--max-session-loss-usd") + 1] == "500.0"

    def test_breached_circuit_breaker_skips_without_launching_subprocess(self, tmp_path, monkeypatch):
        fake_status = opslib.CircuitBreakerStatus(
            breached=True,
            week_start="2026-07-13",
            sessions_counted=3,
            baseline_equity=100000.0,
            cumulative_pnl_usd=-2000.0,
            cumulative_pnl_pct=-2.0,
            reason="weekly loss -2.00% breaches -1.50% limit",
        )
        monkeypatch.setattr(trading_session, "weekly_circuit_breaker_status", lambda **kwargs: fake_status)

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("subprocess.run should not be called when the breaker is breached")

        monkeypatch.setattr(trading_session.subprocess, "run", _fail_if_called)

        report = trading_session.run_trading_session(
            ops_results_dir=str(tmp_path / "ops"),
            day_trader_results_dir=str(tmp_path / "dt"),
            trade_date="2026-07-20",
            weekly_loss_limit_pct=1.5,
            max_deploy_usd=15000.0,
            max_order_notional_usd=3000.0,
            target_positions=4,
            max_session_loss_usd=500.0,
            max_session_drawdown_pct=0.5,
            require_premarket_ready=False,
        )
        assert report["status"] == "skipped"
        assert report["reason"] == "weekly_circuit_breaker_breached"

    def test_dry_run_reports_command_without_launching(self, tmp_path, monkeypatch):
        fake_status = opslib.CircuitBreakerStatus(
            breached=False,
            week_start="2026-07-13",
            sessions_counted=0,
            baseline_equity=None,
            cumulative_pnl_usd=0.0,
            cumulative_pnl_pct=0.0,
            reason="no_sessions_recorded_this_week",
        )
        monkeypatch.setattr(trading_session, "weekly_circuit_breaker_status", lambda **kwargs: fake_status)

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("subprocess.run should not be called on a dry run")

        monkeypatch.setattr(trading_session.subprocess, "run", _fail_if_called)

        report = trading_session.run_trading_session(
            ops_results_dir=str(tmp_path / "ops"),
            day_trader_results_dir=str(tmp_path / "dt"),
            trade_date="2026-07-20",
            weekly_loss_limit_pct=1.5,
            max_deploy_usd=15000.0,
            max_order_notional_usd=3000.0,
            target_positions=4,
            max_session_loss_usd=500.0,
            max_session_drawdown_pct=0.5,
            dry_run=True,
            require_premarket_ready=False,
        )
        assert report["status"] == "skipped"
        assert report["reason"] == "dry_run"
        assert "--flatten-existing-at-start" in report["command"]

    def test_missing_premarket_status_skips_before_circuit_breaker(self, tmp_path, monkeypatch):
        def _fail_if_called(**kwargs):
            raise AssertionError("circuit breaker should not be checked before the premarket gate")

        monkeypatch.setattr(trading_session, "weekly_circuit_breaker_status", _fail_if_called)

        report = trading_session.run_trading_session(
            ops_results_dir=str(tmp_path / "ops"),
            day_trader_results_dir=str(tmp_path / "dt"),
            trade_date="2026-07-20",
            weekly_loss_limit_pct=1.5,
            max_deploy_usd=15000.0,
            max_order_notional_usd=3000.0,
            target_positions=4,
            max_session_loss_usd=500.0,
            max_session_drawdown_pct=0.5,
        )
        assert report["status"] == "skipped"
        assert report["reason"] == "premarket_status_missing"

    def test_premarket_hard_blocker_skips_trading(self, tmp_path, monkeypatch):
        ops_dir = tmp_path / "ops"
        premarket_dir = ops_dir / "premarket"
        premarket_dir.mkdir(parents=True)
        (premarket_dir / "2026-07-20.json").write_text(
            json.dumps({"ready_for_trading": False, "hard_blockers": ["account_active"]}),
            encoding="utf-8",
        )

        def _fail_if_called(**kwargs):
            raise AssertionError("circuit breaker should not be checked when premarket hard-blocked")

        monkeypatch.setattr(trading_session, "weekly_circuit_breaker_status", _fail_if_called)

        report = trading_session.run_trading_session(
            ops_results_dir=str(ops_dir),
            day_trader_results_dir=str(tmp_path / "dt"),
            trade_date="2026-07-20",
            weekly_loss_limit_pct=1.5,
            max_deploy_usd=15000.0,
            max_order_notional_usd=3000.0,
            target_positions=4,
            max_session_loss_usd=500.0,
            max_session_drawdown_pct=0.5,
        )
        assert report["status"] == "skipped"
        assert "account_active" in report["reason"]

    def test_ready_premarket_status_proceeds_to_circuit_breaker(self, tmp_path, monkeypatch):
        ops_dir = tmp_path / "ops"
        premarket_dir = ops_dir / "premarket"
        premarket_dir.mkdir(parents=True)
        (premarket_dir / "2026-07-20.json").write_text(
            json.dumps({"ready_for_trading": True, "hard_blockers": []}),
            encoding="utf-8",
        )

        fake_status = opslib.CircuitBreakerStatus(
            breached=False,
            week_start="2026-07-20",
            sessions_counted=0,
            baseline_equity=None,
            cumulative_pnl_usd=0.0,
            cumulative_pnl_pct=0.0,
            reason="no_sessions_recorded_this_week",
        )
        monkeypatch.setattr(trading_session, "weekly_circuit_breaker_status", lambda **kwargs: fake_status)
        monkeypatch.setattr(trading_session.subprocess, "run", lambda *a, **k: pytest.fail("should not launch"))

        report = trading_session.run_trading_session(
            ops_results_dir=str(ops_dir),
            day_trader_results_dir=str(tmp_path / "dt"),
            trade_date="2026-07-20",
            weekly_loss_limit_pct=1.5,
            max_deploy_usd=15000.0,
            max_order_notional_usd=3000.0,
            target_positions=4,
            max_session_loss_usd=500.0,
            max_session_drawdown_pct=0.5,
            dry_run=True,
        )
        assert report["status"] == "skipped"
        assert report["reason"] == "dry_run"
