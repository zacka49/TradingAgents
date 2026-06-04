from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Iterable, Sequence


PROMOTION_ORDER = {
    "retired": 0,
    "research_idea": 1,
    "paper_watchlist": 2,
    "paper_trade_candidate": 3,
    "approved_paper_strategy": 4,
    "live_candidate": 5,
}

TRADEABLE_PAPER_STATUSES = {"paper_trade_candidate", "approved_paper_strategy"}


@dataclass(frozen=True)
class StrategyBacktestMetrics:
    trades: int = 0
    win_rate_pct: float = 0.0
    total_return_pct: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    expectancy_pct: float = 0.0
    evidence_score: float = 0.0
    source: str = ""


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    desk: str
    asset_class: str
    hypothesis: str
    entry_rules: list[str]
    exit_rules: list[str]
    risk_rules: list[str]
    required_data: list[str]
    promotion_status: str = "research_idea"
    metrics: StrategyBacktestMetrics = field(default_factory=StrategyBacktestMetrics)
    decision: str = "research_only"
    note: str = ""
    last_reviewed: str = ""


@dataclass(frozen=True)
class StrategyResearchReport:
    generated_at: str
    source_root: str
    strategies: list[StrategyCandidate]
    approved_strategy_ids: list[str]
    paper_candidate_strategy_ids: list[str]
    blocked_strategy_ids: list[str]
    research_note: str


