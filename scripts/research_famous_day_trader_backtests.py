from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd
import yfinance as yf


DEFAULT_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "SOXX",
    "SMH",
    "NVDA",
    "AMD",
    "TSLA",
    "COIN",
    "HOOD",
    "PLTR",
    "META",
    "AAPL",
    "MSFT",
    "AMZN",
    "AVGO",
    "UUP",
    "FXE",
    "FXY",
    "FXB",
    "FXA",
    "GLD",
    "TLT",
]

SLIPPAGE_BPS_PER_SIDE = 5.0


@dataclass(frozen=True)
class TradeResult:
    ticker: str
    trader_proxy: str
    strategy: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    return_pct: float
    exit_reason: str


@dataclass(frozen=True)
class StrategySummary:
    trader_proxy: str
    strategy: str
    trades: int
    win_rate_pct: float
    avg_return_pct: float
    median_return_pct: float
    total_return_pct: float
    profit_factor: float
    max_drawdown_pct: float
    expectancy_pct: float
    best_trade_pct: float
    worst_trade_pct: float


StrategyFunc = Callable[[str, pd.DataFrame, dict[str, float]], TradeResult | None]


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


def _pct(start: float, end: float) -> float:
    if start <= 0:
        return 0.0
    return (end - start) / start * 100.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


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
    frame["typical"] = typical
    frame["bar_index"] = range(len(frame))

    ma = frame["Close"].rolling(20, min_periods=20).mean()
    std = frame["Close"].rolling(20, min_periods=20).std()
    tr_components = pd.concat(
        [
            frame["High"] - frame["Low"],
            (frame["High"] - frame["Close"].shift()).abs(),
            (frame["Low"] - frame["Close"].shift()).abs(),
        ],
        axis=1,
    )
    atr = tr_components.max(axis=1).rolling(20, min_periods=20).mean()
    frame["bb_upper"] = ma + 2.0 * std
    frame["bb_lower"] = ma - 2.0 * std
    frame["kc_upper"] = ma + 1.5 * atr
    frame["kc_lower"] = ma - 1.5 * atr
    frame["squeeze_on"] = (frame["bb_upper"] < frame["kc_upper"]) & (
        frame["bb_lower"] > frame["kc_lower"]
    )
    frame["momentum_20"] = frame["Close"] - frame["Close"].shift(20)
    return frame


def _daily_stats(frame: pd.DataFrame) -> dict[object, dict[str, float]]:
    if frame.empty:
        return {}
    daily = frame.groupby(frame.index.date).agg(
        open=("Open", "first"),
        high=("High", "max"),
        low=("Low", "min"),
        close=("Close", "last"),
        volume=("Volume", "sum"),
    )
    daily["range"] = daily["high"] - daily["low"]
    daily["prev_open"] = daily["open"].shift(1)
    daily["prev_high"] = daily["high"].shift(1)
    daily["prev_low"] = daily["low"].shift(1)
    daily["prev_close"] = daily["close"].shift(1)
    daily["prev_volume"] = daily["volume"].shift(1)
    daily["avg_volume_20"] = daily["volume"].shift(1).rolling(20, min_periods=5).mean()
    daily["high_20"] = daily["high"].shift(1).rolling(20, min_periods=5).max()
    daily["low_20"] = daily["low"].shift(1).rolling(20, min_periods=5).min()
    daily["ma20"] = daily["close"].shift(1).rolling(20, min_periods=5).mean()
    daily["prev_range"] = daily["range"].shift(1)
    daily["prev_nr7"] = daily["range"].shift(1) <= daily["range"].shift(2).rolling(
        6, min_periods=3
    ).min()
    return daily.to_dict("index")


def _volume_ratio(row: pd.Series) -> float:
    base = float(row.get("rolling_volume_20") or 0.0)
    if base <= 0:
        return 0.0
    return float(row["Volume"]) / base


def _volume_pace(day: pd.DataFrame, meta: dict[str, float], index: int) -> float:
    avg_volume = float(meta.get("avg_volume_20") or 0.0)
    if avg_volume <= 0:
        return 0.0
    elapsed_fraction = max((index + 1) / max(len(day), 1), 0.01)
    expected = avg_volume * elapsed_fraction
    if expected <= 0:
        return 0.0
    return float(day["Volume"].iloc[: index + 1].sum()) / expected


