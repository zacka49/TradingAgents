from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf
from requests import HTTPError

from tradingagents.agents.utils.market_scanner_tools import DEFAULT_DISCOVERY_UNIVERSE
from tradingagents.company.agent_learning import (
    SpecialistMemoryLog,
    build_agent_scorecards,
    render_agent_scorecards_markdown,
)
from tradingagents.company.backtest_lab import run_momentum_smoke_backtest
from tradingagents.company.day_trading_strategy import (
    StrategyProfile,
    classify_day_trade_setup,
    classify_intraday_setup,
)
from tradingagents.company.technology_scout import (
    build_technology_capabilities,
    capabilities_as_dicts,
    render_technology_scout_report,
)
from tradingagents.dataflows.alpaca_realtime import (
    get_intraday_bars,
    get_latest_quotes,
    get_latest_trades,
    get_snapshots,
)
from tradingagents.dataflows.news_politics_discovery import (
    discover_news_politics_symbols,
)
from tradingagents.dataflows.order_flow import get_alpaca_order_flow_snapshot
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.execution import AlpacaPaperBroker, OrderIntent, evaluate_order_policy
from tradingagents.llm_clients.compute_policy import (
    apply_compute_policy,
    hosted_llm_allowed,
    is_cloud_ollama_model,
    is_local_url,
)


@dataclass
class MarketCandidate:
    ticker: str
    latest_price: float
    return_1d_pct: float
    return_5d_pct: float
    return_20d_pct: float
    volume_ratio: float
    volatility_20d_pct: float
    score: float
    risk_flags: List[str]
    strategy: str
    strategy_confidence: float
    strategy_note: str
    auto_trade_allowed: bool
    stop_loss_pct: float
    take_profit_pct: float
    backtest_return_pct: float = 0.0
    backtest_benchmark_pct: float = 0.0
    backtest_excess_pct: float = 0.0
    backtest_max_drawdown_pct: float = 0.0
    backtest_trades: int = 0
    backtest_passed: bool = True
    backtest_note: str = ""
    strategy_profile: str = "balanced"
    data_source: str = "daily"
    intraday_return_1m_pct: float = 0.0
    intraday_return_5m_pct: float = 0.0
    intraday_return_15m_pct: float = 0.0
    intraday_session_return_pct: float = 0.0
    realtime_volume_ratio: float = 0.0
    quote_spread_pct: float = 0.0
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_size: float = 0.0
    ask_size: float = 0.0
    quote_imbalance: float = 0.0
    latest_trade_time: str = ""
    latest_quote_time: str = ""
    minute_bar_volume: float = 0.0
    daily_bar_volume: float = 0.0
    previous_close: float = 0.0
    prev_close_return_pct: float = 0.0
    order_flow_delta_ratio: float = 0.0
    order_flow_absorption_flags: List[str] = field(default_factory=list)
    news_catalysts: List[str] = field(default_factory=list)
    news_headlines: List[str] = field(default_factory=list)
    political_themes: List[str] = field(default_factory=list)
    catalyst_tags: List[str] = field(default_factory=list)
    catalyst_direction: str = ""
    news_risk_tags: List[str] = field(default_factory=list)
    premarket_research_action: str = ""
    premarket_thesis: str = ""
    day_trade_fit_score: float = 0.0
    day_trade_fit_reasons: List[str] = field(default_factory=list)
    live_market: Dict[str, Any] = field(default_factory=dict)
    realtime_note: str = ""


@dataclass
class PortfolioOrderPlan:
    ticker: str
    side: str
    quantity: float
    latest_price: float
    estimated_notional_usd: float
    reason: str
    strategy: str = ""
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    submitted: bool = False
    blocked_reason: str | None = None
    order_response: Dict[str, Any] | None = None


@dataclass
class CompanyRunResult:
    account_status: str
    market_open: bool
    artifact_dir: str
    candidates: List[MarketCandidate]
    target_weights: Dict[str, float]
    order_plans: List[PortfolioOrderPlan]
    submitted_orders: int
    blocked_orders: int


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _response_text(response: Any) -> str | None:
    if response is None:
        return None
    text = getattr(response, "text", None)
    if text:
        return str(text)[:500]
    try:
        return json.dumps(response.json())[:500]
    except Exception:
        return None


def _pct_change(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end - start) / start * 100.0


def _md_cell(value: Any, *, max_len: int = 120) -> str:
    text = str(value or "").replace("|", "/").replace("\n", " ").strip()
    if len(text) > max_len:
        return f"{text[: max_len - 3]}..."
    return text


