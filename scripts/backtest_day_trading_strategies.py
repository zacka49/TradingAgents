from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Callable, Dict, Iterable, List

import pandas as pd
import yfinance as yf


DEFAULT_UNIVERSE = [
    "NVDA",
    "INTC",
    "AMD",
    "MU",
    "PLTR",
    "TSLA",
    "SMCI",
    "COIN",
    "MSTR",
    "HOOD",
    "SOFI",
    "QQQ",
    "SPY",
]


SLIPPAGE_BPS_PER_SIDE = 2.0


@dataclass(frozen=True)
class TradeResult:
    ticker: str
    strategy: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    return_pct: float
    exit_reason: str


@dataclass(frozen=True)
class StrategySummary:
    ticker: str
    strategy: str
    trades: int
    win_rate_pct: float
    avg_return_pct: float
    total_return_pct: float
    profit_factor: float
    max_drawdown_pct: float
    expectancy_pct: float
    score: float


def _parse_universe(raw: str) -> list[str]:
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _history_for_ticker(data: pd.DataFrame, ticker: str, single_ticker: bool) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()
    if single_ticker or not isinstance(data.columns, pd.MultiIndex):
        return data.dropna(how="all")
    if ticker not in data.columns.get_level_values(0):
        return pd.DataFrame()
    return data[ticker].dropna(how="all")


def _prepare_intraday(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["Open", "High", "Low", "Close", "Volume"]
    if frame.empty or not all(column in frame.columns for column in required):
        return pd.DataFrame(columns=required)
    prepared = frame.loc[:, required].copy()
    prepared.index = pd.to_datetime(prepared.index)
    if prepared.index.tz is None:
        prepared.index = prepared.index.tz_localize("UTC")
    prepared.index = prepared.index.tz_convert("America/New_York")
    prepared = prepared.between_time("09:30", "15:55")
    prepared = prepared.apply(pd.to_numeric, errors="coerce").dropna(how="any")
    prepared = prepared[prepared["Close"] > 0]
    return prepared


def _add_indicators(day: pd.DataFrame) -> pd.DataFrame:
    frame = day.copy()
    typical = (frame["High"] + frame["Low"] + frame["Close"]) / 3.0
    volume = frame["Volume"].clip(lower=0)
    cumulative_volume = volume.cumsum().replace(0, pd.NA)
    frame["vwap"] = (typical * volume).cumsum() / cumulative_volume
    frame["ema9"] = frame["Close"].ewm(span=9, adjust=False).mean()
    frame["ema20"] = frame["Close"].ewm(span=20, adjust=False).mean()
    frame["rolling_high_20"] = frame["High"].rolling(20, min_periods=5).max().shift(1)
    frame["rolling_low_20"] = frame["Low"].rolling(20, min_periods=5).min().shift(1)
    frame["rolling_volume_20"] = frame["Volume"].rolling(20, min_periods=5).mean().shift(1)
    frame["rolling_std_20"] = frame["Close"].rolling(20, min_periods=10).std().shift(1)
    delta = frame["Close"].diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=8).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=8).mean()
    rs = gain / loss.replace(0, pd.NA)
    frame["rsi14"] = 100.0 - (100.0 / (1.0 + rs))
    frame["bar_index"] = range(len(frame))
    return frame


def _pct(start: float, end: float) -> float:
    if start <= 0:
        return 0.0
    return (end - start) / start * 100.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _volume_ratio(row: pd.Series) -> float:
    base = float(row.get("rolling_volume_20") or 0.0)
    if base <= 0:
        return 0.0
    return float(row["Volume"]) / base


