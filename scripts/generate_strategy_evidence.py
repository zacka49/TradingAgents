from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yfinance as yf


UNIVERSE = [
    "NVDA",
    "AVGO",
    "ARM",
    "AMD",
    "MU",
    "SMCI",
    "DELL",
    "HPE",
    "CRDO",
    "PLTR",
    "ORCL",
    "MSFT",
    "GOOGL",
    "PANW",
    "CRWD",
    "MDB",
    "QQQ",
    "SPY",
    "IWM",
    "TLT",
    "GLD",
    "XLE",
    "IBIT",
    "GBTC",
    "BITO",
    "ETHA",
    "ETHE",
    "COIN",
    "MSTR",
    "HOOD",
    "TSLA",
    "INTC",
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "XRP-USD",
    "BNB-USD",
    "DOGE-USD",
    "ADA-USD",
    "LINK-USD",
]

AI_NAMES = {"NVDA", "AVGO", "ARM", "MU", "SMCI", "DELL", "HPE", "CRDO", "PLTR", "ORCL"}
CYBER_NAMES = {"PANW", "CRWD"}
CRYPTO_LINKED_NAMES = {"IBIT", "GBTC", "BITO", "ETHA", "ETHE", "COIN", "MSTR"}
CRYPTO_NAMES = {"BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD", "DOGE-USD", "ADA-USD", "LINK-USD"}
WEAK_NAMES = {"HOOD", "TSLA", "INTC", "AMD"}
REGIME_NAMES = {"QQQ", "SPY", "IWM", "TLT", "GLD", "XLE"}


def main() -> int:
    out_dir = Path("results/research_department/strategy_evidence_2026-06-02")
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        summary = download_daily_summary()
    except Exception as exc:
        return preserve_existing_evidence(
            out_dir,
            reason=f"{type(exc).__name__}: {exc}",
        )
    if summary.empty:
        return preserve_existing_evidence(out_dir, reason="download returned no usable rows")

    scores = score_strategies(summary)
    if scores.empty:
        return preserve_existing_evidence(out_dir, reason="scoring produced no usable rows")

    summary.to_csv(out_dir / "watchlist_daily_snapshot.csv")
    scores.to_csv(out_dir / "strategy_scores.csv")

    render_relative_strength(summary, out_dir / "relative_strength_momentum.svg")
    render_momentum_volume(summary, out_dir / "momentum_volume_confirmation.svg")
    render_score_heatmap(scores, out_dir / "strategy_score_heatmap.svg")

    intraday_rows = render_intraday_lines(out_dir / "today_intraday_relative_lines.svg")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "daily_last_date": str(summary.attrs["last_date"]),
        "intraday_rows": intraday_rows,
        "top_one_day": _round_dict(
            summary[["one_day_pct", "window_pct", "volume_ratio_vs_5d"]]
            .head(12)
            .to_dict(orient="index")
        ),
        "top_strategy_scores": _round_dict(
            scores[
                [
                    "best_strategy",
                    "best_score",
                    "rs_continuation",
                    "breakout_watch",
                    "mean_reversion_fade_risk",
                    "caution_shortlist",
                ]
            ]
            .head(16)
            .to_dict(orient="index")
        ),
        "charts": [
            str(out_dir / "relative_strength_momentum.svg"),
            str(out_dir / "momentum_volume_confirmation.svg"),
            str(out_dir / "strategy_score_heatmap.svg"),
            str(out_dir / "today_intraday_relative_lines.svg"),
        ],
    }
    (out_dir / "strategy_evidence_summary.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0


def preserve_existing_evidence(out_dir: Path, *, reason: str) -> int:
    status = {
        "ok": True,
        "fresh": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "message": "Fresh strategy evidence unavailable; kept the previous successful evidence pack.",
    }
    summary_path = out_dir / "strategy_evidence_summary.json"
    if summary_path.exists():
        existing = json.loads(summary_path.read_text(encoding="utf-8"))
        top_one_day = existing.get("top_one_day", {})
        top_scores = existing.get("top_strategy_scores", {})
        if top_one_day:
            pd.DataFrame.from_dict(top_one_day, orient="index").to_csv(
                out_dir / "watchlist_daily_snapshot.csv"
            )
        if top_scores:
            pd.DataFrame.from_dict(top_scores, orient="index").to_csv(
                out_dir / "strategy_scores.csv"
            )
        status["previous_generated_at"] = existing.get("generated_at", "")
        status["previous_daily_last_date"] = existing.get("daily_last_date", "")
    (out_dir / "strategy_evidence_refresh_status.json").write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(status, indent=2))
    return 0


