import pandas as pd

from tradingagents.dataflows.autonomous_discovery import (
    score_opportunity_candidate,
)


def _history(closes, volumes):
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [price * 1.01 for price in closes],
            "Low": [price * 0.99 for price in closes],
            "Close": closes,
            "Volume": volumes,
        }
    )


def test_score_opportunity_candidate_builds_data_plan_from_available_signals():
    closes = [100 + index for index in range(25)]
    volumes = [1_500_000] * 24 + [4_500_000]
    benchmark = _history([100 + index * 0.2 for index in range(25)], volumes)

    candidate = score_opportunity_candidate(
        "NVDA",
        _history(closes, volumes),
        benchmark,
        info={"sector": "Technology", "marketCap": 1_000_000_000, "beta": 1.4},
        news_headlines=["Chip demand rises"],
        order_flow={
            "status": "ok",
            "delta_ratio": 0.22,
            "point_of_control": 124.0,
            "total_volume": 10_000,
            "l2_heatmap_available": False,
        },
    )

    assert candidate is not None
    assert candidate.ticker == "NVDA"
    assert "relative_strength" in candidate.catalysts
    assert "unusual_volume" in candidate.catalysts
    assert "company_news" in candidate.data_plan
    assert "live_order_flow" in candidate.data_plan
    assert "fundamentals" in candidate.data_plan
    assert "quote_liquidity" in candidate.data_plan


def test_score_opportunity_candidate_filters_illiquid_symbols():
    closes = [10 + index * 0.1 for index in range(25)]
    volumes = [10_000] * 25

    candidate = score_opportunity_candidate(
        "TINY",
        _history(closes, volumes),
        min_avg_volume=1_000_000,
    )

    assert candidate is None