def _clean_universe(universe: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    cleaned: List[str] = []
    for item in universe:
        ticker = safe_ticker_component(str(item).strip().upper())
        if ticker and ticker not in seen:
            seen.add(ticker)
            cleaned.append(ticker)
    return cleaned


def _floor_quantity(value: float, precision: int = 4) -> float:
    factor = 10**precision
    return math.floor(max(0.0, float(value)) * factor) / factor


class CodexCEOCompanyRunner:
    """Compute-light company runner for Codex CEO mode.

    This workflow is intentionally smaller than the full multi-agent graph:
    market screening is deterministic, the optional local Ollama staff memo is
    one short call, and paper execution stays behind explicit guardrails.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        broker: AlpacaPaperBroker | None = None,
    ) -> None:
        self.config = apply_compute_policy(config)
        self.broker = broker or AlpacaPaperBroker()
        self._last_catalyst_context: Dict[str, Any] = {}
        self._last_order_plan_diagnostics: List[Dict[str, Any]] = []

    def run(
        self,
        *,
        trade_date: str | None = None,
        universe: Sequence[str] | None = None,
        submit: bool = False,
        ceo_approved: bool = False,
    ) -> CompanyRunResult:
        trade_date = trade_date or datetime.now(UTC).strftime("%Y-%m-%d")
        candidates = self.scan_market(universe or self.config.get("codex_ceo_universe", []))

        account = self.broker.get_account()
        positions_payload = self.broker.get_positions()
        positions = positions_payload.get("positions", [])
        open_orders_payload = self._get_open_orders()
        open_orders = open_orders_payload.get("orders", [])
        clock = self.broker.get_clock()

        target_weights = self.build_target_weights(candidates)
        order_plans = self.build_order_plans(
            candidates=candidates,
            target_weights=target_weights,
            account=account,
            positions=positions,
            open_orders=open_orders,
        )
        self.apply_order_plans(
            order_plans,
            account=account,
            market_open=bool(clock.get("is_open")),
            submit=submit,
            ceo_approved=ceo_approved,
        )

        artifact_dir = self._artifact_dir(trade_date)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        staff_memo = self.create_ollama_staff_memo(candidates, order_plans)
        technology_capabilities = []
        technology_scout_report = ""
        if self.config.get("technology_scout_enabled", True):
            technology_capabilities = build_technology_capabilities(
                project_root=self._project_root(),
                ollama_base_url=str(self.config.get("ollama_base_url", "http://localhost:11434")),
            )
            technology_scout_report = render_technology_scout_report(
                technology_capabilities
            )
        self.write_artifacts(
            artifact_dir=artifact_dir,
            trade_date=trade_date,
            account=account,
            positions=positions,
            open_orders=open_orders,
            clock=clock,
            candidates=candidates,
            target_weights=target_weights,
            order_plans=order_plans,
            staff_memo=staff_memo,
            technology_capabilities=technology_capabilities,
            technology_scout_report=technology_scout_report,
            submit=submit,
            ceo_approved=ceo_approved,
        )

        submitted = sum(1 for order in order_plans if order.submitted)
        blocked = sum(1 for order in order_plans if order.blocked_reason)
        return CompanyRunResult(
            account_status=str(account.get("status", "unknown")),
            market_open=bool(clock.get("is_open")),
            artifact_dir=str(artifact_dir),
            candidates=candidates,
            target_weights=target_weights,
            order_plans=order_plans,
            submitted_orders=submitted,
            blocked_orders=blocked,
        )

    def scan_market(self, universe: Sequence[str] | None = None) -> List[MarketCandidate]:
        tickers = _clean_universe(universe or DEFAULT_DISCOVERY_UNIVERSE)
        max_universe = int(self.config.get("codex_ceo_max_universe", 30))
        if self.config.get("codex_ceo_news_political_scan_enabled", True):
            max_universe = max(
                max_universe,
                int(self.config.get("codex_ceo_news_political_max_symbols", max_universe)),
            )
        tickers = self._expand_universe_with_news_politics(
            tickers,
            max_symbols=max(5, max_universe),
        )
        tickers = tickers[: max(5, max_universe)]
        limit = int(self.config.get("codex_ceo_watchlist_size", 10))

        if self.config.get("codex_ceo_realtime_scan_enabled", False):
            try:
                realtime_candidates = self._scan_market_realtime(tickers)
                if realtime_candidates:
                    return realtime_candidates[: max(1, limit)]
            except Exception:
                if not self.config.get("codex_ceo_realtime_fallback_to_daily", True):
                    raise

        lookback_days = str(self.config.get("codex_ceo_history_period", "60d"))

        data = yf.download(
            tickers=tickers,
            period=lookback_days,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        candidates: List[MarketCandidate] = []
        for ticker in tickers:
            history = self._history_for_ticker(data, ticker, len(tickers) == 1)
            if history.empty or len(history) < 22:
                continue
            candidate = self._score_ticker(ticker, history)
            if candidate is not None:
                self._apply_catalyst_context(candidate)
                candidates.append(candidate)

        ranked = sorted(candidates, key=lambda item: item.score, reverse=True)
        return ranked[: max(1, limit)]

    def _expand_universe_with_news_politics(
        self,
        tickers: Sequence[str],
        *,
        max_symbols: int,
    ) -> List[str]:
        self._last_catalyst_context = {}
        if not self.config.get("codex_ceo_news_political_scan_enabled", True):
            return list(tickers)

        configured_max = int(
            self.config.get("codex_ceo_news_political_max_symbols", max_symbols)
        )
        queries = self.config.get("codex_ceo_news_political_queries", [])
        try:
            context = discover_news_politics_symbols(
                tickers,
                queries=queries or None,
                max_symbols=max(configured_max, max_symbols),
                articles_per_query=int(
                    self.config.get("codex_ceo_news_political_articles_per_query", 8)
                ),
            )
        except Exception as exc:
            if not self.config.get("codex_ceo_news_political_fallback_to_base", True):
                raise
            self._last_catalyst_context = {
                "symbols": list(tickers),
                "base_symbols": list(tickers),
                "added_symbols": [],
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
            return list(tickers)

        self._last_catalyst_context = context
        expanded = context.get("symbols") or list(tickers)
        return _clean_universe(expanded)

    def _apply_catalyst_context(self, candidate: MarketCandidate) -> None:
        context = self._last_catalyst_context or {}
        symbol = candidate.ticker
        catalysts = [
            str(item)
            for item in context.get("catalysts_by_symbol", {}).get(symbol, [])
            if str(item)
        ]
        themes = [
            str(item)
            for item in context.get("themes_by_symbol", {}).get(symbol, [])
            if str(item)
        ]
        headlines = [
            str(item)
            for item in context.get("headlines_by_symbol", {}).get(symbol, [])
            if str(item)
        ]
        risk_headlines = [
            str(item)
            for item in context.get("risk_headlines_by_symbol", {}).get(symbol, [])
            if str(item)
        ]
        catalyst_tags = [
            str(item)
            for item in context.get("catalyst_tags_by_symbol", {}).get(symbol, [])
            if str(item)
        ]
        risk_tags = [
            str(item)
            for item in context.get("risk_tags_by_symbol", {}).get(symbol, [])
            if str(item)
        ]
        research = (
            context.get("day_trade_research_by_symbol", {}).get(symbol, {})
            if isinstance(context.get("day_trade_research_by_symbol"), dict)
            else {}
        )

        if not (catalysts or themes or headlines or risk_headlines or catalyst_tags or research):
            return

        candidate.news_catalysts = sorted(set([*candidate.news_catalysts, *catalysts]))
        candidate.political_themes = sorted(set([*candidate.political_themes, *themes]))
        candidate.news_headlines = [*candidate.news_headlines, *headlines][:3]
        candidate.catalyst_tags = sorted(set([*candidate.catalyst_tags, *catalyst_tags]))
        candidate.news_risk_tags = sorted(set([*candidate.news_risk_tags, *risk_tags]))
        direction = str(
            research.get("direction")
            or context.get("directions_by_symbol", {}).get(symbol, "")
            or ""
        )
        if direction and direction != "unknown":
            candidate.catalyst_direction = direction
        action = str(research.get("action") or "")
        if action:
            candidate.premarket_research_action = action
            if action not in candidate.day_trade_fit_reasons:
                candidate.day_trade_fit_reasons.append(action)
        thesis = str(research.get("thesis") or "")
        if thesis:
            candidate.premarket_thesis = thesis

        catalyst_score = _safe_float(context.get("scores", {}).get(symbol))
        bonus_per_point = float(self.config.get("codex_ceo_news_catalyst_score_bonus", 0.25))
        max_bonus = float(self.config.get("codex_ceo_news_catalyst_max_bonus", 1.5))
        if catalyst_score > 0:
            candidate.score = round(
                candidate.score + min(max_bonus, catalyst_score * bonus_per_point),
                3,
            )
            candidate.day_trade_fit_score = round(
                candidate.day_trade_fit_score
                + min(
                    float(self.config.get("codex_ceo_news_day_trade_fit_max_bonus", 2.0)),
                    catalyst_score
                    * float(self.config.get("codex_ceo_news_day_trade_fit_bonus", 0.20)),
                ),
                3,
            )

        if (risk_headlines or risk_tags) and "news_risk" not in candidate.risk_flags:
            candidate.risk_flags.append("news_risk")

    def _scan_market_realtime(self, tickers: Sequence[str]) -> List[MarketCandidate]:
        lookback_minutes = int(self.config.get("codex_ceo_realtime_lookback_minutes", 90))
        feed = self.config.get("alpaca_stock_feed") or None
        bars_by_ticker = get_intraday_bars(
            tickers,
            lookback_minutes=lookback_minutes,
            feed=feed,
            timeout=int(self.config.get("alpaca_data_timeout_seconds", 20)),
        )
        latest_trades = get_latest_trades(
            tickers,
            feed=feed,
            timeout=int(self.config.get("alpaca_data_timeout_seconds", 20)),
        )
        latest_quotes = get_latest_quotes(
            tickers,
            feed=feed,
            timeout=int(self.config.get("alpaca_data_timeout_seconds", 20)),
        )
        try:
            snapshots = get_snapshots(
                tickers,
                feed=feed,
                timeout=int(self.config.get("alpaca_data_timeout_seconds", 20)),
            )
        except Exception:
            snapshots = {}

        candidates = []
        for ticker in tickers:
            snapshot = snapshots.get(ticker, {})
            candidate = self._score_realtime_ticker(
                ticker,
                bars_by_ticker.get(ticker, []),
                latest_trades.get(ticker, {}) or snapshot.get("latestTrade", {}),
                latest_quotes.get(ticker, {}) or snapshot.get("latestQuote", {}),
                snapshot=snapshot,
            )
            if candidate is not None:
                self._apply_catalyst_context(candidate)
                candidates.append(candidate)

        ranked = sorted(candidates, key=lambda item: item.score, reverse=True)
        self._enrich_order_flow_candidates(ranked)
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    def _history_for_ticker(
        self,
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

    def _day_trade_fit(
        self,
        *,
        latest_price: float,
        avg_volume: float = 0.0,
        volume_ratio: float,
        volatility_pct: float,
        return_1d_pct: float,
        return_5d_pct: float = 0.0,
        spread_pct: float | None = None,
        recent_volume: float = 0.0,
    ) -> tuple[float, List[str]]:
        score = 0.0
        reasons: List[str] = []
        min_price = float(self.config.get("codex_ceo_min_price", 5.0))
        min_avg_volume = float(self.config.get("codex_ceo_min_avg_volume", 1_000_000))
        preferred_volume_ratio = float(
            self.config.get("codex_ceo_day_trade_preferred_min_volume_ratio", 1.05)
        )
        preferred_min_volatility = float(
            self.config.get("codex_ceo_day_trade_preferred_min_volatility_pct", 0.6)
        )
        preferred_max_volatility = float(
            self.config.get("codex_ceo_day_trade_preferred_max_volatility_pct", 4.5)
        )
        min_abs_move = float(
            self.config.get("codex_ceo_day_trade_min_abs_move_pct", 1.0)
        )

        if latest_price >= min_price:
            score += 1.0
            reasons.append("tradable_price")
        if avg_volume >= min_avg_volume:
            score += 1.0
            reasons.append("baseline_liquidity")
        if avg_volume >= max(min_avg_volume * 5.0, 5_000_000):
            score += 0.75
            reasons.append("deep_liquidity")
        if recent_volume >= float(
            self.config.get("codex_ceo_realtime_min_recent_volume", 2_500)
        ):
            score += 0.75
            reasons.append("fresh_volume")
        if volume_ratio >= preferred_volume_ratio:
            score += 1.0
            reasons.append("relative_volume_confirmed")
        if volume_ratio >= 1.5:
            score += 0.75
            reasons.append("strong_relative_volume")
        if preferred_min_volatility <= volatility_pct <= preferred_max_volatility:
            score += 1.0
            reasons.append("useful_volatility")
        elif volatility_pct > preferred_max_volatility:
            reasons.append("volatility_requires_smaller_size")
        if abs(return_1d_pct) >= min_abs_move or abs(return_5d_pct) >= min_abs_move * 3:
            score += 1.0
            reasons.append("meaningful_price_movement")
        if spread_pct is not None:
            max_spread = float(self.config.get("codex_ceo_realtime_max_spread_pct", 0.12))
            if 0 <= spread_pct <= max_spread:
                score += 1.25
                reasons.append("tight_live_spread")
            elif spread_pct > max_spread:
                reasons.append("spread_too_wide_for_day_trade")
        return round(score, 3), reasons

    def _score_ticker(self, ticker: str, history: pd.DataFrame) -> MarketCandidate | None:
        close = history.get("Close", pd.Series(dtype=float)).dropna()
        volume = history.get("Volume", pd.Series(dtype=float)).dropna()
        if len(close) < 22:
            return None

        latest = float(close.iloc[-1])
        if latest < float(self.config.get("codex_ceo_min_price", 5.0)):
            return None

        avg_volume = float(volume.tail(20).mean()) if len(volume) >= 20 else 0.0
        if avg_volume < float(self.config.get("codex_ceo_min_avg_volume", 1_000_000)):
            return None

        ret_1d = _pct_change(float(close.iloc[-2]), latest)
        ret_5d = _pct_change(float(close.iloc[-6]), latest)
        ret_20d = _pct_change(float(close.iloc[-21]), latest)
        daily_returns = close.pct_change().dropna().tail(20)
        vol_20d = float(daily_returns.std() * 100.0) if len(daily_returns) else 0.0
        latest_volume = float(volume.iloc[-1]) if len(volume) else 0.0
        volume_ratio = latest_volume / avg_volume if avg_volume else 0.0

        score = (
            ret_1d * 0.35
            + ret_5d * 0.45
            + ret_20d * 0.20
            + max(0.0, min(volume_ratio - 1.0, 2.0)) * 2.0
            - max(0.0, vol_20d - 3.0) * 0.6
        )
        risk_flags: List[str] = []
        if vol_20d > 4.0:
            risk_flags.append("high_volatility")
        if ret_5d > 15.0:
            risk_flags.append("extended_5d_move")
        if ret_1d < -2.0:
            risk_flags.append("weak_latest_session")
        if volume_ratio > 2.5:
            risk_flags.append("volume_spike")
        day_trade_fit_score, day_trade_fit_reasons = self._day_trade_fit(
            latest_price=latest,
            avg_volume=avg_volume,
            volume_ratio=volume_ratio,
            volatility_pct=vol_20d,
            return_1d_pct=ret_1d,
            return_5d_pct=ret_5d,
        )

        strategy = classify_day_trade_setup(
            return_1d_pct=ret_1d,
            return_5d_pct=ret_5d,
            return_20d_pct=ret_20d,
            volume_ratio=volume_ratio,
            volatility_20d_pct=vol_20d,
            risk_flags=risk_flags,
        )
        backtest = None
        if self.config.get("backtest_lab_enabled", True):
            backtest = run_momentum_smoke_backtest(
                ticker=ticker,
                history=history,
                min_bars=int(self.config.get("backtest_lab_min_bars", 40)),
                min_strategy_return_pct=float(
                    self.config.get("backtest_lab_min_strategy_return_pct", -10.0)
                ),
                min_excess_return_pct=float(
                    self.config.get("backtest_lab_min_excess_return_pct", -8.0)
                ),
            )
            score += max(-4.0, min(4.0, backtest.excess_return_pct * 0.08))
            if not backtest.passed:
                risk_flags.append("weak_backtest")
            min_closed_trades = int(self.config.get("backtest_lab_min_closed_trades", 0))
            if backtest.trade_count < min_closed_trades:
                risk_flags.append("insufficient_backtest_trades")

        (
            auto_trade_allowed,
            stop_loss_pct,
            take_profit_pct,
            strategy_note,
        ) = self._profile_strategy_controls(strategy, risk_flags)

        return MarketCandidate(
            ticker=ticker,
            latest_price=round(latest, 4),
            return_1d_pct=round(ret_1d, 3),
            return_5d_pct=round(ret_5d, 3),
            return_20d_pct=round(ret_20d, 3),
            volume_ratio=round(volume_ratio, 3),
            volatility_20d_pct=round(vol_20d, 3),
            score=round(score, 3),
            risk_flags=risk_flags,
            strategy=strategy.name,
            strategy_confidence=strategy.confidence,
            strategy_note=strategy_note,
            auto_trade_allowed=auto_trade_allowed,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            backtest_return_pct=backtest.strategy_return_pct if backtest else 0.0,
            backtest_benchmark_pct=backtest.buy_hold_return_pct if backtest else 0.0,
            backtest_excess_pct=backtest.excess_return_pct if backtest else 0.0,
            backtest_max_drawdown_pct=backtest.max_drawdown_pct if backtest else 0.0,
            backtest_trades=backtest.trade_count if backtest else 0,
            backtest_passed=backtest.passed if backtest else True,
            backtest_note=backtest.note if backtest else "",
            strategy_profile=str(self.config.get("strategy_profile_name", "balanced")),
            day_trade_fit_score=day_trade_fit_score,
            day_trade_fit_reasons=day_trade_fit_reasons,
        )

    def _score_realtime_ticker(
        self,
        ticker: str,
        bars: Sequence[Dict[str, Any]],
        latest_trade: Dict[str, Any],
        latest_quote: Dict[str, Any],
        *,
        snapshot: Dict[str, Any] | None = None,
    ) -> MarketCandidate | None:
        snapshot = snapshot or {}
        latest_trade = latest_trade or snapshot.get("latestTrade", {}) or {}
        latest_quote = latest_quote or snapshot.get("latestQuote", {}) or {}
        minute_bar = snapshot.get("minuteBar", {}) if isinstance(snapshot, dict) else {}
        daily_bar = snapshot.get("dailyBar", {}) if isinstance(snapshot, dict) else {}
        prev_daily_bar = snapshot.get("prevDailyBar", {}) if isinstance(snapshot, dict) else {}
        bars = self._prefer_regular_session_bars(bars)
        if len(bars) < 3:
            return None

        closes = [_safe_float(bar.get("c")) for bar in bars if _safe_float(bar.get("c")) > 0]
        volumes = [_safe_float(bar.get("v")) for bar in bars if _safe_float(bar.get("v")) >= 0]
        if len(closes) < 3:
            return None

        trade_price = _safe_float(latest_trade.get("p"))
        latest = trade_price if trade_price > 0 else closes[-1]
        if latest < float(self.config.get("codex_ceo_min_price", 5.0)):
            return None

        recent_volume = sum(volumes[-5:]) if volumes else 0.0
        if recent_volume < float(self.config.get("codex_ceo_realtime_min_recent_volume", 2_500)):
            return None

        open_price = _safe_float(bars[0].get("o"), closes[0]) or closes[0]
        return_1m = _pct_change(closes[-2], latest)
        return_5m = _pct_change(closes[-min(6, len(closes))], latest)
        return_15m = _pct_change(closes[-min(16, len(closes))], latest)
        session_return = _pct_change(open_price, latest)

        base_volumes = volumes[:-5] if len(volumes) > 6 else volumes
        base_volume = sum(base_volumes) / max(1, len(base_volumes))
        recent_avg_volume = recent_volume / min(5, max(1, len(volumes)))
        volume_ratio = recent_avg_volume / base_volume if base_volume else 0.0

        minute_returns = [
            _pct_change(closes[index - 1], closes[index])
            for index in range(1, len(closes))
            if closes[index - 1] > 0
        ][-20:]
        volatility = (
            float(pd.Series(minute_returns).std()) if len(minute_returns) >= 2 else 0.0
        )

        bid = _safe_float(latest_quote.get("bp"))
        ask = _safe_float(latest_quote.get("ap"))
        bid_size = _safe_float(latest_quote.get("bs"))
        ask_size = _safe_float(latest_quote.get("as"))
        midpoint = (bid + ask) / 2 if bid > 0 and ask > 0 and ask >= bid else 0.0
        spread_pct = ((ask - bid) / midpoint * 100.0) if midpoint else 0.0
        quote_imbalance = (
            (bid_size - ask_size) / (bid_size + ask_size)
            if bid_size + ask_size > 0
            else 0.0
        )
        previous_close = _safe_float(prev_daily_bar.get("c"))
        prev_close_return = _pct_change(previous_close, latest) if previous_close else 0.0
        live_market = {
            "feed": self.config.get("alpaca_stock_feed") or "env_default",
            "latest_trade": {
                "price": _safe_float(latest_trade.get("p")),
                "size": _safe_float(latest_trade.get("s")),
                "timestamp": latest_trade.get("t"),
                "exchange": latest_trade.get("x"),
                "conditions": latest_trade.get("c", []),
            },
            "latest_quote": {
                "bid_price": bid,
                "ask_price": ask,
                "bid_size": bid_size,
                "ask_size": ask_size,
                "quote_imbalance": round(quote_imbalance, 4),
                "timestamp": latest_quote.get("t"),
            },
            "minute_bar": {
                "open": _safe_float(minute_bar.get("o")),
                "high": _safe_float(minute_bar.get("h")),
                "low": _safe_float(minute_bar.get("l")),
                "close": _safe_float(minute_bar.get("c")),
                "volume": _safe_float(minute_bar.get("v")),
                "vwap": _safe_float(minute_bar.get("vw")),
                "timestamp": minute_bar.get("t"),
            },
            "daily_bar": {
                "open": _safe_float(daily_bar.get("o")),
                "high": _safe_float(daily_bar.get("h")),
                "low": _safe_float(daily_bar.get("l")),
                "close": _safe_float(daily_bar.get("c")),
                "volume": _safe_float(daily_bar.get("v")),
                "vwap": _safe_float(daily_bar.get("vw")),
                "timestamp": daily_bar.get("t"),
            },
            "prev_daily_bar": {
                "close": previous_close,
                "volume": _safe_float(prev_daily_bar.get("v")),
                "timestamp": prev_daily_bar.get("t"),
            },
        }
        live_note_prefix = (
            "Alpaca snapshot, latest trade/quote, and"
            if snapshot
            else "Alpaca latest trade/quote and"
        )

        risk_flags: List[str] = []
        if spread_pct > float(self.config.get("codex_ceo_realtime_max_spread_pct", 0.12)):
            risk_flags.append("wide_spread")
        if volatility > float(self.config.get("codex_ceo_realtime_high_volatility_pct", 0.85)):
            risk_flags.append("high_volatility")
        if volume_ratio > 4.0:
            risk_flags.append("volume_spike")
        if self._trade_age_seconds(latest_trade) > int(
            self.config.get("codex_ceo_realtime_max_trade_age_seconds", 180)
        ):
            risk_flags.append("stale_live_trade")
        day_trade_fit_score, day_trade_fit_reasons = self._day_trade_fit(
            latest_price=latest,
            avg_volume=_safe_float(prev_daily_bar.get("v")),
            volume_ratio=volume_ratio,
            volatility_pct=volatility,
            return_1d_pct=session_return,
            return_5d_pct=return_15m,
            spread_pct=spread_pct,
            recent_volume=recent_volume,
        )

        score = (
            return_1m * 0.30
            + return_5m * 0.65
            + return_15m * 0.45
            + session_return * 0.20
            + max(0.0, min(volume_ratio - 1.0, 4.0)) * 0.75
            - max(0.0, spread_pct - 0.04) * 8.0
            - max(0.0, volatility - 0.45) * 1.5
        )

        strategy = self._opening_range_strategy(
            bars=bars,
            latest_price=latest,
            return_5m_pct=return_5m,
            volume_ratio=volume_ratio,
            volatility_pct=volatility,
            quote_spread_pct=spread_pct,
        ) or classify_intraday_setup(
            return_1m_pct=return_1m,
            return_5m_pct=return_5m,
            return_15m_pct=return_15m,
            session_return_pct=session_return,
            volume_ratio=volume_ratio,
            volatility_pct=volatility,
            quote_spread_pct=spread_pct,
            risk_flags=risk_flags,
        )
        (
            auto_trade_allowed,
            stop_loss_pct,
            take_profit_pct,
            strategy_note,
        ) = self._profile_strategy_controls(strategy, risk_flags)

        return MarketCandidate(
            ticker=ticker,
            latest_price=round(latest, 4),
            return_1d_pct=round(return_5m, 3),
            return_5d_pct=round(return_15m, 3),
            return_20d_pct=round(session_return, 3),
            volume_ratio=round(volume_ratio, 3),
            volatility_20d_pct=round(volatility, 3),
            score=round(score, 3),
            risk_flags=risk_flags,
            strategy=strategy.name,
            strategy_confidence=strategy.confidence,
            strategy_note=strategy_note,
            auto_trade_allowed=auto_trade_allowed,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            strategy_profile=str(self.config.get("strategy_profile_name", "balanced")),
            data_source="alpaca_realtime",
            intraday_return_1m_pct=round(return_1m, 3),
            intraday_return_5m_pct=round(return_5m, 3),
            intraday_return_15m_pct=round(return_15m, 3),
            intraday_session_return_pct=round(session_return, 3),
            realtime_volume_ratio=round(volume_ratio, 3),
            quote_spread_pct=round(spread_pct, 4),
            bid_price=round(bid, 4),
            ask_price=round(ask, 4),
            bid_size=round(bid_size, 4),
            ask_size=round(ask_size, 4),
            quote_imbalance=round(quote_imbalance, 4),
            latest_trade_time=str(latest_trade.get("t") or ""),
            latest_quote_time=str(latest_quote.get("t") or ""),
            minute_bar_volume=round(_safe_float(minute_bar.get("v")), 4),
            daily_bar_volume=round(_safe_float(daily_bar.get("v")), 4),
            previous_close=round(previous_close, 4),
            prev_close_return_pct=round(prev_close_return, 3),
            live_market=live_market,
            realtime_note=(
                f"{live_note_prefix} {len(bars)} one-minute bars."
            ),
            day_trade_fit_score=day_trade_fit_score,
            day_trade_fit_reasons=day_trade_fit_reasons,
        )

    def _profile_strategy_controls(
        self,
        strategy,
        risk_flags: Sequence[str],
    ) -> tuple[bool, float, float, str]:
        stop_loss_pct = float(strategy.stop_loss_pct) * float(
            self.config.get("day_trade_stop_loss_multiplier", 1.0)
        )
        take_profit_pct = float(strategy.take_profit_pct) * float(
            self.config.get("day_trade_take_profit_multiplier", 1.0)
        )
        stop_loss_pct = max(
            float(self.config.get("day_trade_min_stop_loss_pct", 0.005)),
            min(float(self.config.get("day_trade_max_stop_loss_pct", 0.10)), stop_loss_pct),
        )
        take_profit_pct = max(
            float(self.config.get("day_trade_min_take_profit_pct", 0.01)),
            min(
                float(self.config.get("day_trade_max_take_profit_pct", 0.20)),
                take_profit_pct,
            ),
        )

        blocked_flags = {
            str(flag)
            for flag in self.config.get("day_trade_block_risk_flags", [])
            if str(flag).strip()
        }
        matched_flags = sorted(blocked_flags.intersection(set(risk_flags)))
        auto_trade_allowed = bool(strategy.auto_trade_allowed) and not matched_flags
        note = strategy.note
        if matched_flags:
            note = f"{note} Profile blocked risk flags: {', '.join(matched_flags)}."
        return (
            auto_trade_allowed,
            round(stop_loss_pct, 4),
            round(take_profit_pct, 4),
            note,
        )

    def _prefer_regular_session_bars(
        self,
        bars: Sequence[Dict[str, Any]],
    ) -> Sequence[Dict[str, Any]]:
        regular = [bar for bar in bars if self._is_regular_session_bar(bar)]
        return regular or bars

    def _is_regular_session_bar(self, bar: Dict[str, Any]) -> bool:
        timestamp = self._bar_timestamp_et(bar)
        if timestamp is None:
            return False
        minutes = timestamp.hour * 60 + timestamp.minute
        return 9 * 60 + 30 <= minutes <= 16 * 60

    def _bar_timestamp_et(self, bar: Dict[str, Any]) -> datetime | None:
        raw_time = bar.get("t")
        if not raw_time:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(ZoneInfo("America/New_York"))

    def _opening_range_strategy(
        self,
        *,
        bars: Sequence[Dict[str, Any]],
        latest_price: float,
        return_5m_pct: float,
        volume_ratio: float,
        volatility_pct: float,
        quote_spread_pct: float,
    ) -> StrategyProfile | None:
        if len(bars) < 4 or latest_price <= 0:
            return None
        first_timestamp = self._bar_timestamp_et(bars[0])
        latest_timestamp = self._bar_timestamp_et(bars[-1])
        if first_timestamp is None or latest_timestamp is None:
            return None
        first_minutes = first_timestamp.hour * 60 + first_timestamp.minute
        latest_minutes = latest_timestamp.hour * 60 + latest_timestamp.minute
        if first_minutes > 9 * 60 + 35 or latest_minutes > 11 * 60:
            return None

        opening_high = max(_safe_float(bar.get("h")) for bar in bars[:3])
        if opening_high <= 0 or latest_price <= opening_high:
            return None
        if return_5m_pct < 0.10 or volume_ratio < 1.05 or quote_spread_pct > 0.12:
            return None

        confidence = min(
            0.94,
            0.64
            + min((latest_price - opening_high) / latest_price * 100.0, 1.5) / 7.0
            + min(volume_ratio, 3.0) / 18.0,
        )
        return StrategyProfile(
            name="opening_range_breakout_15m",
            confidence=round(confidence, 3),
            auto_trade_allowed=True,
            stop_loss_pct=0.014 if volatility_pct < 0.55 else 0.024,
            take_profit_pct=0.034 if volatility_pct < 0.55 else 0.060,
            note="Price is breaking the first 15-minute range with live volume confirmation.",
        )

    def _enrich_order_flow_candidates(self, candidates: Sequence[MarketCandidate]) -> None:
        if not self.config.get("order_flow_enabled", True):
            return
        enrichment_limit = int(self.config.get("codex_ceo_order_flow_enrichment_limit", 6))
        lookback_minutes = int(self.config.get("order_flow_lookback_minutes", 15))
        for candidate in list(candidates)[: max(0, enrichment_limit)]:
            try:
                snapshot = get_alpaca_order_flow_snapshot(
                    candidate.ticker,
                    lookback_minutes=lookback_minutes,
                    feed=self.config.get("alpaca_stock_feed") or None,
                    timeout=int(self.config.get("alpaca_data_timeout_seconds", 20)),
                )
            except Exception:
                continue
            if snapshot.get("status") != "ok":
                continue
            delta_ratio = _safe_float(snapshot.get("delta_ratio"))
            absorption_flags = [
                str(flag) for flag in snapshot.get("absorption_flags", []) if str(flag)
            ]
            candidate.order_flow_delta_ratio = round(delta_ratio, 4)
            candidate.order_flow_absorption_flags = absorption_flags
            if delta_ratio > 0:
                candidate.score = round(candidate.score + min(delta_ratio, 0.65) * 2.0, 3)
            if "recent_buy_pressure_absorbed" in absorption_flags:
                candidate.score = round(candidate.score - 0.8, 3)
                if "buy_pressure_absorbed" not in candidate.risk_flags:
                    candidate.risk_flags.append("buy_pressure_absorbed")
            if "recent_sell_pressure_absorbed" in absorption_flags:
                candidate.score = round(candidate.score + 0.35, 3)

    def _trade_age_seconds(self, latest_trade: Dict[str, Any]) -> int:
        raw_time = latest_trade.get("t")
        if not raw_time:
            return 10**9
        try:
            parsed = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        except ValueError:
            return 10**9
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - parsed).total_seconds())

    def build_target_weights(self, candidates: Sequence[MarketCandidate]) -> Dict[str, float]:
        count = min(
            int(self.config.get("portfolio_target_positions", 5)),
            len(candidates),
        )
        if count <= 0:
            return {}

        allowed_strategies = {
            str(item)
            for item in self.config.get(
                "day_trade_auto_strategies",
                ["momentum_breakout", "relative_strength_continuation"],
            )
        }
        min_confidence = float(self.config.get("day_trade_min_strategy_confidence", 0.58))
        min_fit_score = float(self.config.get("codex_ceo_day_trade_min_fit_score", 0.0))
        selected = [
            candidate
            for candidate in candidates
            if candidate.auto_trade_allowed
            and candidate.strategy in allowed_strategies
            and candidate.strategy_confidence >= min_confidence
            and self._candidate_meets_day_trade_fit(candidate, min_fit_score)
            and candidate.score >= float(self.config.get("realtime_score_minimum", -9999.0))
            and (
                candidate.backtest_passed
                or not bool(self.config.get("backtest_lab_gate_targets", True))
            )
        ][:count]
        if not selected:
            return {}
        max_weight = float(self.config.get("portfolio_max_position_weight", 0.20))
        deploy_pct = float(self.config.get("portfolio_deploy_pct", 0.60))
        raw_weight = min(max_weight, deploy_pct / count)
        return {candidate.ticker: round(raw_weight, 4) for candidate in selected}

    def _candidate_meets_day_trade_fit(
        self,
        candidate: MarketCandidate,
        min_fit_score: float,
    ) -> bool:
        if min_fit_score <= 0:
            return True
        if not candidate.day_trade_fit_reasons:
            return True
        return candidate.day_trade_fit_score >= min_fit_score

    def build_order_plans(
        self,
        *,
        candidates: Sequence[MarketCandidate],
        target_weights: Dict[str, float],
        account: Dict[str, Any],
        positions: Sequence[Dict[str, Any]],
        open_orders: Sequence[Dict[str, Any]] | None = None,
    ) -> List[PortfolioOrderPlan]:
        self._last_order_plan_diagnostics = []
        candidate_by_ticker = {candidate.ticker: candidate for candidate in candidates}
        position_by_ticker = {
            str(position.get("symbol", "")).upper(): position for position in positions
        }
        open_buy_notional, open_sell_symbols = self._summarize_open_orders(open_orders or [])
        equity = _safe_float(account.get("equity"))
        buying_power = _safe_float(account.get("buying_power"))
        max_deploy = float(self.config.get("portfolio_max_deploy_usd", 1500.0))
        deploy_base = min(equity, max_deploy)
        min_order_notional = float(self.config.get("portfolio_min_order_notional_usd", 25.0))
        max_order_notional = float(self.config.get("max_order_notional_usd", 250.0))
        max_active_positions = int(self.config.get("portfolio_max_active_positions", 0))
        blocked_new_buys = {
            str(symbol).upper()
            for symbol in self.config.get("day_trade_block_new_buys_symbols", [])
            if str(symbol).strip()
        }
        active_symbols = {
            ticker
            for ticker, position in position_by_ticker.items()
            if abs(_safe_float(position.get("market_value"))) >= min_order_notional
        }

        plans: List[PortfolioOrderPlan] = []
        for ticker, weight in target_weights.items():
            candidate = candidate_by_ticker.get(ticker)
            if candidate is None or candidate.latest_price <= 0:
                self._record_order_plan_skip(ticker, "missing_candidate_or_price")
                continue
            target_notional = min(deploy_base * weight, max_order_notional)
            current_market_value = _safe_float(
                position_by_ticker.get(ticker, {}).get("market_value")
            )
            current_market_value += open_buy_notional.get(ticker, 0.0)
            delta = target_notional - current_market_value
            if abs(delta) < min_order_notional:
                self._record_order_plan_skip(
                    ticker,
                    "target_delta_below_min_order",
                    target_notional=round(target_notional, 2),
                    current_market_value=round(current_market_value, 2),
                    min_order_notional=min_order_notional,
                )
                continue
            if delta > 0 and delta > buying_power:
                delta = buying_power
            if abs(delta) < min_order_notional:
                self._record_order_plan_skip(
                    ticker,
                    "buying_power_adjusted_delta_below_min_order",
                    min_order_notional=min_order_notional,
                )
                continue
            side = "buy" if delta > 0 else "sell"
            if (
                side == "buy"
                and max_active_positions > 0
                and ticker not in active_symbols
                and len(active_symbols) >= max_active_positions
            ):
                self._record_order_plan_skip(
                    ticker,
                    "max_active_positions_reached",
                    active_positions=len(active_symbols),
                    max_active_positions=max_active_positions,
                )
                continue
            if side == "buy" and ticker in open_sell_symbols:
                self._record_order_plan_skip(ticker, "open_sell_order_exists")
                continue
            if side == "buy" and ticker in blocked_new_buys:
                self._record_order_plan_skip(
                    ticker,
                    "blocked_by_same_cycle_profile_buy",
                )
                continue
            quantity = abs(delta) / candidate.latest_price
            if (
                side == "buy"
                and bool(self.config.get("use_bracket_orders", True))
                and candidate.take_profit_pct
                and candidate.stop_loss_pct
            ):
                quantity = math.floor(quantity)
                delta = quantity * candidate.latest_price
                if delta < min_order_notional:
                    self._record_order_plan_skip(
                        ticker,
                        "whole_share_bracket_notional_below_min_order",
                        estimated_notional_usd=round(delta, 2),
                        min_order_notional=min_order_notional,
                    )
                    continue
            if side == "sell":
                current_qty = abs(_safe_float(position_by_ticker.get(ticker, {}).get("qty")))
                quantity = min(quantity, current_qty)
                quantity = _floor_quantity(quantity)
            if quantity <= 0:
                self._record_order_plan_skip(ticker, "quantity_not_positive")
                continue
            stop_loss_price = None
            take_profit_price = None
            if side == "buy":
                stop_loss_price = round(
                    candidate.latest_price * (1.0 - candidate.stop_loss_pct), 2
                )
                take_profit_price = round(
                    candidate.latest_price * (1.0 + candidate.take_profit_pct), 2
                )
            plans.append(
                PortfolioOrderPlan(
                    ticker=ticker,
                    side=side,
                    quantity=round(quantity, 4),
                    latest_price=candidate.latest_price,
                    estimated_notional_usd=round(abs(delta), 2),
                    reason=(
                        f"{candidate.strategy}: {candidate.strategy_note} "
                        f"Target starter allocation weight {weight:.1%}"
                    ),
                    strategy=candidate.strategy,
                    stop_loss_pct=candidate.stop_loss_pct if side == "buy" else None,
                    take_profit_pct=candidate.take_profit_pct if side == "buy" else None,
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price,
                )
            )
            if side == "buy":
                active_symbols.add(ticker)

        if self.config.get("day_trade_trim_stale_losers", False):
            stale_loss_pct = abs(float(self.config.get("day_trade_stale_loss_pct", 1.0))) / 100.0
            trim_non_targets = bool(self.config.get("day_trade_trim_non_target_losers", True))
            for ticker, position in position_by_ticker.items():
                if ticker in open_sell_symbols:
                    self._record_order_plan_skip(ticker, "trim_skipped_open_sell_order_exists")
                    continue
                if ticker in {plan.ticker for plan in plans if plan.side == "sell"}:
                    continue
                if ticker in target_weights and not trim_non_targets:
                    continue
                qty = abs(_safe_float(position.get("qty")))
                market_value = abs(_safe_float(position.get("market_value")))
                loss_pct = abs(_safe_float(position.get("unrealized_plpc")))
                if qty <= 0 or market_value < min_order_notional or loss_pct < stale_loss_pct:
                    continue
                price = _safe_float(position.get("current_price"))
                if price <= 0:
                    price = market_value / qty
                plans.append(
                    PortfolioOrderPlan(
                        ticker=ticker,
                        side="sell",
                        quantity=_floor_quantity(qty),
                        latest_price=round(price, 4),
                        estimated_notional_usd=round(market_value, 2),
                        reason=(
                            "Trim stale day-trade loser; setup is not worth holding "
                            f"with unrealized loss {loss_pct:.2%}"
                        ),
                    )
                )

        if self.config.get("portfolio_liquidate_non_targets", False):
            for ticker, position in position_by_ticker.items():
                if ticker in target_weights:
                    continue
                if ticker in open_sell_symbols:
                    continue
                qty = abs(_safe_float(position.get("qty")))
                market_value = abs(_safe_float(position.get("market_value")))
                if qty <= 0 or market_value < min_order_notional:
                    continue
                price = _safe_float(position.get("current_price"))
                if price <= 0:
                    price = market_value / qty
                plans.append(
                    PortfolioOrderPlan(
                        ticker=ticker,
                        side="sell",
                        quantity=_floor_quantity(qty),
                        latest_price=round(price, 4),
                        estimated_notional_usd=round(market_value, 2),
                        reason="Reduce non-target starter portfolio holding",
                    )
                )

        return plans

    def _record_order_plan_skip(self, ticker: str, reason: str, **details: Any) -> None:
        self._last_order_plan_diagnostics.append(
            {
                "ticker": ticker,
                "reason": reason,
                **details,
            }
        )

    def _summarize_open_orders(
        self, open_orders: Sequence[Dict[str, Any]]
    ) -> tuple[Dict[str, float], set[str]]:
        open_buy_notional: Dict[str, float] = {}
        open_sell_symbols: set[str] = set()
        for order in open_orders:
            symbol = str(order.get("symbol", "")).upper()
            side = str(order.get("side", "")).lower()
            if not symbol or side not in {"buy", "sell"}:
                continue
            if side == "sell":
                open_sell_symbols.add(symbol)
                continue
            qty = _safe_float(order.get("qty"))
            notional = _safe_float(order.get("notional"))
            price = (
                _safe_float(order.get("limit_price"))
                or _safe_float(order.get("stop_price"))
                or _safe_float(order.get("filled_avg_price"))
            )
            if notional <= 0 and qty > 0 and price > 0:
                notional = qty * price
            if notional > 0:
                open_buy_notional[symbol] = open_buy_notional.get(symbol, 0.0) + notional
        return open_buy_notional, open_sell_symbols

    def apply_order_plans(
        self,
        order_plans: Sequence[PortfolioOrderPlan],
        *,
        account: Dict[str, Any],
        market_open: bool,
        submit: bool,
        ceo_approved: bool,
    ) -> None:
        approval_required = bool(self.config.get("ceo_approval_required", True))
        execution_config = {
            **self.config,
            "enforce_market_open": self.config.get("enforce_market_open", True),
        }

        for plan in order_plans:
            if submit and bool(self.config.get("refresh_live_prices_before_submit", True)):
                self._refresh_plan_price(plan)
            intent = OrderIntent(
                ticker=plan.ticker,
                side=plan.side,
                quantity=plan.quantity,
                order_class=(
                    "bracket"
                    if plan.side == "buy"
                    and bool(self.config.get("use_bracket_orders", True))
                    and plan.take_profit_price is not None
                    and plan.stop_loss_price is not None
                    else None
                ),
                take_profit_limit_price=plan.take_profit_price,
                stop_loss_stop_price=plan.stop_loss_price,
            )
            policy = evaluate_order_policy(
                intent=intent,
                account=account,
                market_open=market_open,
                latest_price=plan.latest_price,
                config=execution_config,
            )
            if not policy.allow:
                plan.blocked_reason = policy.reason
                continue
            if not submit:
                plan.blocked_reason = "dry_run"
                continue
            if approval_required and not ceo_approved:
                plan.blocked_reason = "ceo_approval_required"
                continue

            try:
                response = self.broker.submit_order(intent)
                plan.submitted = True
                plan.order_response = response
            except HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                plan.blocked_reason = f"submit_failed_http_{status}"
                plan.order_response = {
                    "error": _response_text(exc.response),
                    "status_code": status,
                }
            except Exception as exc:
                plan.blocked_reason = f"submit_failed_{type(exc).__name__}"

    def _refresh_plan_price(self, plan: PortfolioOrderPlan) -> None:
        feed = self.config.get("alpaca_stock_feed") or None
        try:
            trade = self.broker.get_latest_trade(plan.ticker, feed=feed)
        except TypeError:
            trade = self.broker.get_latest_trade(plan.ticker)
        price = _safe_float(trade.get("p"))
        if price <= 0:
            return
        plan.latest_price = round(price, 4)
        if plan.side == "buy":
            if (
                bool(self.config.get("use_bracket_orders", True))
                and plan.take_profit_pct
                and plan.stop_loss_pct
            ):
                plan.quantity = math.floor(plan.quantity)
            else:
                plan.quantity = round(plan.estimated_notional_usd / plan.latest_price, 4)
            plan.estimated_notional_usd = round(plan.quantity * plan.latest_price, 2)
        else:
            plan.estimated_notional_usd = round(plan.quantity * plan.latest_price, 2)
        if plan.side == "buy" and plan.stop_loss_pct and plan.take_profit_pct:
            plan.stop_loss_price = round(plan.latest_price * (1.0 - plan.stop_loss_pct), 2)
            plan.take_profit_price = round(
                plan.latest_price * (1.0 + plan.take_profit_pct), 2
            )

    def create_ollama_staff_memo(
        self,
        candidates: Sequence[MarketCandidate],
        order_plans: Sequence[PortfolioOrderPlan],
    ) -> str:
        if not self.config.get("ollama_staff_memo_enabled", True):
            return ""
        model = str(self.config.get("ollama_staff_model", "qwen3:0.6b"))
        base_url = str(self.config.get("ollama_base_url", "http://localhost:11434")).rstrip("/")
        if is_cloud_ollama_model(model) and not hosted_llm_allowed(self.config):
            return "Local Ollama staff memo skipped: Ollama cloud model blocked by local-only compute policy."
        if not is_local_url(base_url) and not hosted_llm_allowed(self.config):
            return "Local Ollama staff memo skipped: non-local Ollama URL blocked by local-only compute policy."
        prompt = self._staff_prompt(candidates, order_plans)
        try:
            response = requests.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": float(self.config.get("ollama_temperature", 0.1)),
                        "num_ctx": int(self.config.get("ollama_num_ctx", 2048)),
                        "num_predict": int(self.config.get("ollama_num_predict", 350)),
                    },
                },
                timeout=int(self.config.get("ollama_timeout_seconds", 90)),
            )
            response.raise_for_status()
            return str(response.json().get("response", "")).strip()
        except Exception as exc:
            return f"Local Ollama staff memo unavailable: {exc}"

    def _staff_prompt(
        self,
        candidates: Sequence[MarketCandidate],
        order_plans: Sequence[PortfolioOrderPlan],
    ) -> str:
        candidate_rows = "\n".join(
            f"- {c.ticker}: score {c.score}, 5d {c.return_5d_pct}%, "
            f"20d {c.return_20d_pct}%, strategy {c.strategy} "
            f"({c.strategy_confidence}), risk {', '.join(c.risk_flags) or 'none'}, "
            f"news/themes {', '.join(c.political_themes or c.news_catalysts) or 'none'}"
            for c in candidates[:10]
        )
        order_rows = "\n".join(
            f"- {o.side.upper()} {o.quantity} {o.ticker}, est ${o.estimated_notional_usd}, "
            f"stop {o.stop_loss_price or 'n/a'}, take-profit {o.take_profit_price or 'n/a'}"
            for o in order_plans[:8]
        )
        memory_rows = self._staff_memory_context()
        return (
            "You are a lightweight local research assistant. Produce a concise "
            "staff memo for Codex CEO. Do not add new tickers. Focus on short-term "
            "paper-trading risk, catalysts, and what needs CEO review.\n\n"
            f"Candidates:\n{candidate_rows}\n\n"
            f"Proposed orders:\n{order_rows or 'No proposed orders.'}\n\n"
            f"Recent specialist memory:\n{memory_rows or 'No prior specialist lessons.'}\n\n"
            "Return 5 bullets maximum."
        )

    def _specialist_memory_context(self) -> Dict[str, str]:
        if not self.config.get("specialist_memory_enabled", True):
            return {}
        memory_dir = self.config.get("specialist_memory_dir")
        if not memory_dir:
            return {}
        agents = [
            "Market Analyst",
            "News Catalyst Analyst",
            "Risk Officer",
            "Portfolio Manager",
            "CEO Agent",
            "Local AI Staff",
        ]
        return SpecialistMemoryLog(
            memory_dir,
            max_entries=int(self.config.get("specialist_memory_max_entries", 30)),
        ).get_contexts(
            agents,
            n=int(self.config.get("specialist_memory_context_entries", 2)),
        )

    def _staff_memory_context(self) -> str:
        contexts = self._specialist_memory_context()
        if not contexts:
            return ""
        lines: List[str] = []
        for agent in ["Risk Officer", "Portfolio Manager", "CEO Agent", "Local AI Staff"]:
            context = contexts.get(agent)
            if not context:
                continue
            compact = _md_cell(context, max_len=700)
            if compact:
                lines.append(f"- {agent}: {compact}")
        return "\n".join(lines)

    def write_artifacts(
        self,
        *,
        artifact_dir: Path,
        trade_date: str,
        account: Dict[str, Any],
        positions: Sequence[Dict[str, Any]],
        open_orders: Sequence[Dict[str, Any]],
        clock: Dict[str, Any],
        candidates: Sequence[MarketCandidate],
        target_weights: Dict[str, float],
        order_plans: Sequence[PortfolioOrderPlan],
        staff_memo: str,
        technology_capabilities,
        technology_scout_report: str,
        submit: bool,
        ceo_approved: bool,
    ) -> None:
        payload = {
            "trade_date": trade_date,
            "account": self._account_summary(account),
            "positions": list(positions),
            "open_orders": list(open_orders),
            "clock": clock,
            "candidates": [asdict(candidate) for candidate in candidates],
            "catalyst_context": self._last_catalyst_context,
            "target_weights": target_weights,
            "order_plans": [asdict(plan) for plan in order_plans],
            "order_plan_diagnostics": list(self._last_order_plan_diagnostics),
            "technology_capabilities": capabilities_as_dicts(technology_capabilities),
            "compute_policy_report": self.config.get("compute_policy_report", {}),
            "specialist_memory_context": self._specialist_memory_context(),
            "staff_memo": staff_memo,
            "submit_requested": submit,
            "ceo_approved": ceo_approved,
            "paper_account_only": True,
        }
        scorecards = []
        if self.config.get("agent_scorecards_enabled", True):
            scorecards = build_agent_scorecards(payload)
            payload["agent_scorecards"] = [asdict(scorecard) for scorecard in scorecards]
        (artifact_dir / "company_run.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        (artifact_dir / "ceo_briefing_pack.md").write_text(
            self._briefing_markdown(
                trade_date=trade_date,
                account=account,
                positions=positions,
                open_orders=open_orders,
                clock=clock,
                candidates=candidates,
                target_weights=target_weights,
                order_plans=order_plans,
                order_plan_diagnostics=self._last_order_plan_diagnostics,
                agent_scorecards=scorecards,
                specialist_memory_context=payload["specialist_memory_context"],
                staff_memo=staff_memo,
                technology_scout_report=technology_scout_report,
                submit=submit,
                ceo_approved=ceo_approved,
            ),
            encoding="utf-8",
        )
        if technology_scout_report:
            (artifact_dir / "technology_scout_report.md").write_text(
                technology_scout_report,
                encoding="utf-8",
            )
        if scorecards:
            (artifact_dir / "agent_scorecards.md").write_text(
                render_agent_scorecards_markdown(scorecards),
                encoding="utf-8",
            )

    def _briefing_markdown(
        self,
        *,
        trade_date: str,
        account: Dict[str, Any],
        positions: Sequence[Dict[str, Any]],
        open_orders: Sequence[Dict[str, Any]],
        clock: Dict[str, Any],
        candidates: Sequence[MarketCandidate],
        target_weights: Dict[str, float],
        order_plans: Sequence[PortfolioOrderPlan],
        order_plan_diagnostics: Sequence[Dict[str, Any]],
        agent_scorecards,
        specialist_memory_context: Dict[str, str],
        staff_memo: str,
        technology_scout_report: str,
        submit: bool,
        ceo_approved: bool,
    ) -> str:
        lines = [
            "# Codex CEO Briefing Pack",
            "",
            f"- Trade date: {trade_date}",
            f"- Paper account status: {account.get('status', 'unknown')}",
            f"- Market open: {clock.get('is_open', 'unknown')}",
            f"- Submit requested: {submit}",
            f"- CEO approved: {ceo_approved}",
            f"- Max deployed capital: ${float(self.config.get('portfolio_max_deploy_usd', 1500.0)):.2f}",
            "",
            "## Current Positions",
        ]
        if positions:
            lines.extend(
                [
                    "| Symbol | Qty | Market Value | Unrealized P/L |",
                    "| --- | ---: | ---: | ---: |",
                ]
            )
            for position in positions:
                lines.append(
                    "| {symbol} | {qty} | {market_value} | {upl} |".format(
                        symbol=position.get("symbol", ""),
                        qty=position.get("qty", ""),
                        market_value=position.get("market_value", ""),
                        upl=position.get("unrealized_pl", ""),
                    )
                )
        else:
            lines.append("No open positions reported by the paper account.")

        lines.extend(["", "## Open Alpaca Orders"])
        if open_orders:
            lines.extend(
                [
                    "| Symbol | Side | Qty | Type | Status |",
                    "| --- | --- | ---: | --- | --- |",
                ]
            )
            for order in open_orders[:20]:
                lines.append(
                    "| {symbol} | {side} | {qty} | {type} | {status} |".format(
                        symbol=order.get("symbol", ""),
                        side=order.get("side", ""),
                        qty=order.get("qty", ""),
                        type=order.get("type", ""),
                        status=order.get("status", ""),
                    )
                )
        else:
            lines.append("No open Alpaca orders reported.")

        research_queue = list(
            (self._last_catalyst_context or {}).get("ranked_research_queue", [])
        )
        if research_queue:
            lines.extend(
                [
                    "",
                    "## Pre-Open Catalyst Research Queue",
                    "| Rank | Ticker | Action | Direction | Catalyst Score | Tags | Thesis |",
                    "| --- | --- | --- | --- | ---: | --- | --- |",
                ]
            )
            for rank, item in enumerate(research_queue[:10], start=1):
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "| {rank} | {ticker} | {action} | {direction} | {score:.1f} | {tags} | {thesis} |".format(
                        rank=rank,
                        ticker=_md_cell(item.get("symbol"), max_len=16),
                        action=_md_cell(item.get("action"), max_len=32),
                        direction=_md_cell(item.get("direction"), max_len=16),
                        score=_safe_float(item.get("score")),
                        tags=_md_cell(", ".join(item.get("catalyst_tags", [])), max_len=120)
                        or "none",
                        thesis=_md_cell(item.get("thesis"), max_len=180),
                    )
                )

        lines.extend(
            [
                "",
                "## Top 10 Market Research Candidates",
                "| Rank | Ticker | Price | 1D % | 5D % | 20D % | Vol Ratio | Fit | Strategy | Research | Risk | Score |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |",
            ]
        )
        for rank, candidate in enumerate(candidates[:10], start=1):
            lines.append(
                "| {rank} | {ticker} | {price:.2f} | {ret1:.2f} | {ret5:.2f} | "
                "{ret20:.2f} | {vol_ratio:.2f} | {fit:.1f} | {strategy} | "
                "{research} | {risk} | {score:.2f} |".format(
                    rank=rank,
                    ticker=candidate.ticker,
                    price=candidate.latest_price,
                    ret1=candidate.return_1d_pct,
                    ret5=candidate.return_5d_pct,
                    ret20=candidate.return_20d_pct,
                    vol_ratio=candidate.volume_ratio,
                    fit=candidate.day_trade_fit_score,
                    strategy=f"{candidate.strategy} ({candidate.strategy_confidence:.2f})",
                    research=_md_cell(candidate.premarket_research_action) or "none",
                    risk=", ".join(candidate.risk_flags) or "none",
                    score=candidate.score,
                )
            )

        catalyst_candidates = [
            candidate
            for candidate in candidates[:10]
            if candidate.news_catalysts or candidate.political_themes or candidate.news_headlines
        ]
        if catalyst_candidates:
            lines.extend(
                [
                    "",
                    "## News And Policy Catalysts",
                    "| Ticker | Action | Direction | Tags | Themes | Catalysts | Headlines |",
                    "| --- | --- | --- | --- | --- | --- | --- |",
                ]
            )
            for candidate in catalyst_candidates:
                lines.append(
                    "| {ticker} | {action} | {direction} | {tags} | {themes} | {catalysts} | {headlines} |".format(
                        ticker=candidate.ticker,
                        action=_md_cell(candidate.premarket_research_action) or "none",
                        direction=_md_cell(candidate.catalyst_direction) or "unknown",
                        tags=_md_cell(", ".join(candidate.catalyst_tags) or "none"),
                        themes=_md_cell(", ".join(candidate.political_themes) or "none"),
                        catalysts=_md_cell(", ".join(candidate.news_catalysts) or "none"),
                        headlines=_md_cell("; ".join(candidate.news_headlines), max_len=180)
                        or "none",
                    )
                )

        if candidates and candidates[0].data_source == "alpaca_realtime":
            lines.extend(
                [
                    "",
                    "## Realtime Data",
                    "| Ticker | 1m % | 5m % | 15m % | Session % | Spread % | Flow Delta | Absorption |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
                ]
            )
            for candidate in candidates[:10]:
                lines.append(
                    f"| {candidate.ticker} | {candidate.intraday_return_1m_pct:.2f} | "
                    f"{candidate.intraday_return_5m_pct:.2f} | "
                    f"{candidate.intraday_return_15m_pct:.2f} | "
                    f"{candidate.intraday_session_return_pct:.2f} | "
                    f"{candidate.quote_spread_pct:.3f} | "
                    f"{candidate.order_flow_delta_ratio:.3f} | "
                    f"{', '.join(candidate.order_flow_absorption_flags) or 'none'} |"
                )

            lines.extend(
                [
                    "",
                    "## Live Market Snapshot",
                    "| Ticker | Bid | Ask | Bid Sz | Ask Sz | Quote Imb | Min Vol | Day Vol | Prev Close % | Last Trade |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
                ]
            )
            for candidate in candidates[:10]:
                lines.append(
                    f"| {candidate.ticker} | {candidate.bid_price:.2f} | "
                    f"{candidate.ask_price:.2f} | {candidate.bid_size:.0f} | "
                    f"{candidate.ask_size:.0f} | {candidate.quote_imbalance:.3f} | "
                    f"{candidate.minute_bar_volume:.0f} | {candidate.daily_bar_volume:.0f} | "
                    f"{candidate.prev_close_return_pct:.2f} | "
                    f"{_md_cell(candidate.latest_trade_time, max_len=32)} |"
                )

        if self.config.get("backtest_lab_enabled", True):
            lines.extend(
                [
                    "",
                    "## Backtest Lab",
                    "| Ticker | Strategy Return | Buy/Hold | Excess | Max DD | Trades | Status |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
                ]
            )
            for candidate in candidates[:10]:
                status = "passed" if candidate.backtest_passed else "weak"
                lines.append(
                    f"| {candidate.ticker} | {candidate.backtest_return_pct:.2f}% | "
                    f"{candidate.backtest_benchmark_pct:.2f}% | "
                    f"{candidate.backtest_excess_pct:.2f}% | "
                    f"{candidate.backtest_max_drawdown_pct:.2f}% | "
                    f"{candidate.backtest_trades} | {status}: {candidate.backtest_note} |"
                )

        lines.extend(["", "## Starter Portfolio Targets"])
        if target_weights:
            lines.extend(["| Ticker | Target Weight |", "| --- | ---: |"])
            for ticker, weight in target_weights.items():
                lines.append(f"| {ticker} | {weight:.1%} |")
        else:
            lines.append("No target weights produced.")

        lines.extend(["", "## Proposed Paper Orders"])
        if order_plans:
            lines.extend(
                [
                    "| Ticker | Side | Qty | Est Notional | Stop | Take Profit | Status | Reason |",
                    "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
                ]
            )
            for order in order_plans:
                status = "submitted" if order.submitted else order.blocked_reason or "ready"
                lines.append(
                    f"| {order.ticker} | {order.side} | {order.quantity:.4f} | "
                    f"${order.estimated_notional_usd:.2f} | "
                    f"{order.stop_loss_price or ''} | {order.take_profit_price or ''} | "
                    f"{status} | {order.reason} |"
                )
        else:
            lines.append("No orders proposed.")

        if order_plan_diagnostics:
            lines.extend(
                [
                    "",
                    "## Order Planning Diagnostics",
                    "| Ticker | Reason | Details |",
                    "| --- | --- | --- |",
                ]
            )
            for item in order_plan_diagnostics[:20]:
                details = {
                    key: value
                    for key, value in item.items()
                    if key not in {"ticker", "reason"}
                }
                lines.append(
                    "| {ticker} | {reason} | {details} |".format(
                        ticker=_md_cell(item.get("ticker")),
                        reason=_md_cell(item.get("reason")),
                        details=_md_cell(json.dumps(details, sort_keys=True), max_len=160)
                        if details
                        else "",
                    )
                )

        if staff_memo:
            lines.extend(["", "## Local Ollama Staff Memo", staff_memo])

        if agent_scorecards:
            lines.extend(
                [
                    "",
                    "## AI Agent Scorecards",
                    "| Agent | Score | Grade | Gaps |",
                    "| --- | ---: | --- | --- |",
                ]
            )
            for scorecard in agent_scorecards:
                lines.append(
                    "| {agent} | {score} | {grade} | {gaps} |".format(
                        agent=_md_cell(scorecard.agent),
                        score=scorecard.score,
                        grade=scorecard.grade,
                        gaps=_md_cell("; ".join(scorecard.gaps[:2]) or "none", max_len=140),
                    )
                )

        if specialist_memory_context:
            lines.extend(["", "## Recent Specialist Memory"])
            for agent, context in specialist_memory_context.items():
                lines.extend([f"### {agent}", _md_cell(context, max_len=900)])

        if technology_scout_report:
            lines.extend(["", "## Technology Scout", technology_scout_report])

        lines.extend(
            [
                "",
                "## CEO Notes",
                "- Paper account only.",
                "- Autonomous paper mode still enforces market-open and order-size risk gates.",
                "- Orders remain blocked when the market is closed unless that policy is changed.",
            ]
        )
        return "\n".join(lines)

    def _account_summary(self, account: Dict[str, Any]) -> Dict[str, Any]:
        keys = ("status", "equity", "buying_power", "cash", "portfolio_value")
        return {key: account.get(key) for key in keys}

    def _artifact_dir(self, trade_date: str) -> Path:
        root = Path(self.config.get("results_dir", "results"))
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return root / "codex_ceo_company" / trade_date / f"run_{timestamp}"

    def _project_root(self) -> Path:
        configured = Path(self.config.get("project_dir", ".")).resolve()
        if (configured / "knowledge").exists() or (configured / ".agents").exists():
            return configured
        return configured.parent

    def _get_open_orders(self) -> Dict[str, Any]:
        get_orders = getattr(self.broker, "get_orders", None)
        if get_orders is None:
            return {"orders": []}
        try:
            return get_orders("open")
        except Exception:
            return {"orders": []}
