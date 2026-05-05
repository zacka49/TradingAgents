from tradingagents.company import CodexCEOCompanyRunner, MarketCandidate
from tradingagents.execution import OrderIntent, evaluate_order_policy


class FakeBroker:
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
        return {
            "id": f"order-{order.ticker}",
            "symbol": order.ticker,
            "side": order.side,
            "qty": str(order.quantity),
            "status": "accepted",
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