def _gap_pct(day: pd.DataFrame, meta: dict[str, float]) -> float:
    prev_close = float(meta.get("prev_close") or 0.0)
    if prev_close <= 0:
        return 0.0
    return _pct(prev_close, float(day["Open"].iloc[0]))


def _finish_trade(
    *,
    ticker: str,
    trader_proxy: str,
    strategy: str,
    day: pd.DataFrame,
    entry_index: int,
    entry_price: float,
    stop_price: float,
    take_profit_price: float | None,
) -> TradeResult:
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
        trader_proxy=trader_proxy,
        strategy=strategy,
        entry_time=day.index[entry_index].isoformat(),
        exit_time=exit_time.isoformat(),
        entry_price=round(entry_price, 4),
        exit_price=round(exit_price, 4),
        return_pct=round(net, 4),
        exit_reason=exit_reason,
    )


def _orb_trade(
    *,
    ticker: str,
    trader_proxy: str,
    strategy: str,
    day: pd.DataFrame,
    start_bar: int = 3,
    volume_ratio_min: float = 1.05,
    volume_pace_min: float = 0.0,
    meta: dict[str, float] | None = None,
    require_vwap: bool = True,
) -> TradeResult | None:
    if len(day) < 24:
        return None
    opening = day.iloc[:start_bar]
    opening_high = float(opening["High"].max())
    opening_low = float(opening["Low"].min())
    meta = meta or {}

    for index in range(start_bar, len(day) - 1):
        row = day.iloc[index]
        close = float(row["Close"])
        if close <= opening_high:
            continue
        if require_vwap and close <= float(row["vwap"]):
            continue
        if _volume_ratio(row) < volume_ratio_min:
            continue
        if _volume_pace(day, meta, index) < volume_pace_min:
            continue
        risk_pct = _clamp((close - opening_low) / close, 0.004, 0.018)
        return _finish_trade(
            ticker=ticker,
            trader_proxy=trader_proxy,
            strategy=strategy,
            day=day,
            entry_index=index,
            entry_price=close,
            stop_price=close * (1.0 - risk_pct),
            take_profit_price=close * (1.0 + risk_pct * 2.0),
        )
    return None


