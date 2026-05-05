from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Sequence

import pandas as pd
import yfinance as yf

from tradingagents.dataflows.order_flow import get_alpaca_order_flow_snapshot
from tradingagents.dataflows.utils import safe_ticker_component


DEFAULT_AUTONOMOUS_UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AMD",
    "AVGO",
    "NFLX",
    "PLTR",
    "SMCI",
    "ARM",
    "MU",
    "CRWD",
    "PANW",
    "SNOW",
    "COIN",
    "MSTR",
    "JPM",
    "BAC",
    "GS",
    "V",
    "MA",
    "LLY",
    "NVO",
    "UNH",
    "XOM",
    "CVX",
    "CAT",
    "GE",
    "SPY",
    "QQQ",
    "IWM",
    "TLT",
    "GLD",
    "DIA",
    "XLF",
    "XLK",
    "XLE",
    "XLV",
    "XLY",
    "XLI",
    "ARKK",
    "SOXX",
]

ETF_TICKERS = {
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "TLT",
    "GLD",
    "XLF",
    "XLK",
    "XLE",
    "XLV",
    "XLY",
    "XLI",
    "ARKK",
    "SOXX",
}


@dataclass
class OpportunityCandidate:
    ticker: str
    latest_price: float
    return_1d_pct: float
    return_5d_pct: float
    return_20d_pct: float
    relative_strength_5d_pct: float
    volume_ratio: float
    volatility_20d_pct: float
    price_position_20d: float
    strategy: str
    strategy_confidence: float
    score: float
    data_plan: List[str] = field(default_factory=list)
    catalysts: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    sector: str = ""
    market_cap: float = 0.0
    beta: float = 0.0
    trailing_pe: float = 0.0
    news_headlines: List[str] = field(default_factory=list)
    order_flow: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _SetupProfile:
    name: str
    confidence: float


def _classify_setup(
    *,
    return_1d_pct: float,
    return_5d_pct: float,
    return_20d_pct: float,
    volume_ratio: float,
    volatility_20d_pct: float,
) -> _SetupProfile:
    if return_1d_pct > 2.0 and return_5d_pct > 3.0 and volume_ratio >= 1.05:
        confidence = min(0.95, 0.62 + return_1d_pct / 30.0 + min(volume_ratio, 2.0) / 12.0)
        return _SetupProfile("momentum_breakout", round(confidence, 3))
    if return_5d_pct > 4.0 and return_20d_pct > 10.0 and -1.5 <= return_1d_pct <= 2.0:
        confidence = min(0.90, 0.58 + return_5d_pct / 40.0 + return_20d_pct / 120.0)
        return _SetupProfile("relative_strength_continuation", round(confidence, 3))
    if return_20d_pct > 15.0 and return_1d_pct < -2.0:
        return _SetupProfile("pullback_watch", 0.48)
    if abs(return_5d_pct) < 3.0 and volatility_20d_pct >= 2.5:
        return _SetupProfile("range_reversion_watch", 0.45)
    if return_5d_pct > 10.0 or return_1d_pct > 7.0:
        return _SetupProfile("fade_or_news_watch", 0.40)
    return _SetupProfile("general_momentum_watch", 0.50)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _pct_change(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end - start) / start * 100.0


