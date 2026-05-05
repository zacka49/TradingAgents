from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

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


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _round_price(price: float, tick_size: float) -> float:
    if tick_size <= 0:
        return price
    return round(round(price / tick_size) * tick_size, 6)


def _classify_trade_side(
    trade: Dict[str, Any],
    previous_price: float | None,
    bid_price: float | None,
    ask_price: float | None,
) -> str:
    price = _safe_float(trade.get("p"))
    if bid_price is not None and ask_price is not None and ask_price >= bid_price:
        midpoint = (bid_price + ask_price) / 2.0
        if price > midpoint:
            return "buy"
        if price < midpoint:
            return "sell"

    if previous_price is not None:
        if price > previous_price:
            return "buy"
        if price < previous_price:
            return "sell"

    return "unknown"


def build_order_flow_features(
    symbol: str,
    trades: Iterable[Dict[str, Any]],
    latest_quote: Dict[str, Any] | None = None,
    *,
    tick_size: float = 0.01,
    large_trade_min_size: int = 1_000,
) -> Dict[str, Any]:
    """Build order-flow features from recent trades and top-of-book quote data.

    Alpaca's stock feed provides L1 trades and quotes, not a full order book.
    This derives footprint-like features from prints while clearly marking
    heatmap/L2 features as unavailable unless a depth provider is added later.
    """
    quote = latest_quote or {}
    bid_price = _safe_float(quote.get("bp"), default=0.0) or None
    ask_price = _safe_float(quote.get("ap"), default=0.0) or None
    bid_size = _safe_int(quote.get("bs"))
    ask_size = _safe_int(quote.get("as"))

    normalized: List[Dict[str, Any]] = []
    previous_price: float | None = None
    for raw_trade in trades:
        price = _safe_float(raw_trade.get("p"))
        size = _safe_int(raw_trade.get("s"))
        if price <= 0 or size <= 0:
            continue
        side = _classify_trade_side(raw_trade, previous_price, bid_price, ask_price)
        previous_price = price
        normalized.append(
            {
                "timestamp": raw_trade.get("t"),
                "price": price,
                "size": size,
                "side": side,
                "exchange": raw_trade.get("x"),
                "conditions": raw_trade.get("c", []),
            }
        )

    if not normalized:
        return {
            "symbol": symbol.upper(),
            "status": "empty",
            "message": "No recent trade prints were available.",
            "l2_heatmap_available": False,
        }

    total_volume = sum(trade["size"] for trade in normalized)
    buy_volume = sum(trade["size"] for trade in normalized if trade["side"] == "buy")
    sell_volume = sum(trade["size"] for trade in normalized if trade["side"] == "sell")
    unknown_volume = total_volume - buy_volume - sell_volume
    delta = buy_volume - sell_volume

    volume_by_price: Dict[float, int] = defaultdict(int)
    buy_by_price: Dict[float, int] = defaultdict(int)
    sell_by_price: Dict[float, int] = defaultdict(int)
    for trade in normalized:
        level = _round_price(trade["price"], tick_size)
        volume_by_price[level] += trade["size"]
        if trade["side"] == "buy":
            buy_by_price[level] += trade["size"]
        elif trade["side"] == "sell":
            sell_by_price[level] += trade["size"]

    ranked_levels = sorted(volume_by_price.items(), key=lambda item: item[1], reverse=True)
    point_of_control = ranked_levels[0][0]
    value_area_volume = total_volume * 0.70
    running = 0
    value_area_levels = []
    for price, volume in ranked_levels:
        if running >= value_area_volume:
            break
        value_area_levels.append(price)
        running += volume

    prices = [trade["price"] for trade in normalized]
    sizes = sorted(trade["size"] for trade in normalized)
    percentile_index = max(0, min(len(sizes) - 1, int(len(sizes) * 0.90) - 1))
    dynamic_large_size = max(large_trade_min_size, sizes[percentile_index])
    large_trades = [
        trade for trade in normalized if trade["size"] >= dynamic_large_size
    ][-10:]

    top_imbalances = []
    for price, volume in ranked_levels[:12]:
        buys = buy_by_price.get(price, 0)
        sells = sell_by_price.get(price, 0)
        if volume <= 0:
            continue
        top_imbalances.append(
            {
                "price": price,
                "total_volume": volume,
                "buy_volume": buys,
                "sell_volume": sells,
                "delta": buys - sells,
            }
        )

    spread = None
    quote_imbalance = None
    if bid_price is not None and ask_price is not None:
        spread = round(ask_price - bid_price, 6)
    if bid_size + ask_size > 0:
        quote_imbalance = round((bid_size - ask_size) / (bid_size + ask_size), 4)

    recent_window = normalized[-min(25, len(normalized)) :]
    recent_delta = sum(
        trade["size"] if trade["side"] == "buy" else -trade["size"]
        for trade in recent_window
        if trade["side"] in {"buy", "sell"}
    )
    recent_price_change = recent_window[-1]["price"] - recent_window[0]["price"]
    absorption_flags = []
    if recent_delta < 0 and recent_price_change >= 0:
        absorption_flags.append("recent_sell_pressure_absorbed")
    if recent_delta > 0 and recent_price_change <= 0:
        absorption_flags.append("recent_buy_pressure_absorbed")

    return {
        "symbol": symbol.upper(),
        "status": "ok",
        "trade_count": len(normalized),
        "first_trade_time": normalized[0]["timestamp"],
        "last_trade_time": normalized[-1]["timestamp"],
        "last_price": normalized[-1]["price"],
        "total_volume": total_volume,
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "unknown_volume": unknown_volume,
        "delta": delta,
        "delta_ratio": round(delta / total_volume, 4) if total_volume else 0.0,
        "point_of_control": point_of_control,
        "value_area_low": min(value_area_levels) if value_area_levels else None,
        "value_area_high": max(value_area_levels) if value_area_levels else None,
        "top_volume_price_levels": [
            {
                "price": price,
                "volume": volume,
                "volume_share": round(volume / total_volume, 4),
            }
            for price, volume in ranked_levels[:10]
        ],
        "top_price_imbalances": top_imbalances,
        "large_trade_threshold": dynamic_large_size,
        "large_trades": large_trades,
        "latest_quote": {
            "bid_price": bid_price,
            "ask_price": ask_price,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "spread": spread,
            "quote_imbalance": quote_imbalance,
            "timestamp": quote.get("t"),
        },
        "absorption_flags": absorption_flags,
        "l2_heatmap_available": False,
        "l2_heatmap_note": (
            "Alpaca equities data supplies trades and top-of-book quotes. "
            "Use Databento MBP-10/MBO, Polygon depth where available, or a broker "
            "depth feed for true liquidity heatmap levels."
        ),
    }