def _finish_trade(
    *,
    ticker: str,
    strategy: str,
    day: pd.DataFrame,
    entry_index: int,
    entry_price: float,
    stop_price: float,
    take_profit_price: float | None,
) -> TradeResult:
    entry_time = day.index[entry_index]
    exit_price = float(day["Close"].iloc[-1])
    exit_time = day.index[-1]
    exit_reason = "eod"

    for index in range(entry_index + 1, len(day)):
        high = float(day["High"].iloc[index])
        low = float(day["Low"].iloc[index])
        if low <= stop_price:
            exit_price = stop_price
            exit_time = day.index[index]
            exit_reason = "stop"
            break
        if take_profit_price is not None and high >= take_profit_price:
            exit_price = take_profit_price
            exit_time = day.index[index]
            exit_reason = "take_profit"
            break

    gross = _pct(entry_price, exit_price)
    net = gross - (SLIPPAGE_BPS_PER_SIDE * 2.0 / 100.0)
    return TradeResult(
        ticker=ticker,
        strategy=strategy,
        entry_time=entry_time.isoformat(),
        exit_time=exit_time.isoformat(),
        entry_price=round(entry_price, 4),
        exit_price=round(exit_price, 4),
        return_pct=round(net, 4),
        exit_reason=exit_reason,
    )


def _opening_range_breakout(ticker: str, day: pd.DataFrame) -> TradeResult | None:
    if len(day) < 24:
        return None
    opening = day.iloc[:3]
    opening_high = float(opening["High"].max())
    opening_low = float(opening["Low"].min())

    for index in range(3, len(day) - 1):
        row = day.iloc[index]
        if (
            float(row["Close"]) > opening_high
            and _volume_ratio(row) >= 1.15
            and float(row["Close"]) > float(row["vwap"])
        ):
            entry = float(row["Close"])
            risk_pct = _clamp((entry - opening_low) / entry, 0.0035, 0.015)
            stop = entry * (1.0 - risk_pct)
            take = entry * (1.0 + risk_pct * 2.0)
            return _finish_trade(
                ticker=ticker,
                strategy="opening_range_breakout_15m",
                day=day,
                entry_index=index,
                entry_price=entry,
                stop_price=stop,
                take_profit_price=take,
            )
    return None


def _momentum_breakout(ticker: str, day: pd.DataFrame) -> TradeResult | None:
    if len(day) < 32:
        return None
    for index in range(20, len(day) - 1):
        row = day.iloc[index]
        prior_5 = float(day["Close"].iloc[index - 5])
        close = float(row["Close"])
        if (
            close > float(row["rolling_high_20"])
            and close > float(row["vwap"])
            and _pct(prior_5, close) >= 0.35
            and _volume_ratio(row) >= 1.25
        ):
            stop = close * 0.99
            take = close * 1.02
            return _finish_trade(
                ticker=ticker,
                strategy="momentum_breakout",
                day=day,
                entry_index=index,
                entry_price=close,
                stop_price=stop,
                take_profit_price=take,
            )
    return None


def _relative_strength_continuation(ticker: str, day: pd.DataFrame) -> TradeResult | None:
    if len(day) < 32:
        return None
    open_price = float(day["Open"].iloc[0])
    for index in range(12, len(day) - 1):
        row = day.iloc[index]
        close = float(row["Close"])
        prior_3 = float(day["Close"].iloc[index - 3])
        if (
            _pct(open_price, close) >= 0.65
            and close > float(row["vwap"])
            and float(row["ema9"]) > float(row["ema20"])
            and _pct(prior_3, close) >= 0.12
            and _volume_ratio(row) >= 0.95
        ):
            stop = close * 0.992
            take = close * 1.016
            return _finish_trade(
                ticker=ticker,
                strategy="relative_strength_continuation",
                day=day,
                entry_index=index,
                entry_price=close,
                stop_price=stop,
                take_profit_price=take,
            )
    return None


def _vwap_reclaim(ticker: str, day: pd.DataFrame) -> TradeResult | None:
    if len(day) < 28:
        return None
    for index in range(8, len(day) - 1):
        row = day.iloc[index]
        prev = day.iloc[index - 1]
        recent = day.iloc[max(0, index - 6) : index]
        close = float(row["Close"])
        if (
            bool((recent["Close"] < recent["vwap"]).any())
            and float(prev["Close"]) <= float(prev["vwap"])
            and close > float(row["vwap"])
            and close > float(row["ema9"])
            and _volume_ratio(row) >= 0.90
        ):
            risk_pct = _clamp((close - float(row["vwap"])) / close + 0.003, 0.0035, 0.010)
            stop = close * (1.0 - risk_pct)
            take = close * (1.0 + risk_pct * 1.6)
            return _finish_trade(
                ticker=ticker,
                strategy="vwap_reclaim",
                day=day,
                entry_index=index,
                entry_price=close,
                stop_price=stop,
                take_profit_price=take,
            )
    return None