def _clean_universe(universe: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    cleaned: List[str] = []
    for item in universe:
        ticker = safe_ticker_component(str(item).strip().upper())
        if ticker and ticker not in seen:
            seen.add(ticker)
            cleaned.append(ticker)
    return cleaned


def _history_for_ticker(
    data: pd.DataFrame,
    ticker: str,
    single_ticker: bool,
) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()
    if single_ticker or not isinstance(data.columns, pd.MultiIndex):
        return data.dropna(how="all")
    if ticker not in data.columns.get_level_values(0):
        return pd.DataFrame()
    return data[ticker].dropna(how="all")


def _headline_text(article: Dict[str, Any]) -> str:
    content = article.get("content")
    if isinstance(content, dict):
        return str(content.get("title") or "").strip()
    return str(article.get("title") or "").strip()


def _enrich_ticker(ticker: str, news_limit: int) -> tuple[Dict[str, Any], List[str]]:
    ticker_obj = None
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info or {}
    except Exception:
        info = {}

    headlines: List[str] = []
    try:
        news = ticker_obj.get_news(count=news_limit) if ticker_obj and news_limit > 0 else []
        headlines = [text for text in (_headline_text(item) for item in news) if text]
    except Exception:
        headlines = []

    return info, headlines[:news_limit]


def _data_plan_for_candidate(
    ticker: str,
    *,
    volume_ratio: float,
    volatility_20d_pct: float,
    return_1d_pct: float,
    return_5d_pct: float,
    news_headlines: Sequence[str],
    order_flow: Dict[str, Any],
) -> List[str]:
    plan = ["daily_ohlcv", "technical_indicators"]
    if volume_ratio >= 1.2 or volatility_20d_pct >= 2.5:
        plan.append("live_order_flow")
        plan.append("volume_profile")
    if news_headlines or abs(return_1d_pct) >= 2.0 or abs(return_5d_pct) >= 5.0:
        plan.append("company_news")
    if ticker not in ETF_TICKERS:
        plan.append("fundamentals")
        plan.append("insider_and_copy_trading")
    if order_flow.get("l2_heatmap_available"):
        plan.append("liquidity_heatmap")
    else:
        plan.append("quote_liquidity")
    plan.append("risk_controls")
    return plan


def score_opportunity_candidate(
    ticker: str,
    history: pd.DataFrame,
    benchmark_history: pd.DataFrame | None = None,
    *,
    info: Dict[str, Any] | None = None,
    news_headlines: Sequence[str] | None = None,
    order_flow: Dict[str, Any] | None = None,
    min_price: float = 5.0,
    min_avg_volume: float = 1_000_000,
) -> OpportunityCandidate | None:
    close = history.get("Close", pd.Series(dtype=float)).dropna()
    volume = history.get("Volume", pd.Series(dtype=float)).dropna()
    high = history.get("High", pd.Series(dtype=float)).dropna()
    low = history.get("Low", pd.Series(dtype=float)).dropna()
    if len(close) < 22 or len(volume) < 20:
        return None

    latest = float(close.iloc[-1])
    if latest < min_price:
        return None

    avg_volume = float(volume.tail(20).mean())
    if avg_volume < min_avg_volume:
        return None

    ret_1d = _pct_change(float(close.iloc[-2]), latest)
    ret_5d = _pct_change(float(close.iloc[-6]), latest)
    ret_20d = _pct_change(float(close.iloc[-21]), latest)
    daily_returns = close.pct_change().dropna().tail(20)
    vol_20d = float(daily_returns.std() * 100.0) if len(daily_returns) else 0.0
    volume_ratio = float(volume.iloc[-1]) / avg_volume if avg_volume else 0.0

    benchmark_ret_5d = 0.0
    if benchmark_history is not None and not benchmark_history.empty:
        benchmark_close = benchmark_history.get("Close", pd.Series(dtype=float)).dropna()
        if len(benchmark_close) >= 6:
            benchmark_ret_5d = _pct_change(float(benchmark_close.iloc[-6]), float(benchmark_close.iloc[-1]))
    relative_strength = ret_5d - benchmark_ret_5d

    recent_low = float(low.tail(20).min()) if len(low) >= 20 else float(close.tail(20).min())
    recent_high = float(high.tail(20).max()) if len(high) >= 20 else float(close.tail(20).max())
    price_position = (
        (latest - recent_low) / (recent_high - recent_low)
        if recent_high > recent_low
        else 0.5
    )

    info = info or {}
    headlines = list(news_headlines or [])
    order_flow = order_flow or {}
    delta_ratio = _safe_float(order_flow.get("delta_ratio"))
    quote = order_flow.get("latest_quote", {}) if isinstance(order_flow, dict) else {}
    spread = _safe_float(quote.get("spread"))
    spread_pct = spread / latest * 100.0 if latest and spread else 0.0

    setup = _classify_setup(
        return_1d_pct=ret_1d,
        return_5d_pct=ret_5d,
        return_20d_pct=ret_20d,
        volume_ratio=volume_ratio,
        volatility_20d_pct=vol_20d,
    )

    score = (
        ret_5d * 0.32
        + ret_20d * 0.16
        + relative_strength * 0.26
        + max(0.0, min(volume_ratio - 1.0, 3.0)) * 3.0
        + (price_position - 0.5) * 2.0
        + min(len(headlines), 4) * 0.6
        + delta_ratio * 2.0
        - max(0.0, vol_20d - 4.5) * 0.55
        - max(0.0, spread_pct - 0.08) * 8.0
    )

    risk_flags: List[str] = []
    catalysts: List[str] = []
    if volume_ratio >= 1.8:
        catalysts.append("unusual_volume")
    if ret_5d > 3.0 and relative_strength > 1.0:
        catalysts.append("relative_strength")
    if ret_1d > 2.0:
        catalysts.append("fresh_momentum")
    if headlines:
        catalysts.append("recent_news")
    if delta_ratio > 0.15:
        catalysts.append("positive_order_flow_delta")
    if delta_ratio < -0.15:
        risk_flags.append("negative_order_flow_delta")
    if vol_20d > 4.5:
        risk_flags.append("high_volatility")
    if ret_5d > 15.0:
        risk_flags.append("extended_5d_move")
    if ret_1d < -2.0:
        risk_flags.append("weak_latest_session")
    if spread_pct > 0.08:
        risk_flags.append("wide_spread")
    if ticker in ETF_TICKERS:
        catalysts.append("market_or_sector_proxy")

    data_plan = _data_plan_for_candidate(
        ticker,
        volume_ratio=volume_ratio,
        volatility_20d_pct=vol_20d,
        return_1d_pct=ret_1d,
        return_5d_pct=ret_5d,
        news_headlines=headlines,
        order_flow=order_flow,
    )

    return OpportunityCandidate(
        ticker=ticker,
        latest_price=round(latest, 4),
        return_1d_pct=round(ret_1d, 3),
        return_5d_pct=round(ret_5d, 3),
        return_20d_pct=round(ret_20d, 3),
        relative_strength_5d_pct=round(relative_strength, 3),
        volume_ratio=round(volume_ratio, 3),
        volatility_20d_pct=round(vol_20d, 3),
        price_position_20d=round(price_position, 3),
        strategy=setup.name,
        strategy_confidence=round(setup.confidence, 3),
        score=round(score, 3),
        data_plan=data_plan,
        catalysts=catalysts or ["watchlist_baseline"],
        risk_flags=risk_flags,
        sector=str(info.get("sector") or info.get("category") or ""),
        market_cap=_safe_float(info.get("marketCap")),
        beta=_safe_float(info.get("beta")),
        trailing_pe=_safe_float(info.get("trailingPE")),
        news_headlines=headlines[:3],
        order_flow={
            key: order_flow.get(key)
            for key in (
                "status",
                "delta_ratio",
                "point_of_control",
                "total_volume",
                "absorption_flags",
                "l2_heatmap_available",
            )
            if key in order_flow
        },
    )


def build_autonomous_stock_selection(
    *,
    universe: Sequence[str] | None = None,
    limit: int = 10,
    max_universe: int = 45,
    history_period: str = "90d",
    enrichment_limit: int = 12,
    order_flow_limit: int = 3,
    include_live_order_flow: bool = True,
    min_price: float = 5.0,
    min_avg_volume: float = 1_000_000,
) -> Dict[str, Any]:
    tickers = _clean_universe(universe or DEFAULT_AUTONOMOUS_UNIVERSE)
    tickers = tickers[: max(5, max_universe)]
    benchmark = "SPY"
    download_tickers = _clean_universe([*tickers, benchmark])

    data = yf.download(
        tickers=download_tickers,
        period=history_period,
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    benchmark_history = _history_for_ticker(
        data,
        benchmark,
        len(download_tickers) == 1,
    )

    base_candidates: List[OpportunityCandidate] = []
    for ticker in tickers:
        history = _history_for_ticker(data, ticker, len(download_tickers) == 1)
        candidate = score_opportunity_candidate(
            ticker,
            history,
            benchmark_history,
            min_price=min_price,
            min_avg_volume=min_avg_volume,
        )
        if candidate:
            base_candidates.append(candidate)

    pre_ranked = sorted(base_candidates, key=lambda item: item.score, reverse=True)
    enriched: List[OpportunityCandidate] = []
    for index, candidate in enumerate(pre_ranked[: max(limit, enrichment_limit)]):
        info, headlines = _enrich_ticker(candidate.ticker, news_limit=3)
        order_flow: Dict[str, Any] = {}
        if include_live_order_flow and index < order_flow_limit:
            try:
                order_flow = get_alpaca_order_flow_snapshot(candidate.ticker)
            except Exception as exc:
                order_flow = {"status": "unavailable", "reason": str(exc)}

        history = _history_for_ticker(data, candidate.ticker, len(download_tickers) == 1)
        rescored = score_opportunity_candidate(
            candidate.ticker,
            history,
            benchmark_history,
            info=info,
            news_headlines=headlines,
            order_flow=order_flow,
            min_price=min_price,
            min_avg_volume=min_avg_volume,
        )
        if rescored:
            enriched.append(rescored)

    final_ranked = sorted(enriched or pre_ranked, key=lambda item: item.score, reverse=True)
    selected = final_ranked[: max(1, limit)]
    return {
        "primary_ticker": selected[0].ticker if selected else "",
        "candidate_count": len(final_ranked),
        "scanned_universe": tickers,
        "benchmark": benchmark,
        "history_period": history_period,
        "selection_method": (
            "Ranks liquid tickers by momentum, SPY-relative strength, unusual "
            "volume, volatility quality, news enrichment, fundamentals metadata, "
            "and available live order-flow signals."
        ),
        "candidates": [asdict(candidate) for candidate in selected],
    }
