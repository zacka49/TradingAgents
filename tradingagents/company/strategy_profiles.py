from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


SAFE_DAY_TRADER_PROFILE: Dict[str, Any] = {
    "strategy_profile_name": "safe",
    "portfolio_target_positions": 4,
    "portfolio_max_active_positions": 4,
    "portfolio_deploy_pct": 0.20,
    "portfolio_max_position_weight": 0.05,
    "portfolio_max_deploy_usd": 50000.0,
    "max_order_notional_usd": 3000.0,
    "max_position_notional_usd": 6000.0,
    "portfolio_min_order_notional_usd": 2000.0,
    "day_trade_auto_strategies": [
        "opening_range_breakout_15m",
        "momentum_breakout",
        "relative_strength_continuation",
    ],
    "day_trade_min_strategy_confidence": 0.72,
    "codex_ceo_day_trade_min_fit_score": 4.0,
    "codex_ceo_day_trade_preferred_min_volume_ratio": 1.05,
    "codex_ceo_day_trade_preferred_min_volatility_pct": 0.6,
    "codex_ceo_day_trade_preferred_max_volatility_pct": 4.0,
    "day_trade_stop_loss_multiplier": 0.60,
    "day_trade_take_profit_multiplier": 0.60,
    "day_trade_min_stop_loss_pct": 0.012,
    "day_trade_max_stop_loss_pct": 0.025,
    "day_trade_min_take_profit_pct": 0.018,
    "day_trade_max_take_profit_pct": 0.035,
    "day_trade_block_risk_flags": [
        "high_volatility",
        "wide_spread",
        "stale_live_trade",
        "weak_backtest",
        "news_risk",
        "buy_pressure_absorbed",
    ],
    "backtest_lab_gate_targets": True,
    "backtest_lab_min_closed_trades": 1,
    "day_trade_trim_stale_losers": True,
    "day_trade_stale_loss_pct": 0.75,
    "day_trade_trim_non_target_losers": True,
    "realtime_score_minimum": 0.40,
    "codex_ceo_news_political_scan_enabled": True,
    "codex_ceo_news_political_max_symbols": 60,
    "codex_ceo_realtime_lookback_minutes": 120,
    "codex_ceo_order_flow_enrichment_limit": 8,
    "day_trader_flatten_at_close": True,
    "day_trader_flatten_minutes_before_close": 5,
    "day_trader_stop_new_entries_minutes_before_close": 15,
    "day_trader_flatten_on_max_cycles": True,
    "day_trader_cancel_orders_before_flatten": True,
    "use_bracket_orders": True,
}


RISKY_DAY_TRADER_PROFILE: Dict[str, Any] = {
    "strategy_profile_name": "risky",
    "portfolio_target_positions": 5,
    "portfolio_max_active_positions": 5,
    "portfolio_deploy_pct": 0.30,
    "portfolio_max_position_weight": 0.05,
    "portfolio_max_deploy_usd": 60000.0,
    "max_order_notional_usd": 5000.0,
    "max_position_notional_usd": 10000.0,
    "portfolio_min_order_notional_usd": 2000.0,
    "day_trade_auto_strategies": [
        "opening_range_breakout_15m",
        "momentum_breakout",
        "relative_strength_continuation",
    ],
    "day_trade_min_strategy_confidence": 0.55,
    "codex_ceo_day_trade_min_fit_score": 3.0,
    "codex_ceo_day_trade_preferred_min_volume_ratio": 1.0,
    "codex_ceo_day_trade_preferred_min_volatility_pct": 0.45,
    "codex_ceo_day_trade_preferred_max_volatility_pct": 4.8,
    "day_trade_stop_loss_multiplier": 1.25,
    "day_trade_take_profit_multiplier": 0.85,
    "day_trade_min_stop_loss_pct": 0.025,
    "day_trade_max_stop_loss_pct": 0.065,
    "day_trade_min_take_profit_pct": 0.025,
    "day_trade_max_take_profit_pct": 0.055,
    "day_trade_block_risk_flags": [
        "wide_spread",
        "stale_live_trade",
        "news_risk",
    ],
    "backtest_lab_gate_targets": False,
    "backtest_lab_min_closed_trades": 1,
    "day_trade_trim_stale_losers": True,
    "day_trade_stale_loss_pct": 1.0,
    "day_trade_trim_non_target_losers": True,
    "realtime_score_minimum": 0.15,
    "codex_ceo_news_political_scan_enabled": True,
    "codex_ceo_news_political_max_symbols": 60,
    "codex_ceo_realtime_lookback_minutes": 120,
    "codex_ceo_order_flow_enrichment_limit": 10,
    "day_trader_flatten_at_close": True,
    "day_trader_flatten_minutes_before_close": 5,
    "day_trader_stop_new_entries_minutes_before_close": 15,
    "day_trader_flatten_on_max_cycles": True,
    "day_trader_cancel_orders_before_flatten": True,
    "use_bracket_orders": True,
}


DAY_TRADER_PROFILES = {
    "safe": SAFE_DAY_TRADER_PROFILE,
    "risky": RISKY_DAY_TRADER_PROFILE,
}


def apply_day_trader_profile(config: Dict[str, Any], profile_name: str) -> Dict[str, Any]:
    """Return a config copy with the named autonomous day-trader profile applied."""
    normalized = profile_name.strip().lower()
    if normalized not in DAY_TRADER_PROFILES:
        raise ValueError(f"Unknown day-trader profile: {profile_name}")
    profiled = deepcopy(config)
    profiled.update(DAY_TRADER_PROFILES[normalized])
    profiled["autonomous_paper_trading_enabled"] = True
    profiled["ceo_approval_required"] = False
    profiled["enforce_market_open"] = True
    profiled["codex_ceo_realtime_scan_enabled"] = True
    profiled["refresh_live_prices_before_submit"] = True
    return profiled