DEFAULT_STRATEGIES: tuple[StrategyCandidate, ...] = (
    StrategyCandidate(
        strategy_id="opening_range_breakout_15m",
        desk="Equities Momentum Desk",
        asset_class="us_equity",
        hypothesis="Liquid names that break the first 15-minute range with live volume can continue intraday.",
        entry_rules=[
            "Regular-session bars only",
            "Price breaks opening range high",
            "Live volume and VWAP confirm",
        ],
        exit_rules=["Bracket stop", "Take-profit", "Flatten by day-trader close guard"],
        risk_rules=["No wide spreads", "No stale quote", "No duplicate working order"],
        required_data=["1m or 5m intraday bars", "latest quote", "latest trade", "volume"],
        promotion_status="approved_paper_strategy",
        decision="paper_trade_allowed",
        note="Default approved paper strategy based on prior intraday evidence.",
    ),
    StrategyCandidate(
        strategy_id="momentum_breakout",
        desk="Equities Momentum Desk",
        asset_class="us_equity",
        hypothesis="Strong price momentum with relative volume and clean liquidity can continue intraday.",
        entry_rules=["Price breaks recent high", "VWAP confirmation", "Relative volume confirmation"],
        exit_rules=["Bracket stop", "Take-profit", "Flatten by day-trader close guard"],
        risk_rules=["Block weak backtest in safe profile", "Block wide spreads", "Cap correlated exposure"],
        required_data=["daily bars", "intraday bars", "latest quote", "relative volume"],
        promotion_status="approved_paper_strategy",
        decision="paper_trade_allowed",
        note="Default approved paper strategy based on positive backtest family evidence.",
    ),
    StrategyCandidate(
        strategy_id="relative_strength_continuation",
        desk="Equities Momentum Desk",
        asset_class="us_equity",
        hypothesis="Strong multi-day relative strength can continue when latest-session action is not exhausted.",
        entry_rules=["5D and 20D strength", "No latest-session exhaustion", "Live liquidity confirmation"],
        exit_rules=["Bracket stop", "Take-profit", "Flatten by day-trader close guard"],
        risk_rules=["Use selectively", "Require higher confidence", "Avoid crowded sector stacking"],
        required_data=["daily bars", "intraday confirmation", "quote spread", "volume"],
        promotion_status="paper_trade_candidate",
        decision="paper_trade_allowed",
        note="Allowed selectively; lower evidence quality than ORB and momentum breakout.",
    ),
    StrategyCandidate(
        strategy_id="vwap_reclaim",
        desk="Equities Momentum Desk",
        asset_class="us_equity",
        hypothesis="A reclaim of VWAP after early weakness may mean buyers regained control.",
        entry_rules=["Prior trade below VWAP", "Close reclaims VWAP", "Volume confirms"],
        exit_rules=["Stop below reclaim/VWAP", "Take-profit near measured risk"],
        risk_rules=["Research-only until positive out-of-sample evidence"],
        required_data=["intraday bars", "VWAP", "quote spread", "volume"],
        promotion_status="research_idea",
        decision="research_only",
        note="Recent validation did not support autonomous paper trading.",
    ),
    StrategyCandidate(
        strategy_id="range_reversion_to_vwap",
        desk="Equities Momentum Desk",
        asset_class="us_equity",
        hypothesis="Oversold intraday moves can revert toward VWAP in range-bound names.",
        entry_rules=["Price below VWAP by volatility band", "RSI weakness", "Support confirmation"],
        exit_rules=["Stop below support", "Target VWAP"],
        risk_rules=["Research-only; avoid catching strong downtrends"],
        required_data=["intraday bars", "VWAP", "RSI", "volatility band"],
        promotion_status="retired",
        decision="blocked",
        note="Recent validation was negative; keep out of autonomous execution.",
    ),
    StrategyCandidate(
        strategy_id="news_reversion_event_study",
        desk="News Catalyst And Reversion Desk",
        asset_class="us_equity",
        hypothesis="Some news-shock moves revert toward the pre-news close one trading day later.",
        entry_rules=["Dated headline", "Qualified event move", "One-day reversion evidence"],
        exit_rules=["No autonomous execution", "Paper watch only after promotion"],
        risk_rules=["Block legal/fraud/halt/dilution/bankruptcy shocks", "Deduplicate same-session headlines"],
        required_data=["headline timestamp", "previous close", "event close", "next close"],
        promotion_status="research_idea",
        decision="research_only",
        note="News reversion remains research-only until event studies improve.",
    ),
    StrategyCandidate(
        strategy_id="crypto_momentum",
        desk="Crypto Desk",
        asset_class="crypto",
        hypothesis="Liquid crypto pairs and crypto proxies may trend after momentum confirmation.",
        entry_rules=["Trend confirmation", "Volume/liquidity confirmation", "24/7 risk plan"],
        exit_rules=["Crypto-specific stop", "24/7 monitoring", "Fee-aware target"],
        risk_rules=["No autonomous execution until crypto adapter and fee model are approved"],
        required_data=["crypto bars", "crypto quotes", "fees", "24/7 risk monitor"],
        promotion_status="research_idea",
        decision="research_only",
        note="Research-first because the current execution stack is equity-shaped.",
    ),
    StrategyCandidate(
        strategy_id="general_momentum_watch",
        desk="Equities Momentum Desk",
        asset_class="us_equity",
        hypothesis="Generic momentum can be interesting but is too broad for autonomous execution.",
        entry_rules=["No autonomous entry"],
        exit_rules=["Watchlist only"],
        risk_rules=["Needs a named promoted setup before trading"],
        required_data=["daily bars", "live confirmation"],
        promotion_status="paper_watchlist",
        decision="watch_only",
        note="Watchlist label, not a tradeable strategy.",
    ),
    StrategyCandidate(
        strategy_id="pullback_watch",
        desk="Equities Momentum Desk",
        asset_class="us_equity",
        hypothesis="Strong trends that pull back may become tradable if live reclaim/support confirms.",
        entry_rules=["No autonomous entry until confirmation strategy is promoted"],
        exit_rules=["Watchlist only"],
        risk_rules=["Avoid buying weakness without reclaim confirmation"],
        required_data=["daily bars", "VWAP/support confirmation"],
        promotion_status="paper_watchlist",
        decision="watch_only",
        note="Watchlist label, not a tradeable strategy.",
    ),
    StrategyCandidate(
        strategy_id="range_reversion_watch",
        desk="Equities Momentum Desk",
        asset_class="us_equity",
        hypothesis="Choppy names can revert in range, but need explicit support/resistance and tighter testing.",
        entry_rules=["No autonomous entry"],
        exit_rules=["Watchlist only"],
        risk_rules=["Avoid untested range fades"],
        required_data=["support/resistance", "intraday bars", "quote spread"],
        promotion_status="paper_watchlist",
        decision="watch_only",
        note="Watchlist label, not a tradeable strategy.",
    ),
    StrategyCandidate(
        strategy_id="fade_or_news_watch",
        desk="News Catalyst And Reversion Desk",
        asset_class="us_equity",
        hypothesis="Extended or news-driven moves can reverse, but the edge is specialist and unstable.",
        entry_rules=["No autonomous entry"],
        exit_rules=["Watchlist only"],
        risk_rules=["Requires fresh catalyst review and event-study evidence"],
        required_data=["headline facts", "event bars", "live quote"],
        promotion_status="paper_watchlist",
        decision="watch_only",
        note="Watchlist label, not a tradeable strategy.",
    ),
)


