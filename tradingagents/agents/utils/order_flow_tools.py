from __future__ import annotations

import json
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.order_flow import get_alpaca_order_flow_snapshot


def _format_money(value) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


@tool
def get_live_order_flow_snapshot(
    ticker: Annotated[str, "Ticker symbol to inspect, e.g. NVDA or SPY."],
    lookback_minutes: Annotated[
        int,
        "Recent live window to inspect. Use 5-30 minutes for intraday timing; 0 uses configured default.",
    ] = 0,
) -> str:
    """Fetch live trade/quote order-flow features for a ticker.

    Uses Alpaca equities trades and top-of-book quote data to derive volume
    profile, footprint-like delta, large prints, quote imbalance, and absorption
    flags. True L2/L3 heatmap levels require a depth provider and are reported
    as unavailable when only Alpaca L1 data is configured.
    """
    config = get_config()
    if not config.get("order_flow_enabled", True):
        return f"## Live order-flow snapshot disabled for {ticker.upper()}"

    provider = str(config.get("order_flow_provider", "alpaca")).lower()
    if provider != "alpaca":
        return (
            f"## Live order-flow snapshot unavailable for {ticker.upper()}\n\n"
            f"Configured provider `{provider}` is not implemented yet. "
            "Use `alpaca` for L1 trade/quote-derived order flow, or add a "
            "Databento/Polygon adapter for depth-aware data."
        )

    configured_lookback = int(config.get("order_flow_lookback_minutes", 15))
    effective_lookback = lookback_minutes if lookback_minutes > 0 else configured_lookback
    try:
        snapshot = get_alpaca_order_flow_snapshot(
            ticker,
            lookback_minutes=effective_lookback,
        )
    except Exception as exc:
        return (
            f"## Live order-flow snapshot unavailable for {ticker.upper()}\n\n"
            f"Reason: {exc}\n\n"
            "Set `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, and `ALPACA_STOCK_FEED` "
            "to enable Alpaca trade/quote data. For true liquidity heatmaps, add "
            "a depth provider such as Databento MBP-10/MBO."
        )

    if snapshot.get("status") != "ok":
        return (
            f"## Live order-flow snapshot for {ticker.upper()}\n\n"
            f"{snapshot.get('message', 'No order-flow data was available.')}"
        )

    quote = snapshot.get("latest_quote", {})
    lines = [
        f"## Live order-flow snapshot for {snapshot['symbol']}",
        "",
        f"- Provider/feed: {snapshot.get('provider')} / {snapshot.get('feed')}",
        f"- Window: last {snapshot.get('lookback_minutes')} minutes",
        f"- Prints: {snapshot.get('trade_count')} trades, total volume {snapshot.get('total_volume')}",
        f"- Last price: {_format_money(snapshot.get('last_price'))}",
        f"- Delta: {snapshot.get('delta')} ({snapshot.get('delta_ratio')})",
        f"- Volume profile POC: {_format_money(snapshot.get('point_of_control'))}",
        f"- Value area: {_format_money(snapshot.get('value_area_low'))} - {_format_money(snapshot.get('value_area_high'))}",
        f"- Quote: bid {_format_money(quote.get('bid_price'))} x {quote.get('bid_size')} / "
        f"ask {_format_money(quote.get('ask_price'))} x {quote.get('ask_size')}, "
        f"spread {_format_money(quote.get('spread'))}, imbalance {quote.get('quote_imbalance')}",
        f"- Absorption flags: {', '.join(snapshot.get('absorption_flags') or ['none'])}",
        f"- L2 heatmap available: {snapshot.get('l2_heatmap_available')}",
        "",
        "### Top Volume-At-Price Levels",
        "| Price | Volume | Share |",
        "| ---: | ---: | ---: |",
    ]
    for level in snapshot.get("top_volume_price_levels", [])[:8]:
        lines.append(
            f"| {_format_money(level.get('price'))} | {level.get('volume')} | {level.get('volume_share')} |"
        )

    lines.extend(
        [
            "",
            "### Top Footprint Imbalances",
            "| Price | Buy Vol | Sell Vol | Delta |",
            "| ---: | ---: | ---: | ---: |",
        ]
    )
    for level in snapshot.get("top_price_imbalances", [])[:8]:
        lines.append(
            f"| {_format_money(level.get('price'))} | {level.get('buy_volume')} | "
            f"{level.get('sell_volume')} | {level.get('delta')} |"
        )

    lines.extend(
        [
            "",
            "### Recent Large Prints",
            "| Time | Side | Price | Size |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for trade in snapshot.get("large_trades", [])[-8:]:
        lines.append(
            f"| {trade.get('timestamp')} | {trade.get('side')} | "
            f"{_format_money(trade.get('price'))} | {trade.get('size')} |"
        )

    lines.extend(
        [
            "",
            "### Machine-Readable Snapshot",
            "```json",
            json.dumps(snapshot, indent=2),
            "```",
        ]
    )
    return "\n".join(lines)