def _range_reversion_to_vwap(ticker: str, day: pd.DataFrame) -> TradeResult | None:
    if len(day) < 32:
        return None
    for index in range(20, len(day) - 1):
        row = day.iloc[index]
        std = float(row.get("rolling_std_20") or 0.0)
        close = float(row["Close"])
        vwap = float(row["vwap"])
        rsi = float(row.get("rsi14") or 50.0)
        if std > 0 and close < vwap - 1.1 * std and rsi <= 36:
            stop = close * 0.992
            take = min(vwap, close * 1.014)
            return _finish_trade(
                ticker=ticker,
                strategy="range_reversion_to_vwap",
                day=day,
                entry_index=index,
                entry_price=close,
                stop_price=stop,
                take_profit_price=take,
            )
    return None


STRATEGIES: Dict[str, Callable[[str, pd.DataFrame], TradeResult | None]] = {
    "opening_range_breakout_15m": _opening_range_breakout,
    "momentum_breakout": _momentum_breakout,
    "relative_strength_continuation": _relative_strength_continuation,
    "vwap_reclaim": _vwap_reclaim,
    "range_reversion_to_vwap": _range_reversion_to_vwap,
}


def _iter_days(frame: pd.DataFrame) -> Iterable[pd.DataFrame]:
    for _, day in frame.groupby(frame.index.date):
        if len(day) >= 20:
            yield _add_indicators(day)


def run_backtests(universe: List[str], *, period: str, interval: str) -> tuple[list[TradeResult], list[StrategySummary]]:
    data = yf.download(
        tickers=universe,
        period=period,
        interval=interval,
        group_by="ticker",
        auto_adjust=True,
        prepost=False,
        progress=False,
        threads=True,
    )

    trades: list[TradeResult] = []
    for ticker in universe:
        frame = _prepare_intraday(_history_for_ticker(data, ticker, len(universe) == 1))
        if frame.empty:
            continue
        for day in _iter_days(frame):
            for strategy_func in STRATEGIES.values():
                trade = strategy_func(ticker, day)
                if trade is not None:
                    trades.append(trade)

    summaries = summarize_trades(trades)
    return trades, summaries


def summarize_trades(trades: List[TradeResult]) -> List[StrategySummary]:
    if not trades:
        return []

    frame = pd.DataFrame([asdict(trade) for trade in trades])
    summaries: list[StrategySummary] = []
    for (ticker, strategy), group in frame.groupby(["ticker", "strategy"]):
        returns = group["return_pct"].astype(float).tolist()
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value <= 0]
        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        for value in returns:
            equity *= 1.0 + value / 100.0
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown = min(max_drawdown, (equity - peak) / peak * 100.0)
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_win / gross_loss if gross_loss > 0 else (gross_win or 0.0)
        total_return = (equity - 1.0) * 100.0
        win_rate = len(wins) / len(returns) * 100.0
        avg_return = sum(returns) / len(returns)
        expectancy = avg_return
        score = (
            total_return
            + win_rate * 0.08
            + profit_factor * 1.5
            - abs(max_drawdown) * 0.75
            + min(len(returns), 20) * 0.15
        )
        summaries.append(
            StrategySummary(
                ticker=str(ticker),
                strategy=str(strategy),
                trades=len(returns),
                win_rate_pct=round(win_rate, 2),
                avg_return_pct=round(avg_return, 4),
                total_return_pct=round(total_return, 3),
                profit_factor=round(profit_factor, 3),
                max_drawdown_pct=round(abs(max_drawdown), 3),
                expectancy_pct=round(expectancy, 4),
                score=round(score, 3),
            )
        )
    return sorted(summaries, key=lambda item: item.score, reverse=True)