def build_strategy_research_report(
    *,
    evidence_root: str | Path | None = None,
    now: datetime | None = None,
) -> StrategyResearchReport:
    now = now or datetime.now(UTC)
    source_root = str(evidence_root or "")
    strategies = {strategy.strategy_id: strategy for strategy in DEFAULT_STRATEGIES}
    if evidence_root:
        root = Path(evidence_root)
        _apply_intraday_backtest_evidence(strategies, root)
        _apply_news_reversion_evidence(strategies, root)
        _apply_crypto_evidence(strategies, root)

    ordered = sorted(
        strategies.values(),
        key=lambda item: (
            PROMOTION_ORDER.get(item.promotion_status, 0),
            item.metrics.evidence_score,
            item.strategy_id,
        ),
        reverse=True,
    )
    approved = [
        item.strategy_id
        for item in ordered
        if item.promotion_status == "approved_paper_strategy"
    ]
    paper_candidates = [
        item.strategy_id
        for item in ordered
        if item.promotion_status == "paper_trade_candidate"
    ]
    blocked = [
        item.strategy_id
        for item in ordered
        if item.promotion_status in {"retired", "research_idea"}
        or item.decision in {"blocked", "research_only"}
    ]
    return StrategyResearchReport(
        generated_at=now.isoformat(),
        source_root=source_root,
        strategies=ordered,
        approved_strategy_ids=approved,
        paper_candidate_strategy_ids=paper_candidates,
        blocked_strategy_ids=sorted(set(blocked)),
        research_note=(
            "Quant research owns strategy discovery and promotion. Trading may "
            "only use strategies at paper_trade_candidate or approved_paper_strategy status."
        ),
    )


def load_strategy_research_report(path: str | Path) -> StrategyResearchReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return _report_from_dict(payload)