def download_daily_summary() -> pd.DataFrame:
    daily = yf.download(
        " ".join(UNIVERSE),
        period="10d",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
        group_by="column",
    )
    close = daily["Close"].dropna(how="all")
    volume = daily["Volume"].dropna(how="all")
    last_close = close.iloc[-1]
    prev_close = close.iloc[-2]
    first_close = close.iloc[0]
    avg_vol = volume.iloc[:-1].tail(5).mean()

    summary = pd.DataFrame(
        {
            "last_close": last_close,
            "one_day_pct": (last_close / prev_close - 1.0) * 100.0,
            "window_pct": (last_close / first_close - 1.0) * 100.0,
            "last_volume": volume.iloc[-1],
            "volume_ratio_vs_5d": volume.iloc[-1] / avg_vol.replace(0, np.nan),
        }
    ).dropna()
    summary = summary.sort_values("one_day_pct", ascending=False)
    summary.attrs["last_date"] = close.index[-1].date()
    return summary


def score_strategies(summary: pd.DataFrame) -> pd.DataFrame:
    score = pd.DataFrame(index=summary.index)
    score["rs_continuation"] = (
        summary["one_day_pct"].clip(-5, 8) / 8.0 * 35
        + summary["window_pct"].clip(-10, 30) / 30.0 * 35
        + summary["volume_ratio_vs_5d"].clip(0, 3) / 3.0 * 30
    )
    score["breakout_watch"] = (
        summary["one_day_pct"].clip(0, 12) / 12.0 * 45
        + summary["volume_ratio_vs_5d"].clip(0, 3) / 3.0 * 35
        + summary["window_pct"].clip(0, 40) / 40.0 * 20
    )
    score["mean_reversion_fade_risk"] = (
        summary["window_pct"].clip(0, 40) / 40.0 * 45
        + summary["one_day_pct"].clip(0, 15) / 15.0 * 35
        + (1 / summary["volume_ratio_vs_5d"].replace(0, np.nan)).clip(0, 2).fillna(0)
        * 10
    )
    score["caution_shortlist"] = (
        (-summary["one_day_pct"]).clip(0, 8) / 8.0 * 50
        + (-summary["window_pct"]).clip(0, 15) / 15.0 * 30
        + summary["volume_ratio_vs_5d"].clip(0, 3) / 3.0 * 20
    )

    for ticker in REGIME_NAMES:
        if ticker in score.index:
            score.loc[
                ticker,
                [
                    "rs_continuation",
                    "breakout_watch",
                    "mean_reversion_fade_risk",
                    "caution_shortlist",
                ],
            ] *= 0.65

    score = score.clip(0, 100)
    cols = [
        "rs_continuation",
        "breakout_watch",
        "mean_reversion_fade_risk",
        "caution_shortlist",
    ]
    score["best_strategy"] = score[cols].idxmax(axis=1)
    score["best_score"] = score[cols].max(axis=1)
    return score.sort_values("best_score", ascending=False)


def render_relative_strength(summary: pd.DataFrame, path: Path) -> None:
    rows = summary.sort_values("one_day_pct", ascending=True).tail(18)
    chart = SVG(width=1200, height=720, title="Relative strength into today")
    chart.text(40, 38, "1-day relative strength into today's open", 24, "bold")
    chart.text(40, 64, f"Latest daily close: {summary.attrs['last_date']}", 13)
    x0, y0, w, row_h = 230, 95, 900, 31
    values = rows["one_day_pct"].to_numpy()
    xmin = min(-1.0, float(np.nanmin(values)))
    xmax = max(1.0, float(np.nanmax(values)))
    zero_x = x0 + (0 - xmin) / (xmax - xmin) * w
    chart.line(zero_x, y0 - 10, zero_x, y0 + row_h * len(rows), "#333")
    for i, (ticker, row) in enumerate(rows.iterrows()):
        y = y0 + i * row_h
        value = float(row["one_day_pct"])
        x = x0 + (min(value, 0) - xmin) / (xmax - xmin) * w
        bar_w = abs(value) / (xmax - xmin) * w
        color = "#2ca02c" if value >= 0 else "#d62728"
        chart.text(40, y + 19, ticker, 14, "bold")
        chart.rect(x, y, max(bar_w, 2), 21, color)
        chart.text(x0 + w + 10, y + 17, f"{value:+.2f}%", 13)
    path.write_text(chart.finish(), encoding="utf-8")


