from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class StrategyProfile:
    name: str
    confidence: float
    auto_trade_allowed: bool
    stop_loss_pct: float
    take_profit_pct: float
    note: str


def classify_day_trade_setup(
    *,
    return_1d_pct: float,
    return_5d_pct: float,
    return_20d_pct: float,
    volume_ratio: float,
    volatility_20d_pct: float,
    risk_flags: Iterable[str],
) -> StrategyProfile:
    """Classify a candidate into a compute-light day-trading playbook.

    The goal is not to predict the next tick. It converts the research screen
    into explicit operating modes so the paper runner can avoid mixing
    breakout, momentum, range, and fading logic in one generic score.
    """
    flags = set(risk_flags)

    if return_1d_pct > 2.0 and return_5d_pct > 3.0 and volume_ratio >= 1.05:
        confidence = min(0.95, 0.62 + return_1d_pct / 30.0 + min(volume_ratio, 2.0) / 12.0)
        return StrategyProfile(
            name="momentum_breakout",
            confidence=round(confidence, 3),
            auto_trade_allowed=True,
            stop_loss_pct=0.035 if volatility_20d_pct < 4.0 else 0.045,
            take_profit_pct=0.07 if volatility_20d_pct < 4.0 else 0.09,
            note="Positive 1D/5D momentum with confirming relative volume.",
        )

    if return_5d_pct > 4.0 and return_20d_pct > 10.0 and -1.5 <= return_1d_pct <= 2.0:
        confidence = min(0.90, 0.58 + return_5d_pct / 40.0 + return_20d_pct / 120.0)
        return StrategyProfile(
            name="relative_strength_continuation",
            confidence=round(confidence, 3),
            auto_trade_allowed=True,
            stop_loss_pct=0.03 if volatility_20d_pct < 3.5 else 0.04,
            take_profit_pct=0.06 if volatility_20d_pct < 3.5 else 0.08,
            note="Strong multi-day trend without an overextended latest session.",
        )

    if return_20d_pct > 15.0 and return_1d_pct < -2.0:
        confidence = 0.42 if "high_volatility" in flags else 0.50
        return StrategyProfile(
            name="pullback_watch",
            confidence=confidence,
            auto_trade_allowed=False,
            stop_loss_pct=0.03,
            take_profit_pct=0.06,
            note="Trend is strong, but latest-session weakness needs confirmation before entry.",
        )

    if abs(return_5d_pct) < 3.0 and volatility_20d_pct >= 2.5:
        return StrategyProfile(
            name="range_reversion_watch",
            confidence=0.45,
            auto_trade_allowed=False,
            stop_loss_pct=0.025,
            take_profit_pct=0.04,
            note="Choppy/range-like setup; needs support/resistance confirmation.",
        )

    if return_5d_pct > 10.0 or return_1d_pct > 7.0:
        return StrategyProfile(
            name="fade_or_news_watch",
            confidence=0.40,
            auto_trade_allowed=False,
            stop_loss_pct=0.025,
            take_profit_pct=0.04,
            note="Extended move may be news-driven; avoid autonomous entry without fresh catalyst review.",
        )

    return StrategyProfile(
        name="general_momentum_watch",
        confidence=0.50,
        auto_trade_allowed=False,
        stop_loss_pct=0.03,
        take_profit_pct=0.06,
        note="Interesting candidate, but the setup does not meet autonomous day-trade criteria.",
    )


def classify_intraday_setup(
    *,
    return_1m_pct: float,
    return_5m_pct: float,
    return_15m_pct: float,
    session_return_pct: float,
    volume_ratio: float,
    volatility_pct: float,
    quote_spread_pct: float,
    risk_flags: Iterable[str],
) -> StrategyProfile:
    """Classify a real-time intraday setup for quick paper entries/exits."""
    flags = set(risk_flags)
    tradable_spread = quote_spread_pct <= 0.10 or quote_spread_pct == 0

    if (
        return_5m_pct > 0.35
        and return_15m_pct > 0.70
        and volume_ratio >= 1.20
        and tradable_spread
    ):
        confidence = min(
            0.95,
            0.60
            + min(return_5m_pct, 2.0) / 8.0
            + min(return_15m_pct, 4.0) / 16.0
            + min(volume_ratio, 4.0) / 18.0,
        )
        return StrategyProfile(
            name="momentum_breakout",
            confidence=round(confidence, 3),
            auto_trade_allowed=True,
            stop_loss_pct=0.018 if volatility_pct < 0.50 else 0.028,
            take_profit_pct=0.040 if volatility_pct < 0.50 else 0.065,
            note="Fast intraday upside momentum with confirming real-time volume.",
        )

    if (
        session_return_pct > 0.80
        and return_15m_pct > 0.25
        and -0.40 <= return_1m_pct <= 0.45
        and volume_ratio >= 0.85
        and tradable_spread
    ):
        confidence = min(
            0.90,
            0.58
            + min(session_return_pct, 5.0) / 25.0
            + min(return_15m_pct, 2.5) / 18.0,
        )
        return StrategyProfile(
            name="relative_strength_continuation",
            confidence=round(confidence, 3),
            auto_trade_allowed=True,
            stop_loss_pct=0.014 if volatility_pct < 0.45 else 0.024,
            take_profit_pct=0.030 if volatility_pct < 0.45 else 0.055,
            note="Intraday relative strength is holding without a stretched latest minute.",
        )

    if return_5m_pct > 1.40 or session_return_pct > 5.0:
        return StrategyProfile(
            name="fade_or_news_watch",
            confidence=0.42,
            auto_trade_allowed=False,
            stop_loss_pct=0.018,
            take_profit_pct=0.035,
            note="Move is extended enough that fresh catalyst review is required.",
        )

    if "wide_spread" in flags or "stale_live_trade" in flags:
        return StrategyProfile(
            name="liquidity_watch",
            confidence=0.35,
            auto_trade_allowed=False,
            stop_loss_pct=0.012,
            take_profit_pct=0.025,
            note="Live trade/quote quality is not clean enough for autonomous entry.",
        )

    return StrategyProfile(
        name="general_momentum_watch",
        confidence=0.48,
        auto_trade_allowed=False,
        stop_loss_pct=0.016,
        take_profit_pct=0.035,
        note="Realtime setup is visible, but not strong enough for autonomous entry.",
    )
