"""Preflight checks for live data wiring (Alpaca + optional TradingView webhook).

This script only validates connectivity and data availability. It does not place
orders and does not run the full TradingAgents graph.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from dotenv import load_dotenv


def _headers() -> dict[str, str]:
    key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Missing APCA_API_KEY_ID or APCA_API_SECRET_KEY in .env")
    return {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    }


def _print_ok(name: str, detail: str) -> None:
    print(f"[OK] {name}: {detail}")


def _print_warn(name: str, detail: str) -> None:
    print(f"[WARN] {name}: {detail}")


def _check_account(base_url: str, headers: dict[str, str]) -> None:
    resp = requests.get(f"{base_url}/v2/account", headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    _print_ok(
        "Alpaca trading auth",
        f"status={data.get('status')} buying_power={data.get('buying_power')} currency={data.get('currency')}",
    )


def _check_stock_bars(symbol: str, headers: dict[str, str]) -> None:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=2)
    params = {
        "symbols": symbol,
        "timeframe": "1Min",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "limit": 50,
        "feed": os.getenv("ALPACA_STOCK_FEED", "iex"),
    }
    resp = requests.get(
        "https://data.alpaca.markets/v2/stocks/bars",
        headers=headers,
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    bars = payload.get("bars", {}).get(symbol, [])
    if not bars:
        _print_warn("Alpaca bars", f"no bars returned for {symbol}")
        return
    last_bar = bars[-1]
    _print_ok(
        "Alpaca bars",
        f"{symbol} bars={len(bars)} last_close={last_bar.get('c')} at={last_bar.get('t')}",
    )


def _check_latest_trade_quote(symbol: str, headers: dict[str, str]) -> None:
    feed = os.getenv("ALPACA_STOCK_FEED", "iex")
    tq = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
        headers=headers,
        params={"feed": feed},
        timeout=20,
    )
    tq.raise_for_status()
    trade = tq.json().get("trade") or {}
    _print_ok(
        "Alpaca latest trade",
        f"{symbol} price={trade.get('p')} size={trade.get('s')} time={trade.get('t')}",
    )

    qq = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest",
        headers=headers,
        params={"feed": feed},
        timeout=20,
    )
    qq.raise_for_status()
    quote = qq.json().get("quote") or {}
    _print_ok(
        "Alpaca latest quote",
        f"{symbol} bid={quote.get('bp')} ask={quote.get('ap')} time={quote.get('t')}",
    )


def _check_news(symbol: str, headers: dict[str, str]) -> None:
    resp = requests.get(
        "https://data.alpaca.markets/v1beta1/news",
        headers=headers,
        params={"symbols": symbol, "limit": 3},
        timeout=20,
    )
    if resp.status_code >= 400:
        _print_warn("Alpaca news", f"status={resp.status_code} body={resp.text[:180]}")
        return
    items = resp.json().get("news", [])
    if not items:
        _print_warn("Alpaca news", f"no recent items for {symbol}")
        return
    headline = items[0].get("headline", "")
    _print_ok("Alpaca news", f"items={len(items)} latest='{headline[:80]}'")


def _check_tradingview_secret() -> None:
    secret = os.getenv("TRADINGVIEW_WEBHOOK_SECRET")
    if secret:
        _print_ok("TradingView webhook secret", "configured")
    else:
        _print_warn("TradingView webhook secret", "not set")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="NVDA")
    args = parser.parse_args()

    load_dotenv(".env", override=True)

    trading_base = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets").rstrip("/")
    headers = _headers()

    print("Running live data preflight checks...")
    _check_account(trading_base, headers)
    _check_stock_bars(args.symbol.upper(), headers)
    _check_latest_trade_quote(args.symbol.upper(), headers)
    _check_news(args.symbol.upper(), headers)
    _check_tradingview_secret()
    print("Preflight complete.")


if __name__ == "__main__":
    main()
