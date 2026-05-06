from tradingagents.company import CodexCEOCompanyRunner, MarketCandidate, apply_day_trader_profile
from tradingagents.agents.utils.agent_utils import get_strategy_doctrine_context
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution import OrderIntent, evaluate_order_policy


class FakeBroker:
    def __init__(self):
        self.submitted_orders = []

    def get_account(self):
        return {
            "status": "ACTIVE",
            "equity": "1000",
            "buying_power": "1000",
            "cash": "1000",
            "portfolio_value": "1000",
        }

    def get_positions(self):
        return {"positions": []}

    def get_clock(self):
        return {"is_open": True}

    def get_latest_trade(self, symbol):
        return {"p": 50 if symbol == "AAA" else 25}

    def submit_order(self, order):
        self.submitted_orders.append(order)
        return {
            "id": f"order-{order.ticker}",
            "symbol": order.ticker,
            "side": order.side,
            "qty": str(order.quantity),
            "status": "accepted",
        }


class FakePLTRBroker(FakeBroker):
    def get_account(self):
        return {
            "status": "ACTIVE",
            "equity": "2000",
            "buying_power": "2000",
            "cash": "2000",
            "portfolio_value": "2000",
        }

    def get_latest_trade(self, symbol):
        return {"p": 134.13}


class FakeLargePaperBroker(FakeBroker):
    def get_account(self):
        return {
            "status": "ACTIVE",
            "equity": "100000",
            "buying_power": "100000",
            "cash": "100000",
            "portfolio_value": "100000",
        }


def _candidate(ticker, price, score):
    return MarketCandidate(
        ticker=ticker,
        latest_price=price,
        return_1d_pct=1.0,
        return_5d_pct=3.0,
        return_20d_pct=5.0,
        volume_ratio=1.2,
        volatility_20d_pct=2.0,
        score=score,
        risk_flags=[],
        strategy="momentum_breakout",
        strategy_confidence=0.8,
        strategy_note="test strategy",
        auto_trade_allowed=True,
        stop_loss_pct=0.03,
        take_profit_pct=0.06,
    )


def test_codex_ceo_company_builds_guarded_orders():
    runner = CodexCEOCompanyRunner(
        {
            "portfolio_target_positions": 2,
            "portfolio_deploy_pct": 0.5,
            "portfolio_max_position_weight": 0.25,
            "portfolio_max_deploy_usd": 1000,
            "portfolio_min_order_notional_usd": 10,
            "max_order_notional_usd": 250,
            "max_position_notional_usd": 500,
            "enforce_market_open": True,
            "ceo_approval_required": True,
            "day_trade_auto_strategies": ["momentum_breakout"],
            "day_trade_min_strategy_confidence": 0.58,
            "ollama_staff_memo_enabled": False,
            "results_dir": "unused",
        },
        broker=FakeBroker(),
    )
    candidates = [_candidate("AAA", 50, 10), _candidate("BBB", 25, 8)]
    weights = runner.build_target_weights(candidates)
    plans = runner.build_order_plans(
        candidates=candidates,
        target_weights=weights,
        account=runner.broker.get_account(),
        positions=[],
    )

    assert weights == {"AAA": 0.25, "BBB": 0.25}
    assert [plan.ticker for plan in plans] == ["AAA", "BBB"]
    assert plans[0].stop_loss_price == 48.5
    assert plans[0].take_profit_price == 53.0

    runner.apply_order_plans(
        plans,
        account=runner.broker.get_account(),
        market_open=True,
        submit=True,
        ceo_approved=False,
    )
    assert {plan.blocked_reason for plan in plans} == {"ceo_approval_required"}


def test_open_buy_orders_count_against_target_allocation():
    runner = CodexCEOCompanyRunner(
        {
            "portfolio_target_positions": 1,
            "portfolio_deploy_pct": 0.25,
            "portfolio_max_position_weight": 0.25,
            "portfolio_max_deploy_usd": 1000,
            "portfolio_min_order_notional_usd": 10,
            "max_order_notional_usd": 250,
            "day_trade_auto_strategies": ["momentum_breakout"],
            "day_trade_min_strategy_confidence": 0.58,
            "ollama_staff_memo_enabled": False,
            "results_dir": "unused",
        },
        broker=FakeBroker(),
    )
    candidates = [_candidate("AAA", 50, 10)]
    plans = runner.build_order_plans(
        candidates=candidates,
        target_weights=runner.build_target_weights(candidates),
        account=runner.broker.get_account(),
        positions=[],
        open_orders=[
            {
                "symbol": "AAA",
                "side": "buy",
                "qty": "5",
                "limit_price": "50",
                "status": "new",
            }
        ],
    )

    assert plans == []


