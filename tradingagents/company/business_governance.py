from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


@dataclass(frozen=True)
class BusinessLine:
    """Operating definition for one trading/research desk.

    The desk model separates idea generation from execution authority. A desk
    can research a market before the broker, data, and risk adapters are ready.
    """

    name: str
    mandate: str
    asset_classes: tuple[str, ...]
    strategies: tuple[str, ...]
    operating_status: str
    execution_authority: str
    max_capital_allocation_pct: float
    max_concurrent_positions: int
    schedule: str
    required_evidence: tuple[str, ...] = field(default_factory=tuple)
    risk_notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def can_submit_orders(self) -> bool:
        return self.execution_authority == "alpaca_paper_execution_controller"


DEFAULT_BUSINESS_LINES: tuple[BusinessLine, ...] = (
    BusinessLine(
        name="Equities Momentum Desk",
        mandate="Trade liquid US stocks and ETFs with trend, breakout, VWAP, and relative-strength continuation setups.",
        asset_classes=("us_equity", "us_etf"),
        strategies=(
            "momentum_breakout",
            "relative_strength_continuation",
            "opening_range_breakout_15m",
        ),
        operating_status="paper_trading_enabled",
        execution_authority="alpaca_paper_execution_controller",
        max_capital_allocation_pct=45.0,
        max_concurrent_positions=5,
        schedule="US cash session only; flatten intraday by close guard.",
        required_evidence=(
            "live spread and quote checks",
            "relative volume confirmation",
            "strategy classifier approval",
            "backtest smoke evidence",
        ),
        risk_notes=(
            "Avoid stacking correlated mega-cap tech names without portfolio office approval.",
            "Block weak-backtest and wide-spread setups in the safe profile.",
        ),
    ),
    BusinessLine(
        name="News Catalyst And Reversion Desk",
        mandate="Research news-shock continuation/fade behavior and promote only evidence-backed catalyst setups.",
        asset_classes=("us_equity", "us_etf", "crypto_proxy_equity"),
        strategies=(
            "news_continuation_watch",
            "news_reversion_event_study",
            "fade_or_news_watch",
        ),
        operating_status="research_and_paper_watchlist",
        execution_authority="research_only",
        max_capital_allocation_pct=15.0,
        max_concurrent_positions=2,
        schedule="Pre-open catalyst queue plus event-study reports after complete price bars exist.",
        required_evidence=(
            "dated headline",
            "bounded catalyst fact",
            "price before news",
            "price after news",
            "price one trading day after news",
            "live confirmation before any paper entry",
        ),
        risk_notes=(
            "Do not auto-fade legal, fraud, dilution, halt, bankruptcy, or regulatory shock headlines.",
            "A positive event study is research evidence, not execution authority.",
        ),
    ),
    BusinessLine(
        name="Crypto Desk",
        mandate="Research and later paper trade liquid crypto pairs separately from equity market-hour logic.",
        asset_classes=("crypto",),
        strategies=(
            "crypto_momentum",
            "crypto_range_reversion",
            "crypto_news_catalyst",
        ),
        operating_status="research_first",
        execution_authority="research_only_until_crypto_adapter",
        max_capital_allocation_pct=10.0,
        max_concurrent_positions=2,
        schedule="24/7 market; requires separate overnight/weekend risk supervision.",
        required_evidence=(
            "crypto-specific liquidity and spread checks",
            "24/7 stop and monitoring plan",
            "fee/slippage model",
            "separate paper adapter test",
        ),
        risk_notes=(
            "Do not reuse equity market-open gates for crypto.",
            "Weekend gaps, venue liquidity, and fees need separate controls.",
        ),
    ),
    BusinessLine(
        name="Macro ETF Desk",
        mandate="Trade broad liquid ETFs when macro/rates/inflation/geopolitical catalysts affect the whole market.",
        asset_classes=("us_etf",),
        strategies=(
            "macro_policy_momentum",
            "rates_inflation_rotation",
            "risk_on_risk_off",
        ),
        operating_status="paper_watchlist",
        execution_authority="alpaca_paper_execution_controller",
        max_capital_allocation_pct=20.0,
        max_concurrent_positions=3,
        schedule="US cash session; avoid new entries near major scheduled macro releases unless the catalyst desk approves.",
        required_evidence=(
            "macro catalyst tag",
            "ETF liquidity check",
            "market breadth or index confirmation",
            "portfolio correlation check",
        ),
        risk_notes=(
            "Macro ETFs can double-count risk already present in individual stock positions.",
            "Treasury, gold, and index ETF trades should be reviewed as portfolio hedges or risk-on/risk-off bets.",
        ),
    ),
    BusinessLine(
        name="Forex Research Desk",
        mandate="Research FX macro signals, but do not submit orders until a dedicated FX broker, data feed, and compliance model exist.",
        asset_classes=("forex",),
        strategies=(
            "fx_macro_research",
            "usd_rates_reaction",
            "currency_risk_context",
        ),
        operating_status="research_only",
        execution_authority="not_supported_by_current_execution_stack",
        max_capital_allocation_pct=0.0,
        max_concurrent_positions=0,
        schedule="Research only; can inform dollar, rates, gold, and ETF context.",
        required_evidence=(
            "approved FX broker adapter",
            "FX market data feed",
            "position sizing in base/quote currency",
            "rollover and leverage risk policy",
        ),
        risk_notes=(
            "Do not route FX ideas through the current Alpaca stock execution path.",
            "Use FX research as context for ETFs and multinational equities until execution support exists.",
        ),
    ),
    BusinessLine(
        name="Data Quality And Strategy Governance",
        mandate="Promote, demote, or block strategies based on evidence quality, P&L attribution, and operational readiness.",
        asset_classes=("all",),
        strategies=(
            "strategy_promotion",
            "data_quality_review",
            "pnl_attribution",
        ),
        operating_status="governance_required",
        execution_authority="no_order_authority",
        max_capital_allocation_pct=0.0,
        max_concurrent_positions=0,
        schedule="Runs before strategy promotion and after each session review.",
        required_evidence=(
            "sample size check",
            "walk-forward or event-study evidence",
            "per-desk P&L attribution",
            "data gap report",
        ),
        risk_notes=(
            "No strategy should move from research to paper trading without this gate.",
            "Zero-trade or tiny-sample backtests remain insufficient evidence.",
        ),
    ),
)