def ross_cameron_gap_momentum(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    if _gap_pct(day, meta) < 2.0:
        return None
    return _orb_trade(
        ticker=ticker,
        trader_proxy="Ross Cameron",
        strategy="gap_momentum_orb",
        day=day,
        start_bar=3,
        volume_ratio_min=1.15,
        volume_pace_min=1.2,
        meta=meta,
    )


def andrew_aziz_orb_vwap(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    return _orb_trade(
        ticker=ticker,
        trader_proxy="Andrew Aziz",
        strategy="stocks_in_play_orb_vwap",
        day=day,
        start_bar=3,
        volume_ratio_min=1.10,
        volume_pace_min=0.9,
        meta=meta,
    )


def toby_crabel_nr7_orb(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    if not bool(meta.get("prev_nr7")):
        return None
    return _orb_trade(
        ticker=ticker,
        trader_proxy="Toby Crabel",
        strategy="nr7_opening_range_breakout",
        day=day,
        start_bar=3,
        volume_ratio_min=1.00,
        volume_pace_min=0.75,
        meta=meta,
    )


def linda_raschke_turtle_soup(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    prev_low = float(meta.get("prev_low") or 0.0)
    if prev_low <= 0 or len(day) < 24:
        return None
    swept = False
    sweep_low = prev_low
    for index in range(3, len(day) - 1):
        row = day.iloc[index]
        if float(row["Low"]) < prev_low:
            swept = True
            sweep_low = min(sweep_low, float(row["Low"]))
        if not swept:
            continue
        close = float(row["Close"])
        if close > prev_low and close > float(row["vwap"]) and _volume_ratio(row) >= 0.85:
            risk_pct = _clamp((close - sweep_low) / close, 0.004, 0.015)
            return _finish_trade(
                ticker=ticker,
                trader_proxy="Linda Raschke",
                strategy="turtle_soup_reclaim",
                day=day,
                entry_index=index,
                entry_price=close,
                stop_price=close * (1.0 - risk_pct),
                take_profit_price=close * (1.0 + risk_pct * 1.6),
            )
    return None


def mark_minervini_vcp_intraday(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    high_20 = float(meta.get("high_20") or 0.0)
    ma20 = float(meta.get("ma20") or 0.0)
    if high_20 <= 0 or ma20 <= 0:
        return None
    if float(meta.get("prev_close") or 0.0) < ma20:
        return None
    return _orb_trade(
        ticker=ticker,
        trader_proxy="Mark Minervini",
        strategy="sepa_vcp_intraday_breakout",
        day=day,
        start_bar=3,
        volume_ratio_min=1.10,
        volume_pace_min=0.9,
        meta=meta,
        require_vwap=True,
    )


def dan_zanger_volume_breakout(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    prior_high = max(float(meta.get("prev_high") or 0.0), float(meta.get("high_20") or 0.0))
    if prior_high <= 0 or len(day) < 24:
        return None
    for index in range(3, len(day) - 1):
        row = day.iloc[index]
        close = float(row["Close"])
        if (
            close > prior_high
            and close > float(row["vwap"])
            and _volume_ratio(row) >= 1.25
            and _volume_pace(day, meta, index) >= 1.0
        ):
            stop = close * 0.99
            take = close * 1.025
            return _finish_trade(
                ticker=ticker,
                trader_proxy="Dan Zanger",
                strategy="volume_confirmed_chart_breakout",
                day=day,
                entry_index=index,
                entry_price=close,
                stop_price=stop,
                take_profit_price=take,
            )
    return None


def kristjan_kullamagi_ep(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    if _gap_pct(day, meta) < 3.0:
        return None
    return _orb_trade(
        ticker=ticker,
        trader_proxy="Kristjan Kullamagi",
        strategy="episodic_pivot_orb",
        day=day,
        start_bar=3,
        volume_ratio_min=1.20,
        volume_pace_min=1.5,
        meta=meta,
    )


def al_brooks_price_action_pullback(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    if len(day) < 32:
        return None
    first_hour = day.iloc[:12]
    if float(first_hour["Close"].iloc[-1]) <= float(first_hour["Open"].iloc[0]):
        return None
    for index in range(12, len(day) - 1):
        row = day.iloc[index]
        prev = day.iloc[index - 1]
        close = float(row["Close"])
        if (
            close > float(row["vwap"])
            and close > float(row["ema20"])
            and float(row["ema9"]) > float(row["ema20"])
            and float(prev["Low"]) <= float(prev["ema20"]) * 1.002
            and close > float(prev["High"])
            and _volume_ratio(row) >= 0.85
        ):
            risk_pct = _clamp((close - float(prev["Low"])) / close, 0.004, 0.014)
            return _finish_trade(
                ticker=ticker,
                trader_proxy="Al Brooks",
                strategy="price_action_trend_pullback",
                day=day,
                entry_index=index,
                entry_price=close,
                stop_price=close * (1.0 - risk_pct),
                take_profit_price=close * (1.0 + risk_pct * 1.5),
            )
    return None


def john_carter_ttm_squeeze(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    if len(day) < 45:
        return None
    squeeze_seen = False
    for index in range(25, len(day) - 1):
        row = day.iloc[index]
        if bool(row.get("squeeze_on")):
            squeeze_seen = True
            continue
        if not squeeze_seen:
            continue
        close = float(row["Close"])
        upper = float(row.get("bb_upper") or 0.0)
        if (
            upper > 0
            and close > upper
            and close > float(row["vwap"])
            and float(row.get("momentum_20") or 0.0) > 0
            and _volume_ratio(row) >= 0.95
        ):
            stop = close * 0.99
            take = close * 1.02
            return _finish_trade(
                ticker=ticker,
                trader_proxy="John Carter",
                strategy="ttm_squeeze_release",
                day=day,
                entry_index=index,
                entry_price=close,
                stop_price=stop,
                take_profit_price=take,
            )
    return None


def jesse_livermore_pivotal_point(ticker: str, day: pd.DataFrame, meta: dict[str, float]) -> TradeResult | None:
    high_20 = float(meta.get("high_20") or 0.0)
    ma20 = float(meta.get("ma20") or 0.0)
    if high_20 <= 0 or ma20 <= 0 or float(meta.get("prev_close") or 0.0) < ma20:
        return None
    for index in range(3, len(day) - 1):
        row = day.iloc[index]
        close = float(row["Close"])
        if (
            close > high_20
            and close > float(row["vwap"])
            and _volume_ratio(row) >= 1.10
            and _volume_pace(day, meta, index) >= 1.0
        ):
            stop = close * 0.99
            take = close * 1.025
            return _finish_trade(
                ticker=ticker,
                trader_proxy="Jesse Livermore",
                strategy="pivotal_point_volume_breakout",
                day=day,
                entry_index=index,
                entry_price=close,
                stop_price=stop,
                take_profit_price=take,
            )
    return None


STRATEGIES: list[StrategyFunc] = [
    ross_cameron_gap_momentum,
    andrew_aziz_orb_vwap,
    toby_crabel_nr7_orb,
    linda_raschke_turtle_soup,
    mark_minervini_vcp_intraday,
    dan_zanger_volume_breakout,
    kristjan_kullamagi_ep,
    al_brooks_price_action_pullback,
    john_carter_ttm_squeeze,
    jesse_livermore_pivotal_point,
]


def _iter_days(frame: pd.DataFrame) -> Iterable[tuple[object, pd.DataFrame]]:
    for date_key, day in frame.groupby(frame.index.date):
        if len(day) >= 20:
            yield date_key, _add_indicators(day)


def summarize_trades(trades: list[TradeResult]) -> list[StrategySummary]:
    if not trades:
        return []

    frame = pd.DataFrame([asdict(trade) for trade in trades])
    summaries: list[StrategySummary] = []
    for (trader_proxy, strategy), group in frame.groupby(["trader_proxy", "strategy"]):
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
        summaries.append(
            StrategySummary(
                trader_proxy=str(trader_proxy),
                strategy=str(strategy),
                trades=len(returns),
                win_rate_pct=round(len(wins) / len(returns) * 100.0, 2),
                avg_return_pct=round(sum(returns) / len(returns), 4),
                median_return_pct=round(float(pd.Series(returns).median()), 4),
                total_return_pct=round(total_return, 3),
                profit_factor=round(profit_factor, 3),
                max_drawdown_pct=round(abs(max_drawdown), 3),
                expectancy_pct=round(sum(returns) / len(returns), 4),
                best_trade_pct=round(max(returns), 4),
                worst_trade_pct=round(min(returns), 4),
            )
        )
    return sorted(summaries, key=lambda item: item.total_return_pct, reverse=True)


def run_backtests(
    universe: list[str],
    *,
    period: str,
    interval: str,
) -> tuple[list[TradeResult], list[StrategySummary]]:
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
        stats_by_day = _daily_stats(frame)
        for date_key, day in _iter_days(frame):
            meta = stats_by_day.get(date_key, {})
            for strategy_func in STRATEGIES:
                trade = strategy_func(ticker, day, meta)
                if trade is not None:
                    trades.append(trade)
    return trades, summarize_trades(trades)


def write_outputs(
    *,
    output_dir: Path,
    trades: list[TradeResult],
    summaries: list[StrategySummary],
    payload: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(trade) for trade in trades]).to_csv(output_dir / "trades.csv", index=False)
    pd.DataFrame([asdict(summary) for summary in summaries]).to_csv(
        output_dir / "summary.csv", index=False
    )
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
        else Path("results") / "research" / "famous_day_trader_backtests" / timestamp
    )

    trades, summaries = run_backtests(universe, period=args.period, interval=args.interval)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "period": args.period,
        "interval": args.interval,
        "universe": universe,
        "slippage_bps_per_side": SLIPPAGE_BPS_PER_SIDE,
        "trade_count": len(trades),
        "summary": [asdict(summary) for summary in summaries],
        "output_dir": str(output_dir),
    }
    write_outputs(output_dir=output_dir, trades=trades, summaries=summaries, payload=payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
