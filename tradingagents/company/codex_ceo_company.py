from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import pandas as pd
import requests
import yfinance as yf
from requests import HTTPError

from tradingagents.agents.utils.market_scanner_tools import DEFAULT_DISCOVERY_UNIVERSE
from tradingagents.company.backtest_lab import run_momentum_smoke_backtest
from tradingagents.company.day_trading_strategy import classify_day_trade_setup
from tradingagents.company.technology_scout import (
    build_technology_capabilities,
    capabilities_as_dicts,
    render_technology_scout_report,
)
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.execution import AlpacaPaperBroker, OrderIntent, evaluate_order_policy


@dataclass
class MarketCandidate:
    ticker: str
    latest_price: float
    return_1d_pct: float
    return_5d_pct: float
    return_20d_pct: float
    volume_ratio: float
    volatility_20d_pct: float
    score: float
    risk_flags: List[str]
    strategy: str
    strategy_confidence: float
    strategy_note: str
    auto_trade_allowed: bool
    stop_loss_pct: float
    take_profit_pct: float
    backtest_return_pct: float = 0.0
    backtest_benchmark_pct: float = 0.0
    backtest_excess_pct: float = 0.0
    backtest_max_drawdown_pct: float = 0.0
    backtest_trades: int = 0
    backtest_passed: bool = True
    backtest_note: str = ""


@dataclass
class PortfolioOrderPlan:
    ticker: str
    side: str
    quantity: float
    latest_price: float
    estimated_notional_usd: float
    reason: str
    strategy: str = ""
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    submitted: bool = False
    blocked_reason: str | None = None
    order_response: Dict[str, Any] | None = None


@dataclass
class CompanyRunResult:
    account_status: str
    market_open: bool
    artifact_dir: str
    candidates: List[MarketCandidate]
    target_weights: Dict[str, float]
    order_plans: List[PortfolioOrderPlan]
    submitted_orders: int
    blocked_orders: int


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pct_change(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end - start) / start * 100.0