def business_lines_by_name(
    lines: Sequence[BusinessLine] = DEFAULT_BUSINESS_LINES,
) -> dict[str, BusinessLine]:
    return {line.name: line for line in lines}


def executable_business_lines(
    lines: Sequence[BusinessLine] = DEFAULT_BUSINESS_LINES,
) -> list[BusinessLine]:
    return [line for line in lines if line.can_submit_orders]


def research_only_business_lines(
    lines: Sequence[BusinessLine] = DEFAULT_BUSINESS_LINES,
) -> list[BusinessLine]:
    return [line for line in lines if not line.can_submit_orders]


def total_executable_allocation_pct(
    lines: Sequence[BusinessLine] = DEFAULT_BUSINESS_LINES,
) -> float:
    return sum(line.max_capital_allocation_pct for line in lines if line.can_submit_orders)


def validate_business_line_model(
    lines: Sequence[BusinessLine] = DEFAULT_BUSINESS_LINES,
) -> list[str]:
    errors: list[str] = []
    names = [line.name for line in lines]
    if len(set(names)) != len(names):
        errors.append("business line names must be unique")

    executable_allocation = total_executable_allocation_pct(lines)
    if executable_allocation > 100.0:
        errors.append(
            f"executable desk allocation exceeds 100%: {executable_allocation:.1f}%"
        )

    for line in lines:
        if line.max_capital_allocation_pct < 0:
            errors.append(f"{line.name}: allocation cannot be negative")
        if line.max_concurrent_positions < 0:
            errors.append(f"{line.name}: max positions cannot be negative")
        if not line.asset_classes:
            errors.append(f"{line.name}: at least one asset class is required")
        if line.can_submit_orders and line.max_concurrent_positions <= 0:
            errors.append(f"{line.name}: executable desks need position capacity")
        if line.asset_classes == ("forex",) and line.can_submit_orders:
            errors.append("Forex Research Desk must remain research-only until an FX adapter exists")
    return errors


def render_business_line_model_markdown(
    lines: Sequence[BusinessLine] = DEFAULT_BUSINESS_LINES,
) -> str:
    executable_allocation = total_executable_allocation_pct(lines)
    errors = validate_business_line_model(lines)
    lines_out = [
        "# Multi-Desk Business Operating Model",
        "",
        "This model separates desks by market, strategy behavior, and execution readiness. Research desks can generate ideas, but only desks with explicit execution authority can route paper orders.",
        "",
        "## Allocation Summary",
        f"- Executable desk allocation cap: {executable_allocation:.1f}%",
        f"- Model status: {'valid' if not errors else 'needs review'}",
    ]
    if errors:
        lines_out.extend(f"- Issue: {error}" for error in errors)

    lines_out.extend(
        [
            "",
            "## Business Lines",
            "| Desk | Status | Execution | Assets | Allocation Cap | Max Positions | Mandate |",
            "| --- | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for line in lines:
        lines_out.append(
            "| {name} | {status} | {execution} | {assets} | {allocation:.1f}% | {positions} | {mandate} |".format(
                name=_md_cell(line.name),
                status=_md_cell(line.operating_status),
                execution=_md_cell(line.execution_authority),
                assets=_md_cell(", ".join(line.asset_classes)),
                allocation=line.max_capital_allocation_pct,
                positions=line.max_concurrent_positions,
                mandate=_md_cell(line.mandate, max_len=180),
            )
        )

    lines_out.extend(["", "## Promotion Gate"])
    lines_out.extend(
        [
            "1. Research idea: desk can collect data and write a thesis.",
            "2. Paper watchlist: data quality is acceptable, but no autonomous entry.",
            "3. Paper trade candidate: strategy has enough evidence, live data gates, and risk controls.",
            "4. Approved paper strategy: Portfolio Office assigns a capital cap and position limit.",
            "5. Live candidate: out of scope for this project until explicitly approved as a separate live-broker project.",
        ]
    )

    lines_out.extend(["", "## Desk Evidence Requirements"])
    for line in lines:
        lines_out.append(f"### {line.name}")
        lines_out.append(f"- Schedule: {line.schedule}")
        for item in line.required_evidence:
            lines_out.append(f"- Evidence: {item}")
        for note in line.risk_notes:
            lines_out.append(f"- Risk: {note}")
    return "\n".join(lines_out) + "\n"


def _md_cell(value: object, *, max_len: int = 120) -> str:
    text = str(value or "").replace("|", "/").replace("\n", " ").strip()
    if len(text) > max_len:
        return f"{text[: max_len - 3]}..."
    return text
