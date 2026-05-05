from __future__ import annotations

import json
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.autonomous_discovery import (
    build_autonomous_stock_selection,
)
from tradingagents.dataflows.config import get_config


def _fmt(value, decimals: int = 2) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "n/a"


@tool
def get_autonomous_stock_selection(
    tickers: Annotated[
        str,
        "Optional comma-separated ticker universe. Leave blank to scan configured/default liquid universe.",
    ] = "",
    limit: Annotated[int, "Number of ranked opportunities to return."] = 10,
) -> str:
    """Rank stocks/ETFs and recommend what data each downstream agent should inspect.

    Uses available OHLCV, relative strength, volume anomaly, volatility, yfinance
    fundamentals/news enrichment, and optional Alpaca live order flow for the
    top candidates when credentials are configured.
    """
    config = get_config()
    universe = [
        item.strip().upper()
        for item in tickers.split(",")
        if item.strip()
    ] or config.get("autonomous_discovery_universe", [])

    payload = build_autonomous_stock_selection(
        universe=universe or None,
        limit=limit,
        max_universe=int(config.get("autonomous_discovery_max_universe", 45)),
        history_period=str(config.get("autonomous_discovery_history_period", "90d")),
        enrichment_limit=int(config.get("autonomous_discovery_enrichment_limit", 12)),
        order_flow_limit=int(config.get("autonomous_discovery_order_flow_limit", 3)),
        include_live_order_flow=bool(config.get("order_flow_enabled", True)),
        min_price=float(config.get("autonomous_discovery_min_price", 5.0)),
        min_avg_volume=float(config.get("autonomous_discovery_min_avg_volume", 1_000_000)),
    )

    candidates = payload.get("candidates", [])
    if not candidates:
        return (
            "# Automated opportunity scout\n\n"
            "No liquid candidates passed the configured filters. Consider widening "
            "`autonomous_discovery_universe`, lowering minimum volume, or checking "
            "data vendor connectivity."
        )

    lines = [
        "# Automated opportunity scout",
        "",
        payload.get("selection_method", ""),
        "",
        f"Primary ticker to analyze next: {payload.get('primary_ticker')}",
        "",
        "| Rank | Ticker | Score | 1D % | 5D % | 20D % | RelStr 5D | Vol Ratio | Plan |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for rank, row in enumerate(candidates, start=1):
        lines.append(
            "| {rank} | {ticker} | {score} | {ret1} | {ret5} | {ret20} | "
            "{rs5} | {vol_ratio} | {plan} |".format(
                rank=rank,
                ticker=row.get("ticker"),
                score=_fmt(row.get("score")),
                ret1=_fmt(row.get("return_1d_pct")),
                ret5=_fmt(row.get("return_5d_pct")),
                ret20=_fmt(row.get("return_20d_pct")),
                rs5=_fmt(row.get("relative_strength_5d_pct")),
                vol_ratio=_fmt(row.get("volume_ratio")),
                plan=", ".join(row.get("data_plan", [])[:5]),
            )
        )

    lines.extend(["", "## Candidate Detail"])
    for row in candidates:
        headlines = row.get("news_headlines") or []
        order_flow = row.get("order_flow") or {}
        lines.extend(
            [
                "",
                f"### {row.get('ticker')}",
                f"- Catalysts: {', '.join(row.get('catalysts') or ['none'])}",
                f"- Risk flags: {', '.join(row.get('risk_flags') or ['none'])}",
                f"- Strategy lens: {row.get('strategy')} ({_fmt(row.get('strategy_confidence'))})",
                f"- Sector: {row.get('sector') or 'n/a'}; beta: {_fmt(row.get('beta'))}; trailing PE: {_fmt(row.get('trailing_pe'))}",
                f"- Order flow: status={order_flow.get('status', 'not_checked')}, "
                f"delta_ratio={order_flow.get('delta_ratio', 'n/a')}, "
                f"POC={order_flow.get('point_of_control', 'n/a')}, "
                f"L2 heatmap={order_flow.get('l2_heatmap_available', False)}",
                f"- Data to inspect: {', '.join(row.get('data_plan') or [])}",
            ]
        )
        if headlines:
            lines.append(f"- Recent headlines: {' | '.join(headlines[:2])}")

    lines.extend(
        [
            "",
            "## Machine-Readable Selection",
            "```json",
            json.dumps(payload, indent=2),
            "```",
        ]
    )
    return "\n".join(lines)

