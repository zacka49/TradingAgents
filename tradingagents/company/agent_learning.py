from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class AgentScorecard:
    agent: str
    score: int
    grade: str
    signals: List[str]
    gaps: List[str]
    next_actions: List[str]


@dataclass(frozen=True)
class PostMarketReview:
    trade_date: str
    run_count: int
    average_score: float
    scorecards: List[AgentScorecard]
    lessons_by_agent: Dict[str, List[str]]
    artifact_paths: List[str]
    order_summary: Dict[str, Any]
    candidate_summary: Dict[str, Any]


class SpecialistMemoryLog:
    """Append-only per-agent learning memory.

    This stores compact operational lessons by specialist role. It is not model
    training; it is durable local context that future prompts and human reviews
    can consume without hosted token spend.
    """

    _SEPARATOR = "\n\n<!-- SPECIALIST_MEMORY_ENTRY_END -->\n\n"

    def __init__(self, memory_dir: str | Path, max_entries: int = 30):
        self.memory_dir = Path(memory_dir).expanduser()
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries

    def store_review(self, review: PostMarketReview) -> List[str]:
        written: List[str] = []
        scorecard_by_agent = {card.agent: card for card in review.scorecards}
        for agent, lessons in review.lessons_by_agent.items():
            if not lessons:
                continue
            card = scorecard_by_agent.get(agent)
            path = self.memory_dir / f"{_slug(agent)}_memory.md"
            entry = self._format_entry(review.trade_date, agent, lessons, card)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(entry)
            self._rotate(path)
            written.append(str(path))
        return written

    def get_context(self, agent: str, n: int = 3) -> str:
        path = self.memory_dir / f"{_slug(agent)}_memory.md"
        if not path.exists():
            return ""
        entries = [
            entry.strip()
            for entry in path.read_text(encoding="utf-8").split(self._SEPARATOR)
            if entry.strip()
        ]
        if not entries:
            return ""
        return "\n\n".join(entries[-max(1, n):])

    def get_contexts(self, agents: Sequence[str], n: int = 3) -> Dict[str, str]:
        return {
            agent: context
            for agent in agents
            if (context := self.get_context(agent, n=n))
        }

    def _format_entry(
        self,
        trade_date: str,
        agent: str,
        lessons: Sequence[str],
        card: AgentScorecard | None,
    ) -> str:
        score = card.score if card else 0
        grade = card.grade if card else "n/a"
        lines = [
            f"[{trade_date} | {agent} | score {score} | grade {grade}]",
            "",
            "LESSONS:",
        ]
        lines.extend(f"- {_one_line(lesson)}" for lesson in lessons[:8])
        if card and card.next_actions:
            lines.extend(["", "NEXT ACTIONS:"])
            lines.extend(f"- {_one_line(action)}" for action in card.next_actions[:5])
        return "\n".join(lines).strip() + self._SEPARATOR

    def _rotate(self, path: Path) -> None:
        if self.max_entries <= 0 or not path.exists():
            return
        entries = [
            entry
            for entry in path.read_text(encoding="utf-8").split(self._SEPARATOR)
            if entry.strip()
        ]
        if len(entries) <= self.max_entries:
            return
        kept = entries[-self.max_entries :]
        path.write_text(
            self._SEPARATOR.join(kept) + self._SEPARATOR,
            encoding="utf-8",
        )


def build_agent_scorecards(payload: Dict[str, Any]) -> List[AgentScorecard]:
    candidates = _as_list(payload.get("candidates"))
    orders = _as_list(payload.get("order_plans"))
    diagnostics = _as_list(payload.get("order_plan_diagnostics"))
    catalyst_context = _as_dict(payload.get("catalyst_context"))

    return [
        _market_scorecard(candidates),
        _news_scorecard(candidates, catalyst_context),
        _risk_scorecard(payload, candidates, orders, diagnostics),
        _portfolio_scorecard(payload, candidates, orders, diagnostics),
        _ceo_scorecard(payload, orders),
        _local_ai_staff_scorecard(payload),
    ]


