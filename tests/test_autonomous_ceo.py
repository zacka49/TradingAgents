from datetime import UTC, datetime
from types import SimpleNamespace

from tradingagents.company import (
    AutonomousCEOSettings,
    AutonomousPaperCEOAgent,
    MarketCandidate,
    PortfolioOrderPlan,
    parse_universe,
    profiles_from_choice,
)


class FakeCEOBroker:
    def get_clock(self):
        return {
            "is_open": True,
            "next_close": "2026-05-06T16:00:00-04:00",
            "next_open": "2026-05-07T09:30:00-04:00",
        }

    def get_account(self):
        return {"portfolio_value": "1000"}


class FakeRunner:
    calls = []

    def __init__(self, config, broker):
        self.config = config
        self.broker = broker
        FakeRunner.calls.append(config)

    def run(self, *, trade_date, universe, submit, ceo_approved):
        candidate = MarketCandidate(
            ticker="AAA",
            latest_price=100.0,
            return_1d_pct=1.0,
            return_5d_pct=2.0,
            return_20d_pct=3.0,
            volume_ratio=1.5,
            volatility_20d_pct=0.5,
            score=2.0,
            risk_flags=[],
            strategy="momentum_breakout",
            strategy_confidence=0.8,
            strategy_note="test",
            auto_trade_allowed=True,
            stop_loss_pct=0.02,
            take_profit_pct=0.04,
        )
        return SimpleNamespace(
            market_open=True,
            artifact_dir="results/test",
            candidates=[candidate],
            target_weights={"AAA": 0.1},
            order_plans=[],
            submitted_orders=0,
            blocked_orders=0,
        )


def test_parse_universe_and_profiles():
    assert parse_universe(" amd, nvda ,, spy ") == ["AMD", "NVDA", "SPY"]
    assert profiles_from_choice("both") == ["safe", "risky"]
    assert profiles_from_choice("safe") == ["safe"]


def test_autonomous_ceo_runs_both_profiles_without_manual_supervision():
    FakeRunner.calls = []
    events = []
    agent = AutonomousPaperCEOAgent(
        AutonomousCEOSettings(
            profiles=("safe", "risky"),
            universe=("AAA", "BBB"),
            once=True,
        ),
        broker=FakeCEOBroker(),
        runner_factory=lambda config, broker: FakeRunner(config, broker),
        now_fn=lambda: datetime(2026, 5, 6, 13, 30, tzinfo=UTC),
    )

    assert agent.run(events.append) == 0

    assert [event["event"] for event in events] == [
        "autonomous_ceo_cycle_start",
        "autonomous_ceo_profile_start",
        "autonomous_ceo_profile_complete",
        "autonomous_ceo_profile_start",
        "autonomous_ceo_profile_complete",
        "autonomous_ceo_cycle",
    ]

    cycle_event = events[-1]
    assert [profile["strategy_profile"] for profile in cycle_event["profiles"]] == [
        "safe",
        "risky",
    ]
    assert [config["strategy_profile_name"] for config in FakeRunner.calls] == [
        "safe",
        "risky",
    ]
    assert all(config["ceo_approval_required"] is False for config in FakeRunner.calls)