def test_bracket_buy_order_quantities_are_whole_shares():
    runner = CodexCEOCompanyRunner(
        {
            "portfolio_target_positions": 1,
            "portfolio_deploy_pct": 0.25,
            "portfolio_max_position_weight": 0.25,
            "portfolio_max_deploy_usd": 1000,
            "portfolio_min_order_notional_usd": 10,
            "max_order_notional_usd": 250,
            "day_trade_auto_strategies": ["momentum_breakout"],
            "day_trade_min_strategy_confidence": 0.58,
            "ollama_staff_memo_enabled": False,
            "results_dir": "unused",
            "use_bracket_orders": True,
        },
        broker=FakeBroker(),
    )
    candidates = [_candidate("AAA", 201, 10)]
    plans = runner.build_order_plans(
        candidates=candidates,
        target_weights=runner.build_target_weights(candidates),
        account=runner.broker.get_account(),
        positions=[],
    )

    assert plans[0].quantity == 1
    assert plans[0].estimated_notional_usd == 201


def test_live_price_refresh_keeps_bracket_buy_quantities_whole_shares():
    broker = FakePLTRBroker()
    runner = CodexCEOCompanyRunner(
        {
            "portfolio_target_positions": 1,
            "portfolio_deploy_pct": 0.25,
            "portfolio_max_position_weight": 0.25,
            "portfolio_max_deploy_usd": 1600,
            "portfolio_min_order_notional_usd": 10,
            "max_order_notional_usd": 350,
            "max_position_notional_usd": 500,
            "enforce_market_open": True,
            "ceo_approval_required": False,
            "day_trade_auto_strategies": ["momentum_breakout"],
            "day_trade_min_strategy_confidence": 0.58,
            "ollama_staff_memo_enabled": False,
            "results_dir": "unused",
            "use_bracket_orders": True,
            "refresh_live_prices_before_submit": True,
        },
        broker=broker,
    )
    plans = runner.build_order_plans(
        candidates=[_candidate("PLTR", 134.1, 10)],
        target_weights={"PLTR": 0.17},
        account=broker.get_account(),
        positions=[],
    )

    assert plans[0].quantity == 2

    runner.apply_order_plans(
        plans,
        account=broker.get_account(),
        market_open=True,
        submit=True,
        ceo_approved=True,
    )

    assert plans[0].submitted is True
    assert plans[0].quantity == 2
    assert plans[0].estimated_notional_usd == 268.26
    assert broker.submitted_orders[0].quantity == 2


def test_codex_ceo_company_submits_when_approved():
    runner = CodexCEOCompanyRunner(
        {
            "portfolio_target_positions": 1,
            "portfolio_deploy_pct": 0.25,
            "portfolio_max_position_weight": 0.25,
            "portfolio_max_deploy_usd": 1000,
            "portfolio_min_order_notional_usd": 10,
            "max_order_notional_usd": 250,
            "max_position_notional_usd": 500,
            "enforce_market_open": True,
            "ceo_approval_required": True,
            "day_trade_auto_strategies": ["momentum_breakout"],
            "day_trade_min_strategy_confidence": 0.58,
            "ollama_staff_memo_enabled": False,
            "results_dir": "unused",
        },
        broker=FakeBroker(),
    )
    candidates = [_candidate("AAA", 50, 10)]
    plans = runner.build_order_plans(
        candidates=candidates,
        target_weights=runner.build_target_weights(candidates),
        account=runner.broker.get_account(),
        positions=[],
    )
    runner.apply_order_plans(
        plans,
        account=runner.broker.get_account(),
        market_open=True,
        submit=True,
        ceo_approved=True,
    )

    assert plans[0].submitted is True
    assert plans[0].order_response["status"] == "accepted"


def test_codex_ceo_company_autonomous_mode_skips_approval_gate():
    runner = CodexCEOCompanyRunner(
        {
            "portfolio_target_positions": 1,
            "portfolio_deploy_pct": 0.25,
            "portfolio_max_position_weight": 0.25,
            "portfolio_max_deploy_usd": 1000,
            "portfolio_min_order_notional_usd": 10,
            "max_order_notional_usd": 250,
            "max_position_notional_usd": 500,
            "enforce_market_open": True,
            "ceo_approval_required": False,
            "day_trade_auto_strategies": ["momentum_breakout"],
            "day_trade_min_strategy_confidence": 0.58,
            "ollama_staff_memo_enabled": False,
            "results_dir": "unused",
        },
        broker=FakeBroker(),
    )
    candidates = [_candidate("AAA", 50, 10)]
    plans = runner.build_order_plans(
        candidates=candidates,
        target_weights=runner.build_target_weights(candidates),
        account=runner.broker.get_account(),
        positions=[],
    )
    runner.apply_order_plans(
        plans,
        account=runner.broker.get_account(),
        market_open=True,
        submit=True,
        ceo_approved=False,
    )

    assert plans[0].submitted is True