def render_agent_scorecards_markdown(scorecards: Sequence[AgentScorecard]) -> str:
    lines = [
        "# AI Agent Scorecards",
        "",
        "| Agent | Score | Grade | Main Signals | Gaps |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for card in scorecards:
        lines.append(
            "| {agent} | {score} | {grade} | {signals} | {gaps} |".format(
                agent=_md(card.agent),
                score=card.score,
                grade=card.grade,
                signals=_md("; ".join(card.signals[:3]) or "none", 180),
                gaps=_md("; ".join(card.gaps[:3]) or "none", 180),
            )
        )
    lines.extend(["", "## Next Actions"])
    for card in scorecards:
        if not card.next_actions:
            continue
        lines.append("")
        lines.append(f"### {card.agent}")
        lines.extend(f"- {_one_line(action)}" for action in card.next_actions[:5])
    return "\n".join(lines).strip() + "\n"


def find_company_run_payloads(
    results_dir: str | Path,
    trade_date: str | None = None,
) -> List[tuple[Path, Dict[str, Any]]]:
    root = Path(results_dir)
    if not root.exists():
        return []
    payloads: List[tuple[Path, Dict[str, Any]]] = []
    for path in sorted(root.rglob("company_run.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if trade_date and str(payload.get("trade_date")) != trade_date:
            continue
        payloads.append((path, payload))
    return payloads


def build_post_market_review(
    payloads: Sequence[tuple[Path, Dict[str, Any]]],
    trade_date: str,
) -> PostMarketReview:
    run_scorecards: List[AgentScorecard] = []
    artifact_paths: List[str] = []
    all_candidates: List[Dict[str, Any]] = []
    all_orders: List[Dict[str, Any]] = []
    for path, payload in payloads:
        artifact_paths.append(str(path.parent))
        all_candidates.extend(_as_list(payload.get("candidates")))
        all_orders.extend(_as_list(payload.get("order_plans")))
        saved = payload.get("agent_scorecards")
        if isinstance(saved, list) and saved:
            run_scorecards.extend(_scorecard_from_dict(item) for item in saved)
        else:
            run_scorecards.extend(build_agent_scorecards(payload))

    aggregate = _aggregate_scorecards(run_scorecards)
    average = (
        round(sum(card.score for card in aggregate) / len(aggregate), 1)
        if aggregate
        else 0.0
    )
    review = PostMarketReview(
        trade_date=trade_date,
        run_count=len(payloads),
        average_score=average,
        scorecards=aggregate,
        lessons_by_agent=_lessons_by_agent(aggregate),
        artifact_paths=artifact_paths,
        order_summary=_summarize_orders(all_orders),
        candidate_summary=_summarize_candidates(all_candidates),
    )
    return review


def render_post_market_review_markdown(review: PostMarketReview) -> str:
    lines = [
        "# Post-Market AI Review",
        "",
        f"- Trade date: {review.trade_date}",
        f"- Reviewed runs: {review.run_count}",
        f"- Average agent score: {review.average_score:.1f}",
        "",
        "## Candidate Summary",
        f"- Candidates reviewed: {review.candidate_summary.get('count', 0)}",
        f"- Auto-trade eligible: {review.candidate_summary.get('auto_trade_allowed', 0)}",
        f"- Backtest pass rate: {review.candidate_summary.get('backtest_pass_rate', 'n/a')}",
        "",
        "## Order Summary",
        f"- Proposed orders: {review.order_summary.get('count', 0)}",
        f"- Submitted orders: {review.order_summary.get('submitted', 0)}",
        f"- Blocked orders: {review.order_summary.get('blocked', 0)}",
        f"- Block reasons: {review.order_summary.get('blocked_reasons', {})}",
        "",
        render_agent_scorecards_markdown(review.scorecards).strip(),
        "",
        "## Specialist Lessons",
    ]
    for agent, lessons in review.lessons_by_agent.items():
        lines.extend(["", f"### {agent}"])
        lines.extend(f"- {_one_line(lesson)}" for lesson in lessons)
    if review.artifact_paths:
        lines.extend(["", "## Reviewed Artifacts"])
        lines.extend(f"- {path}" for path in review.artifact_paths)
    return "\n".join(lines).strip() + "\n"


def write_post_market_review(
    *,
    results_dir: str | Path,
    trade_date: str,
    output_dir: str | Path | None = None,
    memory_dir: str | Path | None = None,
    update_memory: bool = True,
    max_memory_entries: int = 30,
) -> Dict[str, Any]:
    payloads = find_company_run_payloads(results_dir, trade_date)
    review = build_post_market_review(payloads, trade_date)

    root = Path(output_dir) if output_dir else Path(results_dir) / "post_market_reviews" / trade_date
    root.mkdir(parents=True, exist_ok=True)
    review_json = root / "post_market_review.json"
    review_md = root / "post_market_review.md"
    review_json.write_text(
        json.dumps(_review_to_dict(review), indent=2),
        encoding="utf-8",
    )
    review_md.write_text(
        render_post_market_review_markdown(review),
        encoding="utf-8",
    )

    memory_paths: List[str] = []
    if update_memory and memory_dir:
        memory_paths = SpecialistMemoryLog(
            memory_dir,
            max_entries=max_memory_entries,
        ).store_review(review)

    return {
        "trade_date": trade_date,
        "run_count": review.run_count,
        "average_score": review.average_score,
        "review_json": str(review_json),
        "review_markdown": str(review_md),
        "memory_paths": memory_paths,
    }


def _market_scorecard(candidates: Sequence[Dict[str, Any]]) -> AgentScorecard:
    score = 45
    signals: List[str] = []
    gaps: List[str] = []
    actions: List[str] = []
    count = len(candidates)
    if count:
        signals.append(f"{count} candidates ranked")
        score += 15
    else:
        gaps.append("No candidates survived market scan")
        actions.append("Widen or refresh the universe before the next premarket run")

    auto_count = sum(1 for item in candidates if item.get("auto_trade_allowed"))
    if auto_count:
        signals.append(f"{auto_count} candidates met auto-trade strategy filters")
        score += 10
    else:
        gaps.append("No candidate met auto-trade strategy filters")

    fit_scores = [_safe_float(item.get("day_trade_fit_score")) for item in candidates]
    if fit_scores and max(fit_scores) >= 4.0:
        signals.append("At least one candidate had strong day-trade fit")
        score += 10
    elif candidates:
        gaps.append("Day-trade fit scores were modest")
        actions.append("Tune liquidity, spread, and volatility thresholds by outcome")

    backtests = [item for item in candidates if "backtest_passed" in item]
    if backtests and all(bool(item.get("backtest_passed")) for item in backtests[:10]):
        signals.append("Top candidates passed backtest gate")
        score += 10
    elif backtests:
        gaps.append("Some candidates failed or lacked backtest confirmation")
        actions.append("Review whether weak backtest candidates should be blocked earlier")

    risk_flags = sum(len(_as_list(item.get("risk_flags"))) for item in candidates)
    if risk_flags > max(3, count):
        gaps.append("Risk flags were dense across candidates")
        score -= 10
    return _card("Market Analyst", score, signals, gaps, actions)


def _news_scorecard(
    candidates: Sequence[Dict[str, Any]],
    catalyst_context: Dict[str, Any],
) -> AgentScorecard:
    score = 40
    signals: List[str] = []
    gaps: List[str] = []
    actions: List[str] = []
    queue = _as_list(catalyst_context.get("ranked_research_queue"))
    if queue:
        signals.append(f"{len(queue)} catalyst research queue items")
        score += 20
    else:
        gaps.append("No ranked catalyst research queue found")
        actions.append("Run premarket catalyst research before market open")

    tagged = [
        item
        for item in candidates
        if _as_list(item.get("catalyst_tags"))
        or _as_list(item.get("news_catalysts"))
        or _as_list(item.get("news_headlines"))
        or _as_list(item.get("political_themes"))
    ]
    if tagged:
        signals.append(f"{len(tagged)} candidates carried news or policy context")
        score += 20
    elif candidates:
        gaps.append("Candidates lacked news/policy context")

    risk_tagged = [item for item in candidates if _as_list(item.get("news_risk_tags"))]
    if risk_tagged:
        signals.append(f"{len(risk_tagged)} candidates included explicit news risk tags")
        score += 10
    return _card("News Catalyst Analyst", score, signals, gaps, actions)


def _risk_scorecard(
    payload: Dict[str, Any],
    candidates: Sequence[Dict[str, Any]],
    orders: Sequence[Dict[str, Any]],
    diagnostics: Sequence[Dict[str, Any]],
) -> AgentScorecard:
    score = 50
    signals: List[str] = []
    gaps: List[str] = []
    actions: List[str] = []
    blocked = [order for order in orders if order.get("blocked_reason")]
    submitted = [order for order in orders if order.get("submitted")]
    if blocked:
        signals.append(f"{len(blocked)} orders blocked by guardrails")
        score += 15
    if diagnostics:
        signals.append(f"{len(diagnostics)} order planning diagnostics recorded")
        score += 10
    if payload.get("submit_requested") and not payload.get("ceo_approved") and not submitted:
        signals.append("Submission request stayed blocked without CEO approval")
        score += 15
    if bool(_as_dict(payload.get("clock")).get("is_open")) is False and blocked:
        signals.append("Market-closed orders were blocked")
        score += 10
    if submitted and not payload.get("ceo_approved") and payload.get("ceo_approval_required", True):
        gaps.append("Orders submitted without explicit CEO approval")
        score -= 30
    risk_flags = sum(len(_as_list(item.get("risk_flags"))) for item in candidates)
    if risk_flags:
        signals.append(f"{risk_flags} candidate risk flags surfaced")
    if not blocked and not diagnostics and orders:
        gaps.append("Orders had little visible risk rationale")
        actions.append("Require a reason-not-to-trade field for every proposed order")
    return _card("Risk Officer", score, signals, gaps, actions)


def _portfolio_scorecard(
    payload: Dict[str, Any],
    candidates: Sequence[Dict[str, Any]],
    orders: Sequence[Dict[str, Any]],
    diagnostics: Sequence[Dict[str, Any]],
) -> AgentScorecard:
    score = 45
    signals: List[str] = []
    gaps: List[str] = []
    actions: List[str] = []
    weights = _as_dict(payload.get("target_weights"))
    if weights:
        signals.append(f"{len(weights)} target weights produced")
        score += 20
        max_weight = max(_safe_float(value) for value in weights.values())
        if max_weight <= 0.25:
            signals.append("Target weights stayed diversified")
            score += 10
        else:
            gaps.append("Largest target weight exceeded 25%")
            actions.append("Check portfolio concentration cap before next open")
    else:
        gaps.append("No target weights produced")
        if candidates:
            actions.append("Review candidate filters against target position count")

    if orders:
        signals.append(f"{len(orders)} order plans generated")
        score += 10
    elif weights:
        gaps.append("Targets did not translate into order plans")
        actions.append("Inspect buying power, open orders, and minimum notional diagnostics")
    if diagnostics and not orders:
        signals.append("No-order state explained by diagnostics")
        score += 5
    return _card("Portfolio Manager", score, signals, gaps, actions)


def _ceo_scorecard(payload: Dict[str, Any], orders: Sequence[Dict[str, Any]]) -> AgentScorecard:
    score = 50
    signals: List[str] = []
    gaps: List[str] = []
    actions: List[str] = []
    account = _as_dict(payload.get("account"))
    if str(account.get("status", "")).upper() == "ACTIVE":
        signals.append("Paper account active")
        score += 10
    else:
        gaps.append("Paper account was not active")
    if payload.get("paper_account_only", True):
        signals.append("Paper-account-only mode confirmed")
        score += 15
    submitted = [order for order in orders if order.get("submitted")]
    blocked = [order for order in orders if order.get("blocked_reason")]
    if payload.get("submit_requested"):
        if submitted:
            signals.append(f"{len(submitted)} submitted paper orders recorded")
            score += 10
        elif blocked:
            signals.append("Submission request resulted in blocked orders only")
            score += 10
        else:
            gaps.append("Submission requested but no order outcome was recorded")
    if not payload.get("ceo_approved") and submitted:
        gaps.append("Submitted orders without CEO approval flag")
        score -= 25
    if not orders:
        actions.append("Review whether no-trade was intentional after the briefing")
    return _card("CEO Agent", score, signals, gaps, actions)


def _local_ai_staff_scorecard(payload: Dict[str, Any]) -> AgentScorecard:
    score = 50
    signals: List[str] = []
    gaps: List[str] = []
    actions: List[str] = []
    policy = _as_dict(payload.get("compute_policy_report"))
    if policy:
        provider = str(policy.get("provider", "unknown"))
        signals.append(f"Compute policy provider: {provider}")
        if not policy.get("online_llm_allowed", False):
            signals.append("Hosted LLM usage blocked")
            score += 20
    else:
        gaps.append("Compute policy report missing from artifact")
        actions.append("Keep compute policy report in each run artifact")

    memo = str(payload.get("staff_memo") or "").strip()
    if memo and "unavailable" not in memo.lower() and "skipped" not in memo.lower():
        signals.append("Local staff memo produced")
        score += 15
    elif memo:
        gaps.append(memo[:120])
        actions.append("Keep staff memo optional while local model quality improves")
    else:
        gaps.append("No local staff memo captured")
    return _card("Local AI Staff", score, signals, gaps, actions)


def _aggregate_scorecards(scorecards: Sequence[AgentScorecard]) -> List[AgentScorecard]:
    grouped: Dict[str, List[AgentScorecard]] = {}
    for card in scorecards:
        grouped.setdefault(card.agent, []).append(card)
    aggregate: List[AgentScorecard] = []
    for agent in sorted(grouped):
        cards = grouped[agent]
        score = round(sum(card.score for card in cards) / len(cards))
        aggregate.append(
            _card(
                agent,
                score,
                _unique(item for card in cards for item in card.signals),
                _unique(item for card in cards for item in card.gaps),
                _unique(item for card in cards for item in card.next_actions),
            )
        )
    return aggregate


def _lessons_by_agent(scorecards: Sequence[AgentScorecard]) -> Dict[str, List[str]]:
    lessons: Dict[str, List[str]] = {}
    for card in scorecards:
        items: List[str] = []
        if card.score >= 80:
            items.append(f"Preserve current {card.agent} workflow; it produced a {card.grade} operational score.")
        elif card.score >= 65:
            items.append(f"Keep {card.agent} active, but tighten the weakest checklist item before the next run.")
        else:
            items.append(f"Treat {card.agent} as a priority improvement area before scaling autonomy.")
        for gap in card.gaps[:3]:
            items.append(f"Gap observed: {gap}")
        for action in card.next_actions[:3]:
            items.append(f"Next action: {action}")
        lessons[card.agent] = items
    return lessons


def _summarize_orders(orders: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    blocked: Dict[str, int] = {}
    for order in orders:
        reason = str(order.get("blocked_reason") or "").strip()
        if reason:
            blocked[reason] = blocked.get(reason, 0) + 1
    return {
        "count": len(orders),
        "submitted": sum(1 for order in orders if order.get("submitted")),
        "blocked": sum(1 for order in orders if order.get("blocked_reason")),
        "blocked_reasons": blocked,
    }


def _summarize_candidates(candidates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    backtests = [item for item in candidates if "backtest_passed" in item]
    pass_rate = "n/a"
    if backtests:
        passed = sum(1 for item in backtests if item.get("backtest_passed"))
        pass_rate = f"{passed}/{len(backtests)}"
    return {
        "count": len(candidates),
        "auto_trade_allowed": sum(1 for item in candidates if item.get("auto_trade_allowed")),
        "backtest_pass_rate": pass_rate,
        "risk_flags": sum(len(_as_list(item.get("risk_flags"))) for item in candidates),
    }


def _review_to_dict(review: PostMarketReview) -> Dict[str, Any]:
    return {
        "trade_date": review.trade_date,
        "run_count": review.run_count,
        "average_score": review.average_score,
        "scorecards": [asdict(card) for card in review.scorecards],
        "lessons_by_agent": review.lessons_by_agent,
        "artifact_paths": review.artifact_paths,
        "order_summary": review.order_summary,
        "candidate_summary": review.candidate_summary,
    }


def _scorecard_from_dict(item: Dict[str, Any]) -> AgentScorecard:
    return AgentScorecard(
        agent=str(item.get("agent", "Unknown Agent")),
        score=int(item.get("score", 0)),
        grade=str(item.get("grade", "F")),
        signals=[str(value) for value in _as_list(item.get("signals"))],
        gaps=[str(value) for value in _as_list(item.get("gaps"))],
        next_actions=[str(value) for value in _as_list(item.get("next_actions"))],
    )


def _card(
    agent: str,
    score: int | float,
    signals: Iterable[str],
    gaps: Iterable[str],
    actions: Iterable[str],
) -> AgentScorecard:
    bounded = max(0, min(100, int(round(score))))
    return AgentScorecard(
        agent=agent,
        score=bounded,
        grade=_grade(bounded),
        signals=_unique(signals),
        gaps=_unique(gaps),
        next_actions=_unique(actions),
    )


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _unique(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        cleaned = _one_line(item)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _one_line(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return cleaned or "agent"


def _md(value: Any, max_len: int = 120) -> str:
    text = _one_line(value)
    text = text.replace("|", "/")
    if len(text) > max_len:
        return text[: max_len - 3].rstrip() + "..."
    return text
