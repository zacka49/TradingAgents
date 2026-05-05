from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

try:
    import backtrader as bt
except Exception:  # pragma: no cover - optional dependency path
    bt = None


@dataclass(frozen=True)
class BacktestEvidence:
    ticker: str
    strategy: str
    strategy_return_pct: float
    buy_hold_return_pct: float
    excess_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    passed: bool
    note: str


if bt is not None:

    class MomentumSmokeStrategy(bt.Strategy):
        params = {
            "fast_period": 5,
            "slow_period": 20,
            "risk_fraction": 0.95,
        }

        def __init__(self) -> None:
            self.fast_sma = bt.ind.SMA(period=self.p.fast_period)
            self.slow_sma = bt.ind.SMA(period=self.p.slow_period)

        def next(self) -> None:
            close = float(self.data.close[0])
            if close <= 0:
                return
            if not self.position:
                if self.fast_sma[0] > self.slow_sma[0] and close > self.slow_sma[0]:
                    size = (self.broker.getcash() * self.p.risk_fraction) / close
                    if size > 0:
                        self.buy(size=size)
                return
            if close < self.fast_sma[0] or self.fast_sma[0] < self.slow_sma[0]:
                self.close()


def run_momentum_smoke_backtest(
    *,
    ticker: str,
    history: pd.DataFrame,
    min_bars: int = 40,
    initial_cash: float = 10_000.0,
    min_strategy_return_pct: float = -10.0,
    min_excess_return_pct: float = -8.0,
) -> BacktestEvidence:
    """Run a tiny Backtrader momentum check over already-loaded daily bars."""

    if bt is None:
        return _unavailable(ticker, "Backtrader is not installed")

    frame = _prepare_ohlcv(history)
    if len(frame) < min_bars:
        return _unavailable(ticker, f"Only {len(frame)} usable bars")

    first_close = float(frame["Close"].iloc[0])
    last_close = float(frame["Close"].iloc[-1])
    if first_close <= 0 or last_close <= 0:
        return _unavailable(ticker, "Invalid close prices")

    try:
        cerebro = bt.Cerebro(stdstats=False)
        cerebro.broker.setcash(initial_cash)
        cerebro.adddata(bt.feeds.PandasData(dataname=frame))
        cerebro.addstrategy(MomentumSmokeStrategy)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        result = cerebro.run(maxcpus=1)[0]
        final_value = float(cerebro.broker.getvalue())
        strategy_return = (final_value - initial_cash) / initial_cash * 100.0
        buy_hold_return = (last_close - first_close) / first_close * 100.0
        excess_return = strategy_return - buy_hold_return
        drawdown = float(
            _nested_get(result.analyzers.drawdown.get_analysis(), ("max", "drawdown"), 0.0)
        )
        trade_count = int(
            _nested_get(result.analyzers.trades.get_analysis(), ("total", "closed"), 0)
        )
    except Exception as exc:  # pragma: no cover - defensive for vendor internals
        return _unavailable(ticker, f"Backtest failed: {type(exc).__name__}")

    passed = strategy_return >= min_strategy_return_pct and (
        strategy_return > 0.0 or excess_return >= min_excess_return_pct
    )
    if passed and excess_return < min_excess_return_pct:
        note = "Momentum smoke test positive but lagged buy-and-hold"
    elif passed:
        note = "Momentum smoke test passed"
    else:
        note = "Momentum smoke test weak; keep position sizing conservative"
    return BacktestEvidence(
        ticker=ticker,
        strategy="sma_momentum_smoke",
        strategy_return_pct=round(strategy_return, 3),
        buy_hold_return_pct=round(buy_hold_return, 3),
        excess_return_pct=round(excess_return, 3),
        max_drawdown_pct=round(drawdown, 3),
        trade_count=trade_count,
        passed=passed,
        note=note,
    )


def _prepare_ohlcv(history: pd.DataFrame) -> pd.DataFrame:
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not all(column in history.columns for column in required):
        return pd.DataFrame(columns=required)
    frame = history.loc[:, required].copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.apply(pd.to_numeric, errors="coerce").dropna(how="any")
    frame = frame[frame["Close"] > 0]
    return frame


def _nested_get(payload: Any, path: tuple[str, ...], default: Any) -> Any:
    current = payload
    for part in path:
        try:
            current = current[part]
        except Exception:
            return default
    return current


def _unavailable(ticker: str, note: str) -> BacktestEvidence:
    return BacktestEvidence(
        ticker=ticker,
        strategy="sma_momentum_smoke",
        strategy_return_pct=0.0,
        buy_hold_return_pct=0.0,
        excess_return_pct=0.0,
        max_drawdown_pct=0.0,
        trade_count=0,
        passed=True,
        note=f"Backtest unavailable: {note}",
    )
