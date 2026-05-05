import pandas as pd

from tradingagents.company import run_momentum_smoke_backtest


def test_momentum_smoke_backtest_returns_evidence():
    dates = pd.date_range("2025-01-01", periods=60, freq="D")
    close = [100 + index for index in range(60)]
    history = pd.DataFrame(
        {
            "Open": close,
            "High": [price + 1 for price in close],
            "Low": [price - 1 for price in close],
            "Close": close,
            "Volume": [1_000_000] * 60,
        },
        index=dates,
    )

    evidence = run_momentum_smoke_backtest(ticker="AAA", history=history)

    assert evidence.ticker == "AAA"
    assert evidence.strategy == "sma_momentum_smoke"
    assert evidence.strategy_return_pct > 0
    assert evidence.passed is True