def test_safe_and_risky_profiles_apply_distinct_risk_caps():
    safe = apply_day_trader_profile(DEFAULT_CONFIG, "safe")
    risky = apply_day_trader_profile(DEFAULT_CONFIG, "risky")

    assert safe["ceo_approval_required"] is False
    assert risky["ceo_approval_required"] is False
    assert "opening_range_breakout_15m" in safe["day_trade_auto_strategies"]
    assert "opening_range_breakout_15m" in risky["day_trade_auto_strategies"]
    assert safe["portfolio_min_order_notional_usd"] == 2000.0
    assert risky["portfolio_min_order_notional_usd"] == 2000.0
    assert safe["max_order_notional_usd"] == 3000.0
    assert risky["max_order_notional_usd"] == 5000.0
    assert safe["portfolio_max_deploy_usd"] == 50000.0
    assert risky["portfolio_max_deploy_usd"] == 60000.0
    assert safe["max_order_notional_usd"] < risky["max_order_notional_usd"]
    assert safe["day_trade_min_strategy_confidence"] > risky["day_trade_min_strategy_confidence"]
    assert safe["day_trade_max_stop_loss_pct"] < risky["day_trade_max_stop_loss_pct"]


def test_profiles_size_trades_above_two_thousand_for_large_paper_account():
    broker = FakeLargePaperBroker()
    candidate = _candidate("AAA", 50, 10)
    candidate.strategy = "relative_strength_continuation"
    candidates = [candidate]

    for profile_name in ["safe", "risky"]:
        runner = CodexCEOCompanyRunner(
            {
                **apply_day_trader_profile(DEFAULT_CONFIG, profile_name),
                "ollama_staff_memo_enabled": False,
                "results_dir": "unused",
            },
            broker=broker,
        )
        plans = runner.build_order_plans(
            candidates=candidates,
            target_weights=runner.build_target_weights(candidates),
            account=broker.get_account(),
            positions=[],
        )

        assert plans[0].estimated_notional_usd >= 2000


def test_realtime_opening_range_breakout_is_classified():
    runner = CodexCEOCompanyRunner(
        {
            "strategy_profile_name": "risky",
            "day_trade_block_risk_flags": [],
            "day_trade_stop_loss_multiplier": 1.0,
            "day_trade_take_profit_multiplier": 1.0,
            "day_trade_min_stop_loss_pct": 0.005,
            "day_trade_max_stop_loss_pct": 0.10,
            "day_trade_min_take_profit_pct": 0.01,
            "day_trade_max_take_profit_pct": 0.20,
            "codex_ceo_min_price": 5.0,
            "codex_ceo_realtime_min_recent_volume": 0,
            "codex_ceo_realtime_max_spread_pct": 0.12,
            "codex_ceo_realtime_high_volatility_pct": 2.0,
            "codex_ceo_realtime_max_trade_age_seconds": 3600,
        },
        broker=FakeBroker(),
    )
    bars = [
        {"t": "2026-05-05T13:30:00Z", "o": 99.7, "h": 100.0, "l": 99.5, "c": 99.8, "v": 1000},
        {"t": "2026-05-05T13:35:00Z", "o": 99.8, "h": 100.2, "l": 99.7, "c": 100.0, "v": 1000},
        {"t": "2026-05-05T13:40:00Z", "o": 100.0, "h": 100.4, "l": 99.9, "c": 100.1, "v": 1000},
        {"t": "2026-05-05T13:45:00Z", "o": 100.1, "h": 100.8, "l": 100.0, "c": 100.6, "v": 2500},
        {"t": "2026-05-05T13:50:00Z", "o": 100.6, "h": 101.0, "l": 100.5, "c": 100.8, "v": 2600},
        {"t": "2026-05-05T13:55:00Z", "o": 100.8, "h": 101.2, "l": 100.7, "c": 100.9, "v": 2700},
        {"t": "2026-05-05T14:00:00Z", "o": 100.9, "h": 101.3, "l": 100.8, "c": 101.0, "v": 2800},
        {"t": "2026-05-05T14:05:00Z", "o": 101.0, "h": 101.4, "l": 100.9, "c": 101.1, "v": 2900},
    ]

    candidate = runner._score_realtime_ticker(
        "AAA",
        bars,
        {"p": 101.2, "t": "2026-05-05T14:05:30Z"},
        {"bp": 101.19, "ap": 101.21},
    )

    assert candidate is not None
    assert candidate.strategy == "opening_range_breakout_15m"
    assert candidate.auto_trade_allowed is True


