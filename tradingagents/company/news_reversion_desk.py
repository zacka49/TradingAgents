from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
import json
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from tradingagents.agents.utils.market_scanner_tools import DEFAULT_DISCOVERY_UNIVERSE
from tradingagents.dataflows.utils import sanitize_ticker_component

try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional dependency path
    yf = None


POPULAR_NEWS_REVERSION_UNIVERSE = [
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
    "COIN",
    "MSTR",
    "HOOD",
    "SPY",
    "QQQ",
]


@dataclass(frozen=True)
class NewsCatalyst:
    ticker: str
    headline: str
    publisher: str
    published_at: datetime
    link: str = ""
    summary: str = ""


@dataclass(frozen=True)
class NewsReversionEvent:
    ticker: str
    headline: str
    publisher: str
    published_at: str
    event_session: str
    before_session: str
    one_day_after_session: str
    price_before_news: float
    price_after_news: float
    price_one_day_after: float
    event_move_pct: float
    one_day_move_from_pre_news_pct: float
    fade_return_pct: float
    reversion_capture_pct: float
    eligible: bool
    reverted_by_1d: bool
    direction: str
    link: str = ""
    note: str = ""


@dataclass(frozen=True)
class SymbolNewsReversionSummary:
    ticker: str
    events: int
    eligible_events: int
    reverted_events: int
    win_rate_pct: float
    avg_fade_return_pct: float
    avg_event_move_abs_pct: float
    avg_reversion_capture_pct: float


@dataclass(frozen=True)
class NewsReversionBacktestReport:
    generated_at: str
    lookback_days: int
    universe: list[str]
    data_source: str
    event_count: int
    eligible_event_count: int
    reverted_event_count: int
    win_rate_pct: float
    avg_fade_return_pct: float
    median_fade_return_pct: float
    avg_event_move_abs_pct: float
    avg_reversion_capture_pct: float
    verdict: str
    verdict_note: str
    events: list[NewsReversionEvent] = field(default_factory=list)
    symbol_summaries: list[SymbolNewsReversionSummary] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)