def render_momentum_volume(summary: pd.DataFrame, path: Path) -> None:
    chart = SVG(width=1200, height=760, title="Momentum and volume confirmation")
    chart.text(40, 38, "Momentum + volume confirmation", 24, "bold")
    chart.text(40, 64, "X axis: multi-day momentum. Y axis: latest volume vs prior 5-day average.", 13)
    x0, y0, w, h = 95, 100, 1020, 560
    xs = summary["window_pct"].clip(-15, 50)
    ys = summary["volume_ratio_vs_5d"].clip(0, 5)
    xmin, xmax = float(xs.min()), float(xs.max())
    ymin, ymax = 0.0, max(2.0, float(ys.max()))
    chart.rect(x0, y0, w, h, "none", "#777")
    chart.line(x0, y0 + h - (1 - ymin) / (ymax - ymin) * h, x0 + w, y0 + h - (1 - ymin) / (ymax - ymin) * h, "#999", dash=True)
    for ticker, row in summary.iterrows():
        x = x0 + (float(row["window_pct"]) - xmin) / (xmax - xmin) * w
        y = y0 + h - (float(row["volume_ratio_vs_5d"]) - ymin) / (ymax - ymin) * h
        color = bucket_color(ticker)
        radius = min(18, max(5, abs(float(row["one_day_pct"])) * 0.9 + 5))
        chart.circle(x, y, radius, color, opacity=0.76)
        chart.text(x + radius + 3, y + 4, ticker, 11)
    chart.text(x0 + w / 2 - 100, y0 + h + 42, "Downloaded-window % move", 14)
    chart.text(20, y0 + h / 2, "Vol ratio", 14)
    chart.text(775, 705, "Blue=AI, purple=cyber, red=caution, orange=regime ETF, green=direct crypto", 12)
    path.write_text(chart.finish(), encoding="utf-8")


def render_score_heatmap(scores: pd.DataFrame, path: Path) -> None:
    cols = [
        ("rs_continuation", "RS continuation"),
        ("breakout_watch", "Breakout watch"),
        ("mean_reversion_fade_risk", "Fade risk"),
        ("caution_shortlist", "Caution"),
    ]
    rows = scores.head(16)
    chart = SVG(width=1100, height=760, title="Strategy evidence scores")
    chart.text(40, 38, "Strategy evidence scores", 24, "bold")
    chart.text(40, 64, "0-100 score from relative strength, extension, and volume evidence.", 13)
    x0, y0, cell_w, cell_h = 230, 105, 190, 34
    for j, (_, label) in enumerate(cols):
        chart.text(x0 + j * cell_w + 12, y0 - 16, label, 13, "bold")
    for i, (ticker, row) in enumerate(rows.iterrows()):
        y = y0 + i * cell_h
        chart.text(40, y + 23, ticker, 14, "bold")
        chart.text(92, y + 23, str(row["best_strategy"]), 11)
        for j, (col, _) in enumerate(cols):
            value = float(row[col])
            color = heat_color(value)
            x = x0 + j * cell_w
            chart.rect(x, y, cell_w - 3, cell_h - 3, color)
            text_color = "#ffffff" if value > 58 else "#111111"
            chart.text(x + cell_w / 2 - 10, y + 22, f"{value:.0f}", 13, color=text_color)
    path.write_text(chart.finish(), encoding="utf-8")


