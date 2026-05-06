from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Sequence

import requests


ALPACA_DATA_BASE_URL = "https://data.alpaca.markets"


def _alpaca_headers() -> Dict[str, str]:
    key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Missing APCA_API_KEY_ID or APCA_API_SECRET_KEY.")
    return {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    }


def _chunks(items: Sequence[str], size: int) -> Iterable[List[str]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def _clean_symbols(symbols: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    cleaned: List[str] = []
    for symbol in symbols:
        normalized = str(symbol).strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned


def get_latest_trades(
    symbols: Iterable[str],
    *,
    feed: str | None = None,
    timeout: int = 20,
    batch_size: int = 50,
) -> Dict[str, Dict[str, Any]]:
    """Return latest Alpaca stock trades keyed by symbol."""
    cleaned = _clean_symbols(symbols)
    if not cleaned:
        return {}

    headers = _alpaca_headers()
    stock_feed = feed or os.getenv("ALPACA_STOCK_FEED", "iex")
    trades: Dict[str, Dict[str, Any]] = {}
    for batch in _chunks(cleaned, max(1, batch_size)):
        resp = requests.get(
            f"{ALPACA_DATA_BASE_URL}/v2/stocks/trades/latest",
            headers=headers,
            params={"symbols": ",".join(batch), "feed": stock_feed},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json().get("trades", {})
        for symbol, trade in payload.items():
            if isinstance(trade, dict):
                trades[str(symbol).upper()] = trade
    return trades


def get_latest_quotes(
    symbols: Iterable[str],
    *,
    feed: str | None = None,
    timeout: int = 20,
    batch_size: int = 50,
) -> Dict[str, Dict[str, Any]]:
    """Return latest Alpaca stock quotes keyed by symbol."""
    cleaned = _clean_symbols(symbols)
    if not cleaned:
        return {}

    headers = _alpaca_headers()
    stock_feed = feed or os.getenv("ALPACA_STOCK_FEED", "iex")
    quotes: Dict[str, Dict[str, Any]] = {}
    for batch in _chunks(cleaned, max(1, batch_size)):
        resp = requests.get(
            f"{ALPACA_DATA_BASE_URL}/v2/stocks/quotes/latest",
            headers=headers,
            params={"symbols": ",".join(batch), "feed": stock_feed},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json().get("quotes", {})
        for symbol, quote in payload.items():
            if isinstance(quote, dict):
                quotes[str(symbol).upper()] = quote
    return quotes


def get_latest_bars(
    symbols: Iterable[str],
    *,
    feed: str | None = None,
    timeout: int = 20,
    batch_size: int = 50,
) -> Dict[str, Dict[str, Any]]:
    """Return Alpaca's latest minute bar keyed by symbol."""
    cleaned = _clean_symbols(symbols)
    if not cleaned:
        return {}

    headers = _alpaca_headers()
    stock_feed = feed or os.getenv("ALPACA_STOCK_FEED", "iex")
    bars: Dict[str, Dict[str, Any]] = {}
    for batch in _chunks(cleaned, max(1, batch_size)):
        resp = requests.get(
            f"{ALPACA_DATA_BASE_URL}/v2/stocks/bars/latest",
            headers=headers,
            params={"symbols": ",".join(batch), "feed": stock_feed},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json().get("bars", {})
        for symbol, bar in payload.items():
            if isinstance(bar, dict):
                bars[str(symbol).upper()] = bar
    return bars


def get_snapshots(
    symbols: Iterable[str],
    *,
    feed: str | None = None,
    timeout: int = 20,
    batch_size: int = 50,
) -> Dict[str, Dict[str, Any]]:
    """Return Alpaca stock snapshots keyed by symbol.

    A snapshot combines the latest trade, latest quote, latest minute bar,
    current daily bar, and previous daily bar. It is the richest REST polling
    endpoint Alpaca exposes for broad stock scans.
    """
    cleaned = _clean_symbols(symbols)
    if not cleaned:
        return {}

    headers = _alpaca_headers()
    stock_feed = feed or os.getenv("ALPACA_STOCK_FEED", "iex")
    snapshots: Dict[str, Dict[str, Any]] = {}
    for batch in _chunks(cleaned, max(1, batch_size)):
        resp = requests.get(
            f"{ALPACA_DATA_BASE_URL}/v2/stocks/snapshots",
            headers=headers,
            params={"symbols": ",".join(batch), "feed": stock_feed},
            timeout=timeout,
        )
        resp.raise_for_status()
        raw_payload = resp.json()
        payload = raw_payload.get("snapshots", raw_payload)
        for symbol, snapshot in payload.items():
            if isinstance(snapshot, dict):
                snapshots[str(symbol).upper()] = snapshot
    return snapshots


def get_intraday_bars(
    symbols: Iterable[str],
    *,
    lookback_minutes: int = 90,
    timeframe: str = "1Min",
    feed: str | None = None,
    timeout: int = 20,
    batch_size: int = 50,
    limit: int = 10_000,
) -> Dict[str, List[Dict[str, Any]]]:
    """Return recent Alpaca intraday bars keyed by symbol."""
    cleaned = _clean_symbols(symbols)
    if not cleaned:
        return {}

    headers = _alpaca_headers()
    stock_feed = feed or os.getenv("ALPACA_STOCK_FEED", "iex")
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=max(1, lookback_minutes))
    bars_by_symbol: Dict[str, List[Dict[str, Any]]] = {symbol: [] for symbol in cleaned}

    for batch in _chunks(cleaned, max(1, batch_size)):
        resp = requests.get(
            f"{ALPACA_DATA_BASE_URL}/v2/stocks/bars",
            headers=headers,
            params={
                "symbols": ",".join(batch),
                "timeframe": timeframe,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": max(1, min(limit, 10_000)),
                "feed": stock_feed,
                "sort": "asc",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json().get("bars", {})
        for symbol, bars in payload.items():
            if isinstance(bars, list):
                bars_by_symbol[str(symbol).upper()] = [
                    bar for bar in bars if isinstance(bar, dict)
                ]
    return bars_by_symbol