def run_news_reversion_event_study(
    *,
    universe: Sequence[str] | None = None,
    news_by_symbol: dict[str, Sequence[NewsCatalyst | dict[str, Any]]] | None = None,
    history_by_symbol: dict[str, pd.DataFrame] | None = None,
    lookback_days: int = 21,
    max_events_per_symbol: int = 3,
    min_event_move_pct: float = 1.0,
    min_reversion_capture_pct: float = 35.0,
    now: datetime | None = None,
) -> NewsReversionBacktestReport:
    """Run a daily-bar event study for the News Reversion Desk.

    The test approximates "price before news -> price after news -> price one
    day after news" with daily closes. If a headline is published after the US
    cash close, the event session is shifted to the next available trading day.
    """

    now = _ensure_utc(now or datetime.now(UTC))
    symbols = _clean_universe(universe or POPULAR_NEWS_REVERSION_UNIVERSE)
    if not symbols:
        symbols = _clean_universe(DEFAULT_DISCOVERY_UNIVERSE[:20])

    news_by_symbol = news_by_symbol or fetch_recent_news_for_symbols(
        symbols,
        lookback_days=lookback_days,
        max_events_per_symbol=max_events_per_symbol,
        now=now,
    )
    history_by_symbol = history_by_symbol or fetch_daily_history_for_symbols(
        symbols,
        lookback_days=lookback_days,
    )

    events: list[NewsReversionEvent] = []
    data_gaps: list[str] = []
    for symbol in symbols:
        catalysts = list(news_by_symbol.get(symbol, []))
        if not catalysts:
            data_gaps.append(f"{symbol}: no recent dated news returned")
            continue
        history = history_by_symbol.get(symbol)
        if history is None or history.empty:
            data_gaps.append(f"{symbol}: no daily price history returned")
            continue
        accepted_for_symbol = 0
        skipped_for_symbol = 0
        seen_event_sessions: set[str] = set()
        for catalyst in catalysts:
            if accepted_for_symbol >= max(1, int(max_events_per_symbol)):
                break
            normalized = _coerce_catalyst(symbol, catalyst)
            if normalized is None:
                skipped_for_symbol += 1
                continue
            event = evaluate_news_reversion_event(
                normalized,
                history=history,
                min_event_move_pct=min_event_move_pct,
                min_reversion_capture_pct=min_reversion_capture_pct,
            )
            if event is None:
                skipped_for_symbol += 1
                continue
            if event.event_session in seen_event_sessions:
                skipped_for_symbol += 1
                continue
            seen_event_sessions.add(event.event_session)
            events.append(event)
            accepted_for_symbol += 1
        if accepted_for_symbol == 0 and skipped_for_symbol:
            data_gaps.append(
                f"{symbol}: {skipped_for_symbol} recent news items lacked full before/after/one-day-after bars"
            )

    symbol_summaries = _summarize_symbols(events)
    eligible = [event for event in events if event.eligible]
    fade_returns = [event.fade_return_pct for event in eligible]
    reverted = [event for event in eligible if event.reverted_by_1d]
    event_abs_moves = [abs(event.event_move_pct) for event in eligible]
    reversion_captures = [event.reversion_capture_pct for event in eligible]
    win_rate = len([value for value in fade_returns if value > 0]) / len(fade_returns) * 100 if fade_returns else 0.0
    avg_fade_return = _avg(fade_returns)
    avg_reversion_capture = _avg(reversion_captures)
    verdict, verdict_note = _verdict(
        eligible_events=len(eligible),
        win_rate_pct=win_rate,
        avg_fade_return_pct=avg_fade_return,
        avg_reversion_capture_pct=avg_reversion_capture,
    )

    return NewsReversionBacktestReport(
        generated_at=now.isoformat(),
        lookback_days=int(lookback_days),
        universe=symbols,
        data_source="yfinance_news_and_daily_closes",
        event_count=len(events),
        eligible_event_count=len(eligible),
        reverted_event_count=len(reverted),
        win_rate_pct=round(win_rate, 3),
        avg_fade_return_pct=round(avg_fade_return, 3),
        median_fade_return_pct=round(median(fade_returns), 3) if fade_returns else 0.0,
        avg_event_move_abs_pct=round(_avg(event_abs_moves), 3),
        avg_reversion_capture_pct=round(avg_reversion_capture, 3),
        verdict=verdict,
        verdict_note=verdict_note,
        events=sorted(events, key=lambda item: (item.published_at, item.ticker), reverse=True),
        symbol_summaries=symbol_summaries,
        data_gaps=data_gaps,
    )


def evaluate_news_reversion_event(
    catalyst: NewsCatalyst,
    *,
    history: pd.DataFrame,
    min_event_move_pct: float = 1.0,
    min_reversion_capture_pct: float = 35.0,
) -> NewsReversionEvent | None:
    close = _prepare_close_series(history)
    if len(close) < 3:
        return None

    trading_dates = [_to_date(index) for index in close.index]
    event_index = _event_session_index(catalyst.published_at, trading_dates)
    if event_index is None or event_index <= 0 or event_index + 1 >= len(close):
        return None

    before = float(close.iloc[event_index - 1])
    after = float(close.iloc[event_index])
    one_day_after = float(close.iloc[event_index + 1])
    if before <= 0 or after <= 0 or one_day_after <= 0:
        return None

    event_move = _pct_change(before, after)
    one_day_move_from_pre = _pct_change(before, one_day_after)
    direction = "up" if event_move > 0 else "down" if event_move < 0 else "flat"
    fade_return = _fade_return_pct(after, one_day_after, event_move)
    reversion_capture = _reversion_capture_pct(before, after, one_day_after)
    eligible = abs(event_move) >= float(min_event_move_pct)
    reverted = (
        eligible
        and reversion_capture >= float(min_reversion_capture_pct)
        and fade_return > 0
    )
    note = (
        "one-day fade moved price closer to the pre-news close"
        if reverted
        else "no qualifying one-day reversion"
    )

    return NewsReversionEvent(
        ticker=catalyst.ticker,
        headline=catalyst.headline,
        publisher=catalyst.publisher,
        published_at=_ensure_utc(catalyst.published_at).isoformat(),
        event_session=str(trading_dates[event_index]),
        before_session=str(trading_dates[event_index - 1]),
        one_day_after_session=str(trading_dates[event_index + 1]),
        price_before_news=round(before, 4),
        price_after_news=round(after, 4),
        price_one_day_after=round(one_day_after, 4),
        event_move_pct=round(event_move, 3),
        one_day_move_from_pre_news_pct=round(one_day_move_from_pre, 3),
        fade_return_pct=round(fade_return, 3),
        reversion_capture_pct=round(reversion_capture, 3),
        eligible=eligible,
        reverted_by_1d=reverted,
        direction=direction,
        link=catalyst.link,
        note=note,
    )