def _clean_universe(universe: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    cleaned: List[str] = []
    for item in universe:
        ticker = safe_ticker_component(str(item).strip().upper())
        if ticker and ticker not in seen:
            seen.add(ticker)
            cleaned.append(ticker)
    return cleaned


class CodexCEOCompanyRunner:
    """Compute-light company runner for Codex CEO mode.

    This workflow is intentionally smaller than the full multi-agent graph:
    market screening is deterministic, the optional local Ollama staff memo is
    one short call, and paper execution stays behind explicit guardrails.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        broker: AlpacaPaperBroker | None = None,
    ) -> None:
        self.config = config
        self.broker = broker or AlpacaPaperBroker()

    def run(
        self,
        *,
        trade_date: str | None = None,
        universe: Sequence[str] | None = None,
        submit: bool = False,
        ceo_approved: bool = False,
    ) -> CompanyRunResult:
        trade_date = trade_date or datetime.now(UTC).strftime("%Y-%m-%d")
        candidates = self.scan_market(universe or self.config.get("codex_ceo_universe", []))

        account = self.broker.get_account()
        positions_payload = self.broker.get_positions()
        positions = positions_payload.get("positions", [])
        clock = self.broker.get_clock()

        target_weights = self.build_target_weights(candidates)
        order_plans = self.build_order_plans(
            candidates=candidates,
            target_weights=target_weights,
            account=account,
            positions=positions,
        )
        self.apply_order_plans(
            order_plans,
            account=account,
            market_open=bool(clock.get("is_open")),
            submit=submit,
            ceo_approved=ceo_approved,
        )

        artifact_dir = self._artifact_dir(trade_date)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        staff_memo = self.create_ollama_staff_memo(candidates, order_plans)
        technology_capabilities = []
        technology_scout_report = ""
        if self.config.get("technology_scout_enabled", True):
            technology_capabilities = build_technology_capabilities(
                project_root=self._project_root(),
                ollama_base_url=str(self.config.get("ollama_base_url", "http://localhost:11434")),
            )
            technology_scout_report = render_technology_scout_report(
                technology_capabilities
            )
        self.write_artifacts(
            artifact_dir=artifact_dir,
            trade_date=trade_date,
            account=account,
            positions=positions,
            clock=clock,
            candidates=candidates,
            target_weights=target_weights,
            order_plans=order_plans,
            staff_memo=staff_memo,
            technology_capabilities=technology_capabilities,
            technology_scout_report=technology_scout_report,
            submit=submit,
            ceo_approved=ceo_approved,
        )

        submitted = sum(1 for order in order_plans if order.submitted)
        blocked = sum(1 for order in order_plans if order.blocked_reason)
        return CompanyRunResult(
            account_status=str(account.get("status", "unknown")),
            market_open=bool(clock.get("is_open")),
            artifact_dir=str(artifact_dir),
            candidates=candidates,
            target_weights=target_weights,
            order_plans=order_plans,
            submitted_orders=submitted,
            blocked_orders=blocked,
        )

    def scan_market(self, universe: Sequence[str] | None = None) -> List[MarketCandidate]:
        tickers = _clean_universe(universe or DEFAULT_DISCOVERY_UNIVERSE)
        max_universe = int(self.config.get("codex_ceo_max_universe", 30))
        tickers = tickers[: max(5, max_universe)]
        lookback_days = str(self.config.get("codex_ceo_history_period", "60d"))

        data = yf.download(
            tickers=tickers,
            period=lookback_days,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        candidates: List[MarketCandidate] = []
        for ticker in tickers:
            history = self._history_for_ticker(data, ticker, len(tickers) == 1)
            if history.empty or len(history) < 22:
                continue
            candidate = self._score_ticker(ticker, history)
            if candidate is not None:
                candidates.append(candidate)

        ranked = sorted(candidates, key=lambda item: item.score, reverse=True)
        limit = int(self.config.get("codex_ceo_watchlist_size", 10))
        return ranked[: max(1, limit)]

    def _history_for_ticker(
        self,
        data: pd.DataFrame,
        ticker: str,
        single_ticker: bool,
    ) -> pd.DataFrame:
        if data.empty:
            return pd.DataFrame()
        if single_ticker or not isinstance(data.columns, pd.MultiIndex):
            return data.dropna(how="all")
        if ticker not in data.columns.get_level_values(0):
            return pd.DataFrame()
        return data[ticker].dropna(how="all")

    def _score_ticker(self, ticker: str, history: pd.DataFrame) -> MarketCandidate | None:
        close = history.get("Close", pd.Series(dtype=float)).dropna()
        volume = history.get("Volume", pd.Series(dtype=float)).dropna()
        if len(close) < 22:
            return None

        latest = float(close.iloc[-1])
        if latest < float(self.config.get("codex_ceo_min_price", 5.0)):
            return None

        avg_volume = float(volume.tail(20).mean()) if len(volume) >= 20 else 0.0
        if avg_volume < float(self.config.get("codex_ceo_min_avg_volume", 1_000_000)):
            return None

        ret_1d = _pct_change(float(close.iloc[-2]), latest)
        ret_5d = _pct_change(float(close.iloc[-6]), latest)
        ret_20d = _pct_change(float(close.iloc[-21]), latest)
        daily_returns = close.pct_change().dropna().tail(20)
        vol_20d = float(daily_returns.std() * 100.0) if len(daily_returns) else 0.0
        latest_volume = float(volume.iloc[-1]) if len(volume) else 0.0
        volume_ratio = latest_volume / avg_volume if avg_volume else 0.0

        score = (
            ret_1d * 0.35
            + ret_5d * 0.45
            + ret_20d * 0.20
            + max(0.0, min(volume_ratio - 1.0, 2.0)) * 2.0
            - max(0.0, vol_20d - 3.0) * 0.6
        )
        risk_flags: List[str] = []
        if vol_20d > 4.0:
            risk_flags.append("high_volatility")
        if ret_5d > 15.0:
            risk_flags.append("extended_5d_move")
        if ret_1d < -2.0:
            risk_flags.append("weak_latest_session")
        if volume_ratio > 2.5:
            risk_flags.append("volume_spike")

        strategy = classify_day_trade_setup(
            return_1d_pct=ret_1d,
            return_5d_pct=ret_5d,
            return_20d_pct=ret_20d,
            volume_ratio=volume_ratio,
            volatility_20d_pct=vol_20d,
            risk_flags=risk_flags,
        )
        backtest = None
        if self.config.get("backtest_lab_enabled", True):
            backtest = run_momentum_smoke_backtest(
                ticker=ticker,
                history=history,
                min_bars=int(self.config.get("backtest_lab_min_bars", 40)),
                min_strategy_return_pct=float(
                    self.config.get("backtest_lab_min_strategy_return_pct", -10.0)
                ),
                min_excess_return_pct=float(
                    self.config.get("backtest_lab_min_excess_return_pct", -8.0)
                ),
            )
            score += max(-4.0, min(4.0, backtest.excess_return_pct * 0.08))
            if not backtest.passed:
                risk_flags.append("weak_backtest")

        return MarketCandidate(
            ticker=ticker,
            latest_price=round(latest, 4),
            return_1d_pct=round(ret_1d, 3),
            return_5d_pct=round(ret_5d, 3),
            return_20d_pct=round(ret_20d, 3),
            volume_ratio=round(volume_ratio, 3),
            volatility_20d_pct=round(vol_20d, 3),
            score=round(score, 3),
            risk_flags=risk_flags,
            strategy=strategy.name,
            strategy_confidence=strategy.confidence,
            strategy_note=strategy.note,
            auto_trade_allowed=strategy.auto_trade_allowed,
            stop_loss_pct=strategy.stop_loss_pct,
            take_profit_pct=strategy.take_profit_pct,
            backtest_return_pct=backtest.strategy_return_pct if backtest else 0.0,
            backtest_benchmark_pct=backtest.buy_hold_return_pct if backtest else 0.0,
            backtest_excess_pct=backtest.excess_return_pct if backtest else 0.0,
            backtest_max_drawdown_pct=backtest.max_drawdown_pct if backtest else 0.0,
            backtest_trades=backtest.trade_count if backtest else 0,
            backtest_passed=backtest.passed if backtest else True,
            backtest_note=backtest.note if backtest else "",
        )

    def build_target_weights(self, candidates: Sequence[MarketCandidate]) -> Dict[str, float]:
        count = min(
            int(self.config.get("portfolio_target_positions", 5)),
            len(candidates),
        )
        if count <= 0:
            return {}

        allowed_strategies = {
            str(item)
            for item in self.config.get(
                "day_trade_auto_strategies",
                ["momentum_breakout", "relative_strength_continuation"],
            )
        }
        min_confidence = float(self.config.get("day_trade_min_strategy_confidence", 0.58))
        selected = [
            candidate
            for candidate in candidates
            if candidate.auto_trade_allowed
            and candidate.strategy in allowed_strategies
            and candidate.strategy_confidence >= min_confidence
            and (
                candidate.backtest_passed
                or not bool(self.config.get("backtest_lab_gate_targets", True))
            )
        ][:count]
        if not selected:
            return {}
        max_weight = float(self.config.get("portfolio_max_position_weight", 0.20))
        deploy_pct = float(self.config.get("portfolio_deploy_pct", 0.60))
        raw_weight = min(max_weight, deploy_pct / count)
        return {candidate.ticker: round(raw_weight, 4) for candidate in selected}

    def build_order_plans(
        self,
        *,
        candidates: Sequence[MarketCandidate],
        target_weights: Dict[str, float],
        account: Dict[str, Any],
        positions: Sequence[Dict[str, Any]],
    ) -> List[PortfolioOrderPlan]:
        candidate_by_ticker = {candidate.ticker: candidate for candidate in candidates}
        position_by_ticker = {
            str(position.get("symbol", "")).upper(): position for position in positions
        }
        equity = _safe_float(account.get("equity"))
        buying_power = _safe_float(account.get("buying_power"))
        max_deploy = float(self.config.get("portfolio_max_deploy_usd", 1500.0))
        deploy_base = min(equity, max_deploy)
        min_order_notional = float(self.config.get("portfolio_min_order_notional_usd", 25.0))
        max_order_notional = float(self.config.get("max_order_notional_usd", 250.0))

        plans: List[PortfolioOrderPlan] = []
        for ticker, weight in target_weights.items():
            candidate = candidate_by_ticker.get(ticker)
            if candidate is None or candidate.latest_price <= 0:
                continue
            target_notional = min(deploy_base * weight, max_order_notional)
            current_market_value = _safe_float(
                position_by_ticker.get(ticker, {}).get("market_value")
            )
            delta = target_notional - current_market_value
            if abs(delta) < min_order_notional:
                continue
            if delta > 0 and delta > buying_power:
                delta = buying_power
            if abs(delta) < min_order_notional:
                continue
            side = "buy" if delta > 0 else "sell"
            quantity = abs(delta) / candidate.latest_price
            if side == "sell":
                current_qty = abs(_safe_float(position_by_ticker.get(ticker, {}).get("qty")))
                quantity = min(quantity, current_qty)
            if quantity <= 0:
                continue
            stop_loss_price = None
            take_profit_price = None
            if side == "buy":
                stop_loss_price = round(
                    candidate.latest_price * (1.0 - candidate.stop_loss_pct), 2
                )
                take_profit_price = round(
                    candidate.latest_price * (1.0 + candidate.take_profit_pct), 2
                )
            plans.append(
                PortfolioOrderPlan(
                    ticker=ticker,
                    side=side,
                    quantity=round(quantity, 4),
                    latest_price=candidate.latest_price,
                    estimated_notional_usd=round(abs(delta), 2),
                    reason=(
                        f"{candidate.strategy}: {candidate.strategy_note} "
                        f"Target starter allocation weight {weight:.1%}"
                    ),
                    strategy=candidate.strategy,
                    stop_loss_pct=candidate.stop_loss_pct if side == "buy" else None,
                    take_profit_pct=candidate.take_profit_pct if side == "buy" else None,
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price,
                )
            )

        if self.config.get("portfolio_liquidate_non_targets", False):
            for ticker, position in position_by_ticker.items():
                if ticker in target_weights:
                    continue
                qty = abs(_safe_float(position.get("qty")))
                market_value = abs(_safe_float(position.get("market_value")))
                if qty <= 0 or market_value < min_order_notional:
                    continue
                price = _safe_float(position.get("current_price"))
                if price <= 0:
                    price = market_value / qty
                plans.append(
                    PortfolioOrderPlan(
                        ticker=ticker,
                        side="sell",
                        quantity=round(qty, 4),
                        latest_price=round(price, 4),
                        estimated_notional_usd=round(market_value, 2),
                        reason="Reduce non-target starter portfolio holding",
                    )
                )

        return plans

    def apply_order_plans(
        self,
        order_plans: Sequence[PortfolioOrderPlan],
        *,
        account: Dict[str, Any],
        market_open: bool,
        submit: bool,
        ceo_approved: bool,
    ) -> None:
        approval_required = bool(self.config.get("ceo_approval_required", True))
        execution_config = {
            **self.config,
            "enforce_market_open": self.config.get("enforce_market_open", True),
        }

        for plan in order_plans:
            if submit and bool(self.config.get("refresh_live_prices_before_submit", True)):
                self._refresh_plan_price(plan)
            intent = OrderIntent(
                ticker=plan.ticker,
                side=plan.side,
                quantity=plan.quantity,
                order_class=(
                    "bracket"
                    if plan.side == "buy"
                    and bool(self.config.get("use_bracket_orders", True))
                    and plan.take_profit_price is not None
                    and plan.stop_loss_price is not None
                    else None
                ),
                take_profit_limit_price=plan.take_profit_price,
                stop_loss_stop_price=plan.stop_loss_price,
            )
            policy = evaluate_order_policy(
                intent=intent,
                account=account,
                market_open=market_open,
                latest_price=plan.latest_price,
                config=execution_config,
            )
            if not policy.allow:
                plan.blocked_reason = policy.reason
                continue
            if not submit:
                plan.blocked_reason = "dry_run"
                continue
            if approval_required and not ceo_approved:
                plan.blocked_reason = "ceo_approval_required"
                continue

            try:
                response = self.broker.submit_order(intent)
                plan.submitted = True
                plan.order_response = response
            except HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                plan.blocked_reason = f"submit_failed_http_{status}"
            except Exception as exc:
                plan.blocked_reason = f"submit_failed_{type(exc).__name__}"

    def _refresh_plan_price(self, plan: PortfolioOrderPlan) -> None:
        trade = self.broker.get_latest_trade(plan.ticker)
        price = _safe_float(trade.get("p"))
        if price <= 0:
            return
        plan.latest_price = round(price, 4)
        if plan.side == "buy":
            plan.quantity = round(plan.estimated_notional_usd / plan.latest_price, 4)
        else:
            plan.estimated_notional_usd = round(plan.quantity * plan.latest_price, 2)
        if plan.side == "buy" and plan.stop_loss_pct and plan.take_profit_pct:
            plan.stop_loss_price = round(plan.latest_price * (1.0 - plan.stop_loss_pct), 2)
            plan.take_profit_price = round(
                plan.latest_price * (1.0 + plan.take_profit_pct), 2
            )

    def create_ollama_staff_memo(
        self,
        candidates: Sequence[MarketCandidate],
        order_plans: Sequence[PortfolioOrderPlan],
    ) -> str:
        if not self.config.get("ollama_staff_memo_enabled", True):
            return ""
        model = str(self.config.get("ollama_staff_model", "qwen3:0.6b"))
        base_url = str(self.config.get("ollama_base_url", "http://localhost:11434")).rstrip("/")
        prompt = self._staff_prompt(candidates, order_plans)
        try:
            response = requests.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": float(self.config.get("ollama_temperature", 0.1)),
                        "num_ctx": int(self.config.get("ollama_num_ctx", 2048)),
                        "num_predict": int(self.config.get("ollama_num_predict", 350)),
                    },
                },
                timeout=int(self.config.get("ollama_timeout_seconds", 90)),
            )
            response.raise_for_status()
            return str(response.json().get("response", "")).strip()
        except Exception as exc:
            return f"Local Ollama staff memo unavailable: {exc}"

    def _staff_prompt(
        self,
        candidates: Sequence[MarketCandidate],
        order_plans: Sequence[PortfolioOrderPlan],
    ) -> str:
        candidate_rows = "\n".join(
            f"- {c.ticker}: score {c.score}, 5d {c.return_5d_pct}%, "
            f"20d {c.return_20d_pct}%, strategy {c.strategy} "
            f"({c.strategy_confidence}), risk {', '.join(c.risk_flags) or 'none'}"
            for c in candidates[:10]
        )
        order_rows = "\n".join(
            f"- {o.side.upper()} {o.quantity} {o.ticker}, est ${o.estimated_notional_usd}, "
            f"stop {o.stop_loss_price or 'n/a'}, take-profit {o.take_profit_price or 'n/a'}"
            for o in order_plans[:8]
        )
        return (
            "You are a lightweight local research assistant. Produce a concise "
            "staff memo for Codex CEO. Do not add new tickers. Focus on short-term "
            "paper-trading risk, catalysts, and what needs CEO review.\n\n"
            f"Candidates:\n{candidate_rows}\n\n"
            f"Proposed orders:\n{order_rows or 'No proposed orders.'}\n\n"
            "Return 5 bullets maximum."
        )

    def write_artifacts(
        self,
        *,
        artifact_dir: Path,
        trade_date: str,
        account: Dict[str, Any],
        positions: Sequence[Dict[str, Any]],
        clock: Dict[str, Any],
        candidates: Sequence[MarketCandidate],
        target_weights: Dict[str, float],
        order_plans: Sequence[PortfolioOrderPlan],
        staff_memo: str,
        technology_capabilities,
        technology_scout_report: str,
        submit: bool,
        ceo_approved: bool,
    ) -> None:
        payload = {
            "trade_date": trade_date,
            "account": self._account_summary(account),
            "positions": list(positions),
            "clock": clock,
            "candidates": [asdict(candidate) for candidate in candidates],
            "target_weights": target_weights,
            "order_plans": [asdict(plan) for plan in order_plans],
            "technology_capabilities": capabilities_as_dicts(technology_capabilities),
            "submit_requested": submit,
            "ceo_approved": ceo_approved,
            "paper_account_only": True,
        }
        (artifact_dir / "company_run.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        (artifact_dir / "ceo_briefing_pack.md").write_text(
            self._briefing_markdown(
                trade_date=trade_date,
                account=account,
                positions=positions,
                clock=clock,
                candidates=candidates,
                target_weights=target_weights,
                order_plans=order_plans,
                staff_memo=staff_memo,
                technology_scout_report=technology_scout_report,
                submit=submit,
                ceo_approved=ceo_approved,
            ),
            encoding="utf-8",
        )
        if technology_scout_report:
            (artifact_dir / "technology_scout_report.md").write_text(
                technology_scout_report,
                encoding="utf-8",
            )

    def _briefing_markdown(
        self,
        *,
        trade_date: str,
        account: Dict[str, Any],
        positions: Sequence[Dict[str, Any]],
        clock: Dict[str, Any],
        candidates: Sequence[MarketCandidate],
        target_weights: Dict[str, float],
        order_plans: Sequence[PortfolioOrderPlan],
        staff_memo: str,
        technology_scout_report: str,
        submit: bool,
        ceo_approved: bool,
    ) -> str:
        lines = [
            "# Codex CEO Briefing Pack",
            "",
            f"- Trade date: {trade_date}",
            f"- Paper account status: {account.get('status', 'unknown')}",
            f"- Market open: {clock.get('is_open', 'unknown')}",
            f"- Submit requested: {submit}",
            f"- CEO approved: {ceo_approved}",
            f"- Max deployed capital: ${float(self.config.get('portfolio_max_deploy_usd', 1500.0)):.2f}",
            "",
            "## Current Positions",
        ]
        if positions:
            lines.extend(
                [
                    "| Symbol | Qty | Market Value | Unrealized P/L |",
                    "| --- | ---: | ---: | ---: |",
                ]
            )
            for position in positions:
                lines.append(
                    "| {symbol} | {qty} | {market_value} | {upl} |".format(
                        symbol=position.get("symbol", ""),
                        qty=position.get("qty", ""),
                        market_value=position.get("market_value", ""),
                        upl=position.get("unrealized_pl", ""),
                    )
                )
        else:
            lines.append("No open positions reported by the paper account.")

        lines.extend(
            [
                "",
                "## Top 10 Market Research Candidates",
                "| Rank | Ticker | Price | 1D % | 5D % | 20D % | Vol Ratio | Strategy | Risk | Score |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |",
            ]
        )
        for rank, candidate in enumerate(candidates[:10], start=1):
            lines.append(
                "| {rank} | {ticker} | {price:.2f} | {ret1:.2f} | {ret5:.2f} | "
                "{ret20:.2f} | {vol_ratio:.2f} | {strategy} | {risk} | {score:.2f} |".format(
                    rank=rank,
                    ticker=candidate.ticker,
                    price=candidate.latest_price,
                    ret1=candidate.return_1d_pct,
                    ret5=candidate.return_5d_pct,
                    ret20=candidate.return_20d_pct,
                    vol_ratio=candidate.volume_ratio,
                    strategy=f"{candidate.strategy} ({candidate.strategy_confidence:.2f})",
                    risk=", ".join(candidate.risk_flags) or "none",
                    score=candidate.score,
                )
            )

        if self.config.get("backtest_lab_enabled", True):
            lines.extend(
                [
                    "",
                    "## Backtest Lab",
                    "| Ticker | Strategy Return | Buy/Hold | Excess | Max DD | Trades | Status |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
                ]
            )
            for candidate in candidates[:10]:
                status = "passed" if candidate.backtest_passed else "weak"
                lines.append(
                    f"| {candidate.ticker} | {candidate.backtest_return_pct:.2f}% | "
                    f"{candidate.backtest_benchmark_pct:.2f}% | "
                    f"{candidate.backtest_excess_pct:.2f}% | "
                    f"{candidate.backtest_max_drawdown_pct:.2f}% | "
                    f"{candidate.backtest_trades} | {status}: {candidate.backtest_note} |"
                )

        lines.extend(["", "## Starter Portfolio Targets"])
        if target_weights:
            lines.extend(["| Ticker | Target Weight |", "| --- | ---: |"])
            for ticker, weight in target_weights.items():
                lines.append(f"| {ticker} | {weight:.1%} |")
        else:
            lines.append("No target weights produced.")

        lines.extend(["", "## Proposed Paper Orders"])
        if order_plans:
            lines.extend(
                [
                    "| Ticker | Side | Qty | Est Notional | Stop | Take Profit | Status | Reason |",
                    "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
                ]
            )
            for order in order_plans:
                status = "submitted" if order.submitted else order.blocked_reason or "ready"
                lines.append(
                    f"| {order.ticker} | {order.side} | {order.quantity:.4f} | "
                    f"${order.estimated_notional_usd:.2f} | "
                    f"{order.stop_loss_price or ''} | {order.take_profit_price or ''} | "
                    f"{status} | {order.reason} |"
                )
        else:
            lines.append("No orders proposed.")

        if staff_memo:
            lines.extend(["", "## Local Ollama Staff Memo", staff_memo])

        if technology_scout_report:
            lines.extend(["", "## Technology Scout", technology_scout_report])

        lines.extend(
            [
                "",
                "## CEO Notes",
                "- Paper account only.",
                "- Autonomous paper mode still enforces market-open and order-size risk gates.",
                "- Orders remain blocked when the market is closed unless that policy is changed.",
            ]
        )
        return "\n".join(lines)

    def _account_summary(self, account: Dict[str, Any]) -> Dict[str, Any]:
        keys = ("status", "equity", "buying_power", "cash", "portfolio_value")
        return {key: account.get(key) for key in keys}

    def _artifact_dir(self, trade_date: str) -> Path:
        root = Path(self.config.get("results_dir", "results"))
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return root / "codex_ceo_company" / trade_date / f"run_{timestamp}"

    def _project_root(self) -> Path:
        configured = Path(self.config.get("project_dir", ".")).resolve()
        if (configured / "knowledge").exists() or (configured / ".agents").exists():
            return configured
        return configured.parent
