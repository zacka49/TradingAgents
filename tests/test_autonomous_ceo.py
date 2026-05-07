from datetime import UTC, datetime
from types import SimpleNamespace

from tradingagents.company import (
    AutonomousCEOSettings,
    AutonomousPaperCEOAgent,
    MarketCandidate,
    PortfolioOrderPlan,
    open_sell_quantity_by_symbol,
    parse_universe,
    profiles_from_choice,
)


class FakeCEOBroker:
    def __init__(self):
        self.closed_positions = []
        self.submitted_orders = []
        self.cancelled_orders = []
        self.positions_payload = [
            {
                "symbol": "AAA",
                "qty": "2",
                "market_value": "200",
                "unrealized_pl": "4",
                "unrealized_plpc": "0.02",
                "current_price": "100",
            }
        ]
        self.orders_payload = [
            {
                "id": "order-1",
                "symbol": "AAA",
                "side": "sell",
                "qty": "2",
                "type": "stop",
                "order_class": "bracket",
                "status": "held",
                "stop_price": "97",
            }
        ]

    def get_clock(self):
        return {
            "is_open": True,
            "next_close": "2026-05-06T16:00:00-04:00",
            "next_open": "2026-05-07T09:30:00-04:00",
        }

    def get_account(self):
        return {"portfolio_value": "1000"}

    def get_positions(self):
        return {"positions": self.positions_payload}

    def get_orders(self, status="open"):
        return {"orders": self.orders_payload}

    def close_all_positions(self, cancel_orders=True):
        payload = {"cancel_orders": cancel_orders, "status": "requested"}
        self.closed_positions.append(payload)
        return payload

    def cancel_order(self, order_id):
        self.cancelled_orders.append(order_id)
        return {"id": order_id, "status": "canceled"}

    def submit_order(self, order):
        self.submitted_orders.append(order)
        return {
            "id": f"exit-{order.ticker}",
            "symbol": order.ticker,
            "side": order.side,
            "qty": str(order.quantity),
            "status": "accepted",
        }


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


def test_autonomous_ceo_position_monitor_summarizes_live_risk():
    agent = AutonomousPaperCEOAgent(
        AutonomousCEOSettings(once=True),
        broker=FakeCEOBroker(),
        runner_factory=lambda config, broker: FakeRunner(config, broker),
        now_fn=lambda: datetime(2026, 5, 6, 13, 30, tzinfo=UTC),
    )

    event = agent.position_monitor_event(cycle=3, seconds_to_next_cycle=4.5)

    assert event["event"] == "autonomous_ceo_position_monitor"
    assert event["positions_count"] == 1
    assert event["open_orders_count"] == 1
    assert event["positions"][0]["symbol"] == "AAA"
    assert event["open_orders"][0]["order_class"] == "bracket"


def test_autonomous_ceo_profit_protection_exits_giveback():
    broker = FakeCEOBroker()
    broker.positions_payload = [
        {
            "symbol": "AAA",
            "qty": "10",
            "market_value": "1010",
            "avg_entry_price": "100",
            "current_price": "101",
            "unrealized_pl": "10",
            "unrealized_plpc": "0.01",
        }
    ]
    broker.orders_payload = [
        {
            "id": "bracket-limit",
            "symbol": "AAA",
            "side": "sell",
            "qty": "10",
            "type": "limit",
            "order_class": "bracket",
            "status": "new",
            "limit_price": "106",
        }
    ]
    agent = AutonomousPaperCEOAgent(
        AutonomousCEOSettings(
            once=True,
            exit_unprotected_positions=False,
            profit_protection_min_gain_pct=0.75,
            profit_protection_max_giveback_pct=0.60,
            profit_protection_max_giveback_fraction=0.50,
            profit_protection_min_unrealized_pl_usd=5.0,
        ),
        broker=broker,
        runner_factory=lambda config, broker: FakeRunner(config, broker),
        now_fn=lambda: datetime(2026, 5, 6, 14, 30, tzinfo=UTC),
    )
    agent.position_highs["AAA"] = 103.0

    event = agent.position_monitor_event(cycle=4, seconds_to_next_cycle=10)

    assert event["risk_exits"][0]["reason"] == "profit_giveback"
    assert event["risk_exits"][0]["submitted"] is True
    assert broker.cancelled_orders == ["bracket-limit"]
    assert broker.submitted_orders[0].ticker == "AAA"
    assert broker.submitted_orders[0].side == "sell"
    assert broker.submitted_orders[0].quantity == 10


def test_autonomous_ceo_exits_unprotected_remainder():
    broker = FakeCEOBroker()
    broker.positions_payload = [
        {
            "symbol": "AAA",
            "qty": "11.25",
            "market_value": "1125",
            "avg_entry_price": "100",
            "current_price": "100",
            "unrealized_pl": "0",
            "unrealized_plpc": "0",
        }
    ]
    broker.orders_payload = [
        {
            "id": "bracket-limit",
            "symbol": "AAA",
            "side": "sell",
            "qty": "10",
            "type": "limit",
            "order_class": "bracket",
            "status": "new",
            "limit_price": "106",
        }
    ]
    agent = AutonomousPaperCEOAgent(
        AutonomousCEOSettings(
            once=True,
            protect_intraday_profits=False,
            exit_unprotected_positions=True,
            unprotected_position_grace_seconds=0,
            open_sell_coverage_threshold=0.95,
        ),
        broker=broker,
        runner_factory=lambda config, broker: FakeRunner(config, broker),
        now_fn=lambda: datetime(2026, 5, 6, 14, 30, tzinfo=UTC),
    )

    event = agent.position_monitor_event(cycle=5, seconds_to_next_cycle=10)

    assert event["risk_exits"][0]["reason"] == "unprotected_remainder"
    assert event["risk_exits"][0]["submitted"] is True
    assert broker.cancelled_orders == []
    assert broker.submitted_orders[0].ticker == "AAA"
    assert broker.submitted_orders[0].side == "sell"
    assert broker.submitted_orders[0].quantity == 1.25


def test_open_sell_coverage_counts_bracket_legs_once():
    quantities = open_sell_quantity_by_symbol(
        [
            {
                "id": "parent",
                "symbol": "AAA",
                "side": "buy",
                "qty": "10",
                "status": "filled",
                "legs": [
                    {
                        "id": "take-profit",
                        "symbol": "AAA",
                        "side": "sell",
                        "qty": "10",
                        "filled_qty": "0",
                        "status": "new",
                    },
                    {
                        "id": "stop",
                        "symbol": "AAA",
                        "side": "sell",
                        "qty": "10",
                        "filled_qty": "0",
                        "status": "held",
                    },
                ],
            }
        ]
    )

    assert quantities == {"AAA": 10.0}


def test_autonomous_ceo_flattens_in_pre_close_window():
    broker = FakeCEOBroker()
    events = []
    agent = AutonomousPaperCEOAgent(
        AutonomousCEOSettings(
            once=False,
            run_until_close=True,
            flatten_at_close=True,
            flatten_minutes_before_close=5,
        ),
        broker=broker,
        runner_factory=lambda config, broker: FakeRunner(config, broker),
        now_fn=lambda: datetime(2026, 5, 6, 19, 56, tzinfo=UTC),
    )

    assert agent.run(events.append) == 0

    assert broker.closed_positions == [
        {"cancel_orders": True, "status": "requested"}
    ]
    assert [event["event"] for event in events] == [
        "autonomous_ceo_eod_flatten_start",
        "autonomous_ceo_eod_flatten_complete",
    ]
