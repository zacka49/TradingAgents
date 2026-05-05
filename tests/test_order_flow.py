from tradingagents.dataflows.order_flow import build_order_flow_features


def test_build_order_flow_features_derives_volume_profile_and_delta():
    trades = [
        {"t": "2026-05-05T13:30:00Z", "p": 100.00, "s": 100},
        {"t": "2026-05-05T13:30:01Z", "p": 100.02, "s": 250},
        {"t": "2026-05-05T13:30:02Z", "p": 100.01, "s": 1_200},
        {"t": "2026-05-05T13:30:03Z", "p": 100.03, "s": 300},
    ]
    quote = {"bp": 100.00, "ap": 100.04, "bs": 8, "as": 12, "t": "2026-05-05T13:30:04Z"}

    snapshot = build_order_flow_features(
        "msft",
        trades,
        quote,
        large_trade_min_size=1_000,
    )

    assert snapshot["status"] == "ok"
    assert snapshot["symbol"] == "MSFT"
    assert snapshot["trade_count"] == 4
    assert snapshot["total_volume"] == 1_850
    assert snapshot["point_of_control"] == 100.01
    assert snapshot["large_trades"][0]["size"] == 1_200
    assert snapshot["latest_quote"]["spread"] == 0.04
    assert snapshot["latest_quote"]["quote_imbalance"] == -0.2
    assert snapshot["l2_heatmap_available"] is False


def test_build_order_flow_features_flags_absorbed_recent_sell_pressure():
    trades = [
        {"t": "2026-05-05T13:30:00Z", "p": 100.00, "s": 100},
        {"t": "2026-05-05T13:30:01Z", "p": 99.99, "s": 500},
        {"t": "2026-05-05T13:30:02Z", "p": 100.00, "s": 100},
    ]

    snapshot = build_order_flow_features("spy", trades)

    assert "recent_sell_pressure_absorbed" in snapshot["absorption_flags"]