def test_realtime_candidate_carries_alpaca_snapshot_fields():
    runner = CodexCEOCompanyRunner(
        {
            "strategy_profile_name": "risky",
            "day_trade_block_risk_flags": [],
            "day_trade_stop_loss_multiplier": 1.0,
            "day_trade_take_profit_multiplier": 1.0,
            "day_trade_min_stop_loss_pct": 0.005,
            "day_trade_max_stop_loss_pct": 0.10,
            "day_trade_min_take_profit_pct": 0.01,
            "day_trade_max_take_profit_pct": 0.20,
            "codex_ceo_min_price": 5.0,
            "codex_ceo_realtime_min_recent_volume": 0,
            "codex_ceo_realtime_max_spread_pct": 0.12,
            "codex_ceo_realtime_high_volatility_pct": 2.0,
            "codex_ceo_realtime_max_trade_age_seconds": 3600,
            "alpaca_stock_feed": "iex",
        },
        broker=FakeBroker(),
    )
    bars = [
        {"t": "2026-05-05T13:30:00Z", "o": 100, "h": 101, "l": 99, "c": 100, "v": 1000},
        {"t": "2026-05-05T13:31:00Z", "o": 100, "h": 102, "l": 99, "c": 101, "v": 1200},
        {"t": "2026-05-05T13:32:00Z", "o": 101, "h": 103, "l": 100, "c": 102, "v": 1300},
    ]
    snapshot = {
        "latestTrade": {"p": 103, "s": 200, "t": "2026-05-05T13:32:30Z"},
        "latestQuote": {"bp": 102.95, "ap": 103.05, "bs": 6, "as": 4, "t": "2026-05-05T13:32:31Z"},
        "minuteBar": {"o": 102, "h": 103.2, "l": 101.9, "c": 103, "v": 2222},
        "dailyBar": {"o": 99, "h": 104, "l": 98, "c": 103, "v": 333333},
        "prevDailyBar": {"c": 100, "v": 444444},
    }

    candidate = runner._score_realtime_ticker(
        "AAA",
        bars,
        {},
        {},
        snapshot=snapshot,
    )

    assert candidate is not None
    assert candidate.bid_price == 102.95
    assert candidate.ask_price == 103.05
    assert candidate.quote_imbalance == 0.2
    assert candidate.minute_bar_volume == 2222
    assert candidate.daily_bar_volume == 333333
    assert candidate.prev_close_return_pct == 3.0
    assert candidate.live_market["latest_trade"]["price"] == 103


def test_news_politics_context_expands_and_boosts_candidates(monkeypatch):
    def fake_discover(base, **kwargs):
        return {
            "symbols": [*base, "NVDA"],
            "base_symbols": list(base),
            "added_symbols": ["NVDA"],
            "scores": {"NVDA": 4},
            "catalysts_by_symbol": {"NVDA": ["direct_headline_match"]},
            "themes_by_symbol": {"NVDA": ["ai_chips_datacenter"]},
            "headlines_by_symbol": {"NVDA": ["AI chip policy puts NVDA in focus (TestWire)"]},
            "risk_headlines_by_symbol": {},
            "errors": [],
        }

    monkeypatch.setattr(
        "tradingagents.company.codex_ceo_company.discover_news_politics_symbols",
        fake_discover,
    )
    runner = CodexCEOCompanyRunner(
        {
            "codex_ceo_news_political_scan_enabled": True,
            "codex_ceo_news_political_max_symbols": 5,
            "codex_ceo_news_catalyst_score_bonus": 0.25,
            "codex_ceo_news_catalyst_max_bonus": 2,
        },
        broker=FakeBroker(),
    )
    expanded = runner._expand_universe_with_news_politics(["SPY"], max_symbols=5)
    candidate = _candidate("NVDA", 100, 1)

    runner._apply_catalyst_context(candidate)

    assert expanded == ["SPY", "NVDA"]
    assert candidate.score == 2.0
    assert candidate.political_themes == ["ai_chips_datacenter"]
    assert candidate.news_headlines == ["AI chip policy puts NVDA in focus (TestWire)"]


def test_strategy_doctrine_context_contains_tradeable_and_watch_only_rules():
    doctrine = get_strategy_doctrine_context()

    assert "Regime before signal" in doctrine
    assert "opening-range breakout" in doctrine
    assert "famous-trader playbooks" in doctrine
    assert "pivotal-point volume breakouts" in doctrine
    assert "VWAP reclaim" in doctrine
    assert "watch/research modes" in doctrine


def test_sell_orders_do_not_require_buying_power_or_position_cap():
    policy = evaluate_order_policy(
        intent=OrderIntent(ticker="AAA", side="sell", quantity=10),
        account={"buying_power": "1"},
        market_open=True,
        latest_price=20,
        config={
            "enforce_market_open": True,
            "max_order_notional_usd": 250,
            "max_position_notional_usd": 25,
        },
    )

    assert policy.allow is True
    assert policy.reason == "approved"
