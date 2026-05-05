from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

import yfinance as yf
from langchain_core.tools import tool


DEFAULT_DISCOVERY_UNIVERSE = [
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
]


def _pct_change(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end - start) / start * 100.0


@tool
def get_discovery_market_snapshot(
    tickers: Annotated[
        str,
        "Optional comma-separated tickers to screen. Leave blank for the default liquid US universe.",
    ] = "",
    look_back_days: Annotated[int, "Calendar days of price history to inspect"] = 30,
    limit: Annotated[int, "Maximum ranked rows to return"] = 15,
) -> str:
    """Screen a liquid stock/ETF universe for momentum, volatility, and volume.

    This is a lightweight discovery tool for the morning research desk. It is
    not a backtest or recommendation engine; the Stock Discovery Researcher
    should combine it with news and fundamentals before suggesting what the
    rest of the business should analyze.
    """
    universe = [
        item.strip().upper()
        for item in tickers.split(",")
        if item.strip()
    ] or DEFAULT_DISCOVERY_UNIVERSE

    end = datetime.utcnow().date() + timedelta(days=1)
    start = end - timedelta(days=max(7, look_back_days))
    rows = []

    for ticker in universe:
        try:
            history = yf.Ticker(ticker).history(start=str(start), end=str(end))
            if history.empty or len(history) < 2:
                continue

            close = history["Close"].dropna()
            volume = history["Volume"].dropna()
            if len(close) < 2:
                continue

            latest = float(close.iloc[-1])
            first = float(close.iloc[0])
            daily_return = _pct_change(float(close.iloc[-2]), latest)
            period_return = _pct_change(first, latest)
            avg_volume = float(volume.tail(10).mean()) if len(volume) else 0.0
            latest_volume = float(volume.iloc[-1]) if len(volume) else 0.0
            volume_ratio = latest_volume / avg_volume if avg_volume else 0.0

            score = period_return + daily_return * 1.5 + max(0.0, volume_ratio - 1.0) * 5.0
            rows.append(
                {
                    "ticker": ticker,
                    "latest_close": latest,
                    "daily_return_pct": daily_return,
                    "period_return_pct": period_return,
                    "volume_ratio": volume_ratio,
                    "score": score,
                }
            )
        except Exception:
            continue

    if not rows:
        return "No market snapshot rows were available from yfinance."

    ranked = sorted(rows, key=lambda row: row["score"], reverse=True)[:limit]
    lines = [
        f"# Discovery market snapshot ({start} to {end})",
        "| Rank | Ticker | Close | 1D % | Period % | Volume Ratio | Discovery Score |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, row in enumerate(ranked, start=1):
        lines.append(
            "| {rank} | {ticker} | {latest_close:.2f} | {daily_return_pct:.2f} | "
            "{period_return_pct:.2f} | {volume_ratio:.2f} | {score:.2f} |".format(
                rank=rank,
                **row,
            )
        )
    return "\n".join(lines)