def fetch_recent_news_for_symbols(
    symbols: Sequence[str],
    *,
    lookback_days: int = 21,
    max_events_per_symbol: int = 3,
    now: datetime | None = None,
) -> dict[str, list[NewsCatalyst]]:
    if yf is None:
        return {symbol: [] for symbol in symbols}

    now = _ensure_utc(now or datetime.now(UTC))
    start = now - timedelta(days=max(1, int(lookback_days)))
    news_by_symbol: dict[str, list[NewsCatalyst]] = {}
    for symbol in _clean_universe(symbols):
        try:
            ticker = yf.Ticker(symbol)
            raw_news = ticker.get_news(count=max(30, int(max_events_per_symbol) * 10))
        except Exception:
            raw_news = []

        catalysts: list[NewsCatalyst] = []
        seen_headlines: set[str] = set()
        for item in raw_news or []:
            catalyst = _parse_yfinance_news_item(symbol, item)
            if catalyst is None:
                continue
            if catalyst.headline in seen_headlines:
                continue
            published = _ensure_utc(catalyst.published_at)
            if not (start <= published <= now):
                continue
            seen_headlines.add(catalyst.headline)
            catalysts.append(catalyst)
        catalysts.sort(key=lambda item: item.published_at, reverse=True)
        news_by_symbol[symbol] = catalysts[: max(10, int(max_events_per_symbol) * 6)]
    return news_by_symbol


def fetch_daily_history_for_symbols(
    symbols: Sequence[str],
    *,
    lookback_days: int = 21,
) -> dict[str, pd.DataFrame]:
    if yf is None:
        return {symbol: pd.DataFrame() for symbol in symbols}

    history_by_symbol: dict[str, pd.DataFrame] = {}
    calendar_days = max(35, int(lookback_days) + 14)
    period = f"{calendar_days}d"
    for symbol in _clean_universe(symbols):
        try:
            history = yf.Ticker(symbol).history(
                period=period,
                interval="1d",
                auto_adjust=False,
            )
        except Exception:
            history = pd.DataFrame()
        history_by_symbol[symbol] = history
    return history_by_symbol