def _aggregate_by_strategy(summaries: list[StrategySummary]) -> pd.DataFrame:
    if not summaries:
        return pd.DataFrame()
    frame = pd.DataFrame([asdict(item) for item in summaries])
    grouped = frame.groupby("strategy").agg(
        tickers=("ticker", "count"),
        trades=("trades", "sum"),
        avg_win_rate_pct=("win_rate_pct", "mean"),
        avg_total_return_pct=("total_return_pct", "mean"),
        avg_profit_factor=("profit_factor", "mean"),
        avg_max_drawdown_pct=("max_drawdown_pct", "mean"),
        avg_score=("score", "mean"),
    )
    return grouped.sort_values("avg_score", ascending=False).round(3)


def _markdown_table(frame: pd.DataFrame, max_rows: int = 20) -> list[str]:
    if frame.empty:
        return ["No rows available."]
    rows = frame.head(max_rows)
    columns = list(rows.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in rows.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return lines


def write_report(
    *,
    output_dir: Path,
    universe: list[str],
    period: str,
    interval: str,
    trades: list[TradeResult],
    summaries: list[StrategySummary],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    trades_path = output_dir / "strategy_trades.csv"
    summaries_path = output_dir / "strategy_summary.csv"
    pd.DataFrame([asdict(trade) for trade in trades]).to_csv(trades_path, index=False)
    summary_frame = pd.DataFrame([asdict(summary) for summary in summaries])
    summary_frame.to_csv(summaries_path, index=False)
    aggregate = _aggregate_by_strategy(summaries)
    if not aggregate.empty:
        aggregate.to_csv(output_dir / "strategy_aggregate.csv")

    top = summary_frame.head(20) if not summary_frame.empty else pd.DataFrame()
    report_path = output_dir / "board_strategy_backtest_report.md"
    lines = [
        "# Board Strategy Backtest Report",
        "",
        f"- Generated at: {datetime.now(UTC).isoformat()}",
        f"- Universe: {', '.join(universe)}",
        f"- Data window: yfinance `{period}` / `{interval}` regular session bars",
        f"- Cost model: {SLIPPAGE_BPS_PER_SIDE} bps per side, long-only, one entry per strategy/ticker/day",
        f"- Trade count: {len(trades)}",
        "",
        "## Strategy Family Results",
    ]
    if aggregate.empty:
        lines.append("No strategy results were produced.")
    else:
        aggregate_reset = aggregate.reset_index()
        lines.extend(_markdown_table(aggregate_reset))

    lines.extend(["", "## Top Ticker/Strategy Pairs"])
    if top.empty:
        lines.append("No ticker/strategy pairs passed the data filters.")
    else:
        lines.extend(_markdown_table(top))

    lines.extend(
        [
            "",
            "## Operating Interpretation",
            "- Favor strategies with at least 8 trades, positive total return, profit factor above 1.15, and drawdown below 5%.",
            "- Treat low-trade-count winners as watchlist candidates, not full deployment candidates.",
            "- Do not deploy fading/short setups yet; the current paper executor is optimized for long entries with bracket exits.",
            "- Use tomorrow's live Alpaca scanner to confirm spread, volume, and direction before any paper order is placed.",
            "",
            "## Files",
            f"- Trades: `{trades_path.name}`",
            f"- Summary: `{summaries_path.name}`",
            "- Aggregate: `strategy_aggregate.csv`",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="")
    parser.add_argument("--period", default="60d")
    parser.add_argument("--interval", default="5m")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    universe = _parse_universe(args.universe) or DEFAULT_UNIVERSE
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path("results") / "research" / "strategy_backtests" / timestamp
    )

    trades, summaries = run_backtests(universe, period=args.period, interval=args.interval)
    report_path = write_report(
        output_dir=output_dir,
        universe=universe,
        period=args.period,
        interval=args.interval,
        trades=trades,
        summaries=summaries,
    )
    payload = {
        "report_path": str(report_path),
        "trade_count": len(trades),
        "top_pairs": [asdict(item) for item in summaries[:12]],
        "strategy_aggregate": _aggregate_by_strategy(summaries).reset_index().to_dict("records")
        if summaries
        else [],
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