def render_intraday_lines(path: Path) -> int:
    intraday = yf.download(
        " ".join(
            [
                "NVDA",
                "AVGO",
                "ARM",
                "PANW",
                "CRWD",
                "PLTR",
                "ORCL",
                "MU",
                "QQQ",
                "SPY",
                "BTC-USD",
                "ETH-USD",
                "SOL-USD",
            ]
        ),
        period="1d",
        interval="5m",
        prepost=True,
        auto_adjust=False,
        progress=False,
        threads=False,
        group_by="column",
    )
    if not isinstance(intraday.columns, pd.MultiIndex) or "Close" not in intraday.columns.get_level_values(0):
        path.write_text(empty_svg("Today intraday lines unavailable from Yahoo"), encoding="utf-8")
        return 0
    close = intraday["Close"].dropna(how="all")
    if len(close) < 3:
        path.write_text(empty_svg("Today intraday lines unavailable before premarket data"), encoding="utf-8")
        return int(len(close))

    keep = [col for col in close.columns if close[col].notna().any()]
    norm = close[keep].ffill().bfill()
    norm = norm / norm.iloc[0] * 100.0
    chart = SVG(width=1200, height=720, title="Today extended-hours relative lines")
    chart.text(40, 38, "Today extended-hours / intraday relative lines", 24, "bold")
    chart.text(40, 64, "Normalized to first Yahoo 5-minute bar = 100.", 13)
    x0, y0, w, h = 80, 100, 1040, 520
    chart.rect(x0, y0, w, h, "none", "#777")
    ymin = float(norm.min().min())
    ymax = float(norm.max().max())
    if ymax == ymin:
        ymax += 1
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#17becf", "#bcbd22", "#7f7f7f", "#e377c2"]
    for idx, ticker in enumerate(keep):
        points = []
        series = norm[ticker].dropna()
        for pos, value in enumerate(series):
            x = x0 + pos / max(1, len(series) - 1) * w
            y = y0 + h - (float(value) - ymin) / (ymax - ymin) * h
            points.append((x, y))
        chart.polyline(points, colors[idx % len(colors)], 2)
        if points:
            chart.text(points[-1][0] + 4, points[-1][1] + 4, ticker, 11)
    path.write_text(chart.finish(), encoding="utf-8")
    return int(len(close))


def bucket_color(ticker: str) -> str:
    if ticker in CRYPTO_NAMES:
        return "#16a34a"
    if ticker in CRYPTO_LINKED_NAMES:
        return "#0f766e"
    if ticker in AI_NAMES:
        return "#1f77b4"
    if ticker in CYBER_NAMES:
        return "#9467bd"
    if ticker in WEAK_NAMES:
        return "#d62728"
    if ticker in REGIME_NAMES:
        return "#ff7f0e"
    return "#7f7f7f"


def heat_color(value: float) -> str:
    value = max(0, min(100, value))
    if value < 33:
        return "#e6f2ff"
    if value < 66:
        return "#4fa3d1"
    return "#1167a8"


def empty_svg(message: str) -> str:
    chart = SVG(width=900, height=280, title=message)
    chart.text(40, 55, message, 22, "bold")
    chart.text(40, 90, "Use the daily charts until live/pre-market bars are available.", 14)
    return chart.finish()


def _round_dict(payload: dict) -> dict:
    def round_value(value):
        if isinstance(value, float):
            return round(value, 3)
        if isinstance(value, dict):
            return {k: round_value(v) for k, v in value.items()}
        return value

    return {k: round_value(v) for k, v in payload.items()}


class SVG:
    def __init__(self, *, width: int, height: int, title: str) -> None:
        self.width = width
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            "<style>text{font-family:Arial,Helvetica,sans-serif;fill:#111}</style>",
            f"<title>{escape(title)}</title>",
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        ]

    def text(self, x: float, y: float, text: str, size: int, weight: str = "normal", color: str = "#111111") -> None:
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(str(text))}</text>'
        )

    def rect(self, x: float, y: float, w: float, h: float, fill: str, stroke: str | None = None) -> None:
        stroke_attr = f' stroke="{stroke}"' if stroke else ""
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"{stroke_attr}/>')

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str, dash: bool = False) -> None:
        dash_attr = ' stroke-dasharray="5 5"' if dash else ""
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="1"{dash_attr}/>')

    def circle(self, x: float, y: float, r: float, fill: str, opacity: float = 1.0) -> None:
        self.parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" opacity="{opacity:.2f}"/>')

    def polyline(self, points: Iterable[tuple[float, float]], color: str, width: int) -> None:
        raw = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        self.parts.append(f'<polyline points="{raw}" fill="none" stroke="{color}" stroke-width="{width}"/>')

    def finish(self) -> str:
        return "\n".join([*self.parts, "</svg>"])


if __name__ == "__main__":
    raise SystemExit(main())