def render_news_reversion_report(report: NewsReversionBacktestReport) -> str:
    lines = [
        "# News Reversion Desk Event Study",
        "",
        f"- Generated: {report.generated_at}",
        f"- Lookback days: {report.lookback_days}",
        f"- Universe: {', '.join(report.universe)}",
        f"- Data source: {report.data_source}",
        f"- Verdict: {report.verdict}",
        f"- Verdict note: {report.verdict_note}",
        "",
        "## Summary",
        "| Events | Eligible | Reverted | Win Rate | Avg Fade Return | Median Fade Return | Avg Event Move | Avg Reversion Capture |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {report.event_count} | {report.eligible_event_count} | "
            f"{report.reverted_event_count} | {report.win_rate_pct:.2f}% | "
            f"{report.avg_fade_return_pct:.2f}% | {report.median_fade_return_pct:.2f}% | "
            f"{report.avg_event_move_abs_pct:.2f}% | {report.avg_reversion_capture_pct:.2f}% |"
        ),
        "",
        "## Department Operating Rule",
        "The News Reversion Desk is a research and evidence function. It can flag a fade/reversion setup for paper review, but it does not submit orders by itself. Any trade still needs live liquidity, spread, market-open, sizing, stop, and take-profit controls from the execution controller.",
        "",
    ]

    if report.symbol_summaries:
        lines.extend(
            [
                "## Symbol Summary",
                "| Ticker | Events | Eligible | Reverted | Win Rate | Avg Fade Return | Avg Event Move | Avg Reversion Capture |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in report.symbol_summaries:
            lines.append(
                f"| {row.ticker} | {row.events} | {row.eligible_events} | "
                f"{row.reverted_events} | {row.win_rate_pct:.2f}% | "
                f"{row.avg_fade_return_pct:.2f}% | {row.avg_event_move_abs_pct:.2f}% | "
                f"{row.avg_reversion_capture_pct:.2f}% |"
            )
        lines.append("")

    if report.events:
        lines.extend(
            [
                "## Event Detail",
                "| Ticker | Published | Event Session | Headline | Before | After | 1D After | Event Move | Fade Return | Reversion Capture | Status |",
                "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for event in report.events:
            status = "reverted" if event.reverted_by_1d else "eligible" if event.eligible else "small move"
            lines.append(
                f"| {event.ticker} | {_md_cell(event.published_at, max_len=22)} | "
                f"{event.event_session} | {_md_cell(event.headline, max_len=120)} | "
                f"{event.price_before_news:.2f} | {event.price_after_news:.2f} | "
                f"{event.price_one_day_after:.2f} | {event.event_move_pct:.2f}% | "
                f"{event.fade_return_pct:.2f}% | {event.reversion_capture_pct:.2f}% | "
                f"{status} |"
            )
        lines.append("")

    if report.data_gaps:
        lines.extend(["## Data Gaps"])
        for gap in report.data_gaps[:40]:
            lines.append(f"- {_md_cell(gap, max_len=180)}")
        if len(report.data_gaps) > 40:
            lines.append(f"- ... {len(report.data_gaps) - 40} additional gaps omitted")
        lines.append("")

    lines.extend(
        [
            "## Viability Notes",
            "- This event study uses daily closes, so it does not model intraday entry timing, spreads, borrow cost, commissions, or slippage.",
            "- A positive fade return means the next trading-day close moved in the opposite direction of the news-session close move.",
            "- A positive reversion capture means the next trading-day close moved closer to the pre-news close.",
            "- Treat a small sample as research only; require more events before allowing this desk to influence autonomous paper entries.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_news_reversion_artifacts(
    report: NewsReversionBacktestReport,
    *,
    output_dir: str | Path,
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "news_reversion_event_study.json"
    markdown_path = output / "news_reversion_event_study.md"
    json_path.write_text(
        json.dumps(asdict(report), indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_news_reversion_report(report),
        encoding="utf-8",
    )
    return {"json": str(json_path), "markdown": str(markdown_path)}


def _parse_yfinance_news_item(symbol: str, item: dict[str, Any]) -> NewsCatalyst | None:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}
    title = _clean_text(content.get("title") or item.get("title") or "")
    if not title:
        return None

    publisher = _clean_text(provider.get("displayName") or item.get("publisher") or "unknown")
    summary = _clean_text(content.get("summary") or item.get("summary") or "")
    link_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
    if isinstance(link_obj, dict):
        link = str(link_obj.get("url") or "").strip()
    else:
        link = str(item.get("link") or "").strip()
    published = _parse_publish_time(
        content.get("pubDate")
        or item.get("pubDate")
        or item.get("providerPublishTime")
        or item.get("publishTime")
    )
    if published is None:
        return None
    return NewsCatalyst(
        ticker=symbol,
        headline=title,
        publisher=publisher or "unknown",
        published_at=published,
        link=link,
        summary=summary,
    )


def _coerce_catalyst(
    symbol: str,
    value: NewsCatalyst | dict[str, Any],
) -> NewsCatalyst | None:
    if isinstance(value, NewsCatalyst):
        return value
    if not isinstance(value, dict):
        return None
    headline = _clean_text(value.get("headline") or value.get("title") or "")
    published = _parse_publish_time(
        value.get("published_at")
        or value.get("published")
        or value.get("pubDate")
        or value.get("providerPublishTime")
    )
    if not headline or published is None:
        return None
    return NewsCatalyst(
        ticker=sanitize_ticker_component(str(value.get("ticker") or symbol).upper()) or symbol,
        headline=headline,
        publisher=_clean_text(value.get("publisher") or "unknown"),
        published_at=published,
        link=str(value.get("link") or ""),
        summary=_clean_text(value.get("summary") or ""),
    )


def _parse_publish_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_utc(value)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return _ensure_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return None


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    if "\u00c3" in text or "\u00e2" in text:
        try:
            repaired = text.encode("latin-1").decode("utf-8")
            if repaired.count("\ufffd") <= text.count("\ufffd"):
                return repaired.strip()
        except UnicodeError:
            pass
    return text


def _prepare_close_series(history: pd.DataFrame) -> pd.Series:
    if history.empty or "Close" not in history.columns:
        return pd.Series(dtype=float)
    close = pd.to_numeric(history["Close"], errors="coerce").dropna()
    close = close[close > 0]
    close.index = pd.to_datetime(close.index)
    return close.sort_index()


def _event_session_index(published_at: datetime, trading_dates: Sequence[date]) -> int | None:
    if not trading_dates:
        return None
    local = _ensure_utc(published_at).astimezone(ZoneInfo("America/New_York"))
    candidate = local.date()
    if local.time() > time(16, 0):
        candidate = candidate + timedelta(days=1)
    for index, trading_date in enumerate(trading_dates):
        if trading_date >= candidate:
            return index
    return None


def _summarize_symbols(events: Sequence[NewsReversionEvent]) -> list[SymbolNewsReversionSummary]:
    rows: list[SymbolNewsReversionSummary] = []
    for ticker in sorted({event.ticker for event in events}):
        symbol_events = [event for event in events if event.ticker == ticker]
        eligible = [event for event in symbol_events if event.eligible]
        if not symbol_events:
            continue
        fade_returns = [event.fade_return_pct for event in eligible]
        wins = [event for event in eligible if event.fade_return_pct > 0]
        rows.append(
            SymbolNewsReversionSummary(
                ticker=ticker,
                events=len(symbol_events),
                eligible_events=len(eligible),
                reverted_events=len([event for event in eligible if event.reverted_by_1d]),
                win_rate_pct=round(len(wins) / len(eligible) * 100, 3) if eligible else 0.0,
                avg_fade_return_pct=round(_avg(fade_returns), 3),
                avg_event_move_abs_pct=round(_avg([abs(event.event_move_pct) for event in eligible]), 3),
                avg_reversion_capture_pct=round(_avg([event.reversion_capture_pct for event in eligible]), 3),
            )
        )
    return sorted(rows, key=lambda row: (row.avg_fade_return_pct, row.eligible_events), reverse=True)


def _verdict(
    *,
    eligible_events: int,
    win_rate_pct: float,
    avg_fade_return_pct: float,
    avg_reversion_capture_pct: float,
) -> tuple[str, str]:
    if eligible_events < 5:
        return (
            "insufficient_sample",
            "Fewer than five eligible events; keep the desk in research-only mode.",
        )
    if win_rate_pct >= 55.0 and avg_fade_return_pct > 0.15 and avg_reversion_capture_pct > 25.0:
        return (
            "promising_for_paper_research",
            "Recent eligible events show positive one-day fade behavior; continue with paper-only confirmation gates.",
        )
    if win_rate_pct >= 50.0 and avg_fade_return_pct > 0.0:
        return (
            "mixed_but_watchable",
            "The sample is positive but not strong enough for autonomous entries.",
        )
    return (
        "not_viable_yet",
        "Recent eligible events did not show enough one-day reversion to justify trading this setup.",
    )


def _clean_universe(symbols: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in symbols:
        ticker = sanitize_ticker_component(str(item).strip().upper())
        if ticker and ticker not in seen:
            seen.add(ticker)
            cleaned.append(ticker)
    return cleaned


def _to_date(value: Any) -> date:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("America/New_York")
    return timestamp.date()


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _pct_change(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end - start) / start * 100.0


def _fade_return_pct(after: float, one_day_after: float, event_move_pct: float) -> float:
    if event_move_pct > 0:
        return (after - one_day_after) / after * 100.0
    if event_move_pct < 0:
        return (one_day_after - after) / after * 100.0
    return 0.0


def _reversion_capture_pct(before: float, after: float, one_day_after: float) -> float:
    event_distance = abs(after - before)
    if event_distance == 0:
        return 0.0
    remaining_distance = abs(one_day_after - before)
    return (event_distance - remaining_distance) / event_distance * 100.0


def _avg(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _md_cell(value: Any, *, max_len: int = 120) -> str:
    text = str(value or "").replace("|", "/").replace("\n", " ").strip()
    if len(text) > max_len:
        return f"{text[: max_len - 3]}..."
    return text