def get_alpaca_order_flow_snapshot(
    symbol: str,
    *,
    lookback_minutes: int = 15,
    trade_limit: int = 1_000,
    feed: str | None = None,
    timeout: int = 20,
) -> Dict[str, Any]:
    """Fetch recent Alpaca prints/quote and return derived order-flow features."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("symbol is required")

    headers = _alpaca_headers()
    stock_feed = feed or os.getenv("ALPACA_STOCK_FEED", "iex")
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=max(1, lookback_minutes))

    trades_resp = requests.get(
        f"{ALPACA_DATA_BASE_URL}/v2/stocks/{symbol}/trades",
        headers=headers,
        params={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": max(1, min(trade_limit, 10_000)),
            "feed": stock_feed,
            "sort": "asc",
        },
        timeout=timeout,
    )
    trades_resp.raise_for_status()
    trades = trades_resp.json().get("trades", [])

    quote_resp = requests.get(
        f"{ALPACA_DATA_BASE_URL}/v2/stocks/{symbol}/quotes/latest",
        headers=headers,
        params={"feed": stock_feed},
        timeout=timeout,
    )
    quote_resp.raise_for_status()
    latest_quote = quote_resp.json().get("quote", {})

    snapshot = build_order_flow_features(
        symbol,
        trades,
        latest_quote,
        large_trade_min_size=_safe_int(os.getenv("ORDER_FLOW_LARGE_TRADE_MIN_SIZE"), 1_000),
    )
    snapshot["provider"] = "alpaca"
    snapshot["feed"] = stock_feed
    snapshot["lookback_minutes"] = lookback_minutes
    snapshot["generated_at"] = datetime.now(timezone.utc).isoformat()
    return snapshot