def write_strategy_library(
    report: StrategyResearchReport,
    *,
    output_dir: str | Path,
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "strategy_research_report.json"
    markdown_path = output / "strategy_research_report.md"
    approved_path = output / "approved_paper_strategies.json"
    research_path = output / "research_ideas.json"
    retired_path = output / "retired_strategies.json"

    report_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    markdown_path.write_text(render_strategy_research_report(report), encoding="utf-8")
    approved_path.write_text(
        json.dumps(
            [asdict(item) for item in report.strategies if item.strategy_id in set(report.approved_strategy_ids)],
            indent=2,
        ),
        encoding="utf-8",
    )
    research_path.write_text(
        json.dumps(
            [
                asdict(item)
                for item in report.strategies
                if item.promotion_status in {"research_idea", "paper_watchlist", "paper_trade_candidate"}
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    retired_path.write_text(
        json.dumps(
            [asdict(item) for item in report.strategies if item.promotion_status == "retired"],
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "report_json": str(report_path),
        "report_markdown": str(markdown_path),
        "approved": str(approved_path),
        "research": str(research_path),
        "retired": str(retired_path),
    }


def render_strategy_research_report(report: StrategyResearchReport) -> str:
    lines = [
        "# Strategy Research Department Report",
        "",
        f"- Generated: {report.generated_at}",
        f"- Evidence root: {report.source_root or 'defaults only'}",
        f"- Approved paper strategies: {', '.join(report.approved_strategy_ids) or 'none'}",
        f"- Paper trade candidates: {', '.join(report.paper_candidate_strategy_ids) or 'none'}",
        f"- Blocked/research-only strategies: {', '.join(report.blocked_strategy_ids) or 'none'}",
        "",
        "## Strategy Library",
        "| Strategy | Desk | Status | Decision | Trades | Return | Profit Factor | Max DD | Evidence | Note |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for strategy in report.strategies:
        metrics = strategy.metrics
        lines.append(
            "| {strategy} | {desk} | {status} | {decision} | {trades} | {ret:.2f}% | {pf:.2f} | {dd:.2f}% | {score:.2f} | {note} |".format(
                strategy=_md(strategy.strategy_id),
                desk=_md(strategy.desk),
                status=_md(strategy.promotion_status),
                decision=_md(strategy.decision),
                trades=metrics.trades,
                ret=metrics.total_return_pct,
                pf=metrics.profit_factor,
                dd=metrics.max_drawdown_pct,
                score=metrics.evidence_score,
                note=_md(strategy.note, 160),
            )
        )
    lines.extend(
        [
            "",
            "## Trading Handoff Rule",
            "Trading may only create autonomous paper orders from `paper_trade_candidate` or `approved_paper_strategy` strategies. Research, watchlist, and retired strategies may explain candidates but must not submit orders.",
        ]
    )
    return "\n".join(lines) + "\n"


def strategy_decision_for_name(
    report: StrategyResearchReport,
    strategy_id: str,
) -> StrategyCandidate:
    normalized = str(strategy_id).strip()
    for strategy in report.strategies:
        if strategy.strategy_id == normalized:
            return strategy
    return StrategyCandidate(
        strategy_id=normalized,
        desk="Unknown",
        asset_class="unknown",
        hypothesis="No quant research record exists for this strategy.",
        entry_rules=["No autonomous entry"],
        exit_rules=["Research only"],
        risk_rules=["Strategy must be researched and promoted before trading"],
        required_data=[],
        promotion_status="research_idea",
        decision="research_only",
        note="Unknown strategy blocked by strategy research gate.",
    )


def strategy_status_allows_paper_trade(
    status: str,
    *,
    minimum_status: str = "paper_trade_candidate",
) -> bool:
    return PROMOTION_ORDER.get(status, 0) >= PROMOTION_ORDER.get(minimum_status, 3)


def _apply_intraday_backtest_evidence(
    strategies: dict[str, StrategyCandidate],
    root: Path,
) -> None:
    for path in _latest_paths(root, "strategy_aggregate.csv"):
        for row in _read_csv_rows(path):
            strategy_id = str(row.get("strategy") or "").strip()
            if not strategy_id:
                continue
            trades = int(_float(row.get("trades")))
            total_return = _float(row.get("avg_total_return_pct"))
            profit_factor = _float(row.get("avg_profit_factor"))
            max_drawdown = _float(row.get("avg_max_drawdown_pct"))
            win_rate = _float(row.get("avg_win_rate_pct"))
            score = _float(row.get("avg_score"))
            metrics = StrategyBacktestMetrics(
                trades=trades,
                win_rate_pct=round(win_rate, 3),
                total_return_pct=round(total_return, 3),
                profit_factor=round(profit_factor, 3),
                max_drawdown_pct=round(max_drawdown, 3),
                evidence_score=round(score, 3),
                source=str(path),
            )
            if trades >= 100 and total_return > 1.0 and profit_factor >= 1.15 and max_drawdown <= 6.0:
                status = "approved_paper_strategy"
                decision = "paper_trade_allowed"
                note = "Promoted by intraday aggregate backtest evidence."
            elif trades >= 60 and total_return > 0.0 and profit_factor >= 1.05:
                status = "paper_trade_candidate"
                decision = "paper_trade_allowed"
                note = "Positive but not strong enough for full approved status."
            elif trades >= 50 and (total_return <= 0.0 or profit_factor < 1.0):
                status = "retired"
                decision = "blocked"
                note = "Demoted by negative aggregate backtest evidence."
            else:
                status = "paper_watchlist"
                decision = "watch_only"
                note = "Insufficient aggregate evidence for autonomous trading."
            _update_strategy_from_metrics(
                strategies,
                strategy_id,
                metrics=metrics,
                promotion_status=status,
                decision=decision,
                note=note,
            )
        return


def _apply_news_reversion_evidence(
    strategies: dict[str, StrategyCandidate],
    root: Path,
) -> None:
    for path in _latest_paths(root, "news_reversion_event_study.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        eligible = int(_float(payload.get("eligible_event_count")))
        win_rate = _float(payload.get("win_rate_pct"))
        avg_return = _float(payload.get("avg_fade_return_pct"))
        capture = _float(payload.get("avg_reversion_capture_pct"))
        metrics = StrategyBacktestMetrics(
            trades=eligible,
            win_rate_pct=round(win_rate, 3),
            total_return_pct=round(avg_return, 3),
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            expectancy_pct=round(avg_return, 3),
            evidence_score=round(avg_return + win_rate / 20.0 + capture / 50.0, 3),
            source=str(path),
        )
        if eligible >= 20 and win_rate >= 55.0 and avg_return > 0.15 and capture > 25.0:
            status = "paper_trade_candidate"
            decision = "paper_trade_allowed"
            note = "News reversion event study is positive enough for paper candidate review."
        elif eligible >= 5 and avg_return <= 0.0:
            status = "research_idea"
            decision = "research_only"
            note = "Recent event study is negative; keep research-only."
        else:
            status = "paper_watchlist"
            decision = "watch_only"
            note = "Event study sample is too small for promotion."
        _update_strategy_from_metrics(
            strategies,
            "news_reversion_event_study",
            metrics=metrics,
            promotion_status=status,
            decision=decision,
            note=note,
        )
        return


def _apply_crypto_evidence(
    strategies: dict[str, StrategyCandidate],
    root: Path,
) -> None:
    for path in _latest_paths(root, "crypto_proxy_momentum_smoke.json"):
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list) or not rows:
            continue
        returns = [_float(row.get("strategy_return_pct")) for row in rows if isinstance(row, dict)]
        excess = [_float(row.get("excess_return_pct")) for row in rows if isinstance(row, dict)]
        passed = [row for row in rows if isinstance(row, dict) and row.get("passed")]
        avg_return = sum(returns) / len(returns) if returns else 0.0
        avg_excess = sum(excess) / len(excess) if excess else 0.0
        metrics = StrategyBacktestMetrics(
            trades=len(rows),
            total_return_pct=round(avg_return, 3),
            profit_factor=0.0,
            max_drawdown_pct=max((_float(row.get("max_drawdown_pct")) for row in rows if isinstance(row, dict)), default=0.0),
            evidence_score=round(avg_return + avg_excess / 2.0 + len(passed), 3),
            source=str(path),
        )
        if avg_return > 2.0 and len(passed) >= 4:
            status = "paper_watchlist"
            decision = "watch_only"
            note = "Crypto momentum has research value, but execution adapter/risk gates are not approved."
        else:
            status = "research_idea"
            decision = "research_only"
            note = "Crypto evidence is not strong enough and execution support is incomplete."
        _update_strategy_from_metrics(
            strategies,
            "crypto_momentum",
            metrics=metrics,
            promotion_status=status,
            decision=decision,
            note=note,
        )
        return


def _update_strategy_from_metrics(
    strategies: dict[str, StrategyCandidate],
    strategy_id: str,
    *,
    metrics: StrategyBacktestMetrics,
    promotion_status: str,
    decision: str,
    note: str,
) -> None:
    existing = strategies.get(strategy_id) or StrategyCandidate(
        strategy_id=strategy_id,
        desk="Strategy Research Department",
        asset_class="unknown",
        hypothesis="Generated from discovered strategy evidence.",
        entry_rules=["See source backtest artifact"],
        exit_rules=["See source backtest artifact"],
        risk_rules=["Requires explicit promotion before trading"],
        required_data=["Backtest artifact"],
    )
    strategies[strategy_id] = StrategyCandidate(
        strategy_id=existing.strategy_id,
        desk=existing.desk,
        asset_class=existing.asset_class,
        hypothesis=existing.hypothesis,
        entry_rules=existing.entry_rules,
        exit_rules=existing.exit_rules,
        risk_rules=existing.risk_rules,
        required_data=existing.required_data,
        promotion_status=promotion_status,
        metrics=metrics,
        decision=decision,
        note=note,
        last_reviewed=datetime.now(UTC).isoformat(),
    )


def _latest_paths(root: Path, name: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob(name), key=lambda path: path.stat().st_mtime, reverse=True)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except Exception:
        return []


def _report_from_dict(payload: dict[str, Any]) -> StrategyResearchReport:
    return StrategyResearchReport(
        generated_at=str(payload.get("generated_at") or ""),
        source_root=str(payload.get("source_root") or ""),
        strategies=[
            _strategy_from_dict(item)
            for item in payload.get("strategies", [])
            if isinstance(item, dict)
        ],
        approved_strategy_ids=[str(item) for item in payload.get("approved_strategy_ids", [])],
        paper_candidate_strategy_ids=[
            str(item) for item in payload.get("paper_candidate_strategy_ids", [])
        ],
        blocked_strategy_ids=[str(item) for item in payload.get("blocked_strategy_ids", [])],
        research_note=str(payload.get("research_note") or ""),
    )


def _strategy_from_dict(payload: dict[str, Any]) -> StrategyCandidate:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    return StrategyCandidate(
        strategy_id=str(payload.get("strategy_id") or ""),
        desk=str(payload.get("desk") or ""),
        asset_class=str(payload.get("asset_class") or ""),
        hypothesis=str(payload.get("hypothesis") or ""),
        entry_rules=[str(item) for item in payload.get("entry_rules", [])],
        exit_rules=[str(item) for item in payload.get("exit_rules", [])],
        risk_rules=[str(item) for item in payload.get("risk_rules", [])],
        required_data=[str(item) for item in payload.get("required_data", [])],
        promotion_status=str(payload.get("promotion_status") or "research_idea"),
        metrics=StrategyBacktestMetrics(
            trades=int(_float(metrics.get("trades"))),
            win_rate_pct=_float(metrics.get("win_rate_pct")),
            total_return_pct=_float(metrics.get("total_return_pct")),
            profit_factor=_float(metrics.get("profit_factor")),
            max_drawdown_pct=_float(metrics.get("max_drawdown_pct")),
            expectancy_pct=_float(metrics.get("expectancy_pct")),
            evidence_score=_float(metrics.get("evidence_score")),
            source=str(metrics.get("source") or ""),
        ),
        decision=str(payload.get("decision") or "research_only"),
        note=str(payload.get("note") or ""),
        last_reviewed=str(payload.get("last_reviewed") or ""),
    )


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _md(value: Any, max_len: int = 120) -> str:
    text = str(value or "").replace("|", "/").replace("\n", " ").strip()
    if len(text) > max_len:
        return f"{text[: max_len - 3]}..."
    return text
