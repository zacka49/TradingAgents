from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


AVAILABLE_AGENT_SKILLS: tuple[str, ...] = (
    "agent-training-orchestration",
    "copy-flow-research",
    "crypto-desk-research",
    "data-quality-strategy-governance",
    "day-trading-research",
    "equities-momentum-desk",
    "financial-ai-technology-scout",
    "forex-macro-research",
    "multi-desk-portfolio-risk",
    "news-catalyst-reversion",
    "quant-strategy-research",
)


@dataclass(frozen=True)
class AgentSkillAssignment:
    agent: str
    department: str
    primary_skill: str
    supporting_skills: tuple[str, ...]
    training_drill: str
    success_metric: str
    authority: str = "research_or_review"

    @property
    def all_skills(self) -> tuple[str, ...]:
        return (self.primary_skill, *self.supporting_skills)


DEFAULT_AGENT_SKILL_ASSIGNMENTS: tuple[AgentSkillAssignment, ...] = (
    AgentSkillAssignment(
        "Codex CEO Company Runner",
        "Executive Control",
        "multi-desk-portfolio-risk",
        ("data-quality-strategy-governance", "day-trading-research"),
        "Produce a desk-by-desk decision pack with allocation caps, blockers, and one approved next action.",
        "Every proposed order has a desk, strategy, risk cap, and blocker status.",
        "central_orchestration",
    ),
    AgentSkillAssignment(
        "Autonomous Paper CEO Agent",
        "Executive Control",
        "multi-desk-portfolio-risk",
        ("equities-momentum-desk", "data-quality-strategy-governance"),
        "Run one paper cycle and explain every accepted, blocked, flattened, or cooled-down symbol.",
        "No order is submitted outside market, allocation, duplicate, or drawdown gates.",
        "paper_execution_orchestration",
    ),
    AgentSkillAssignment(
        "CEO Agent",
        "Executive Control",
        "data-quality-strategy-governance",
        ("multi-desk-portfolio-risk", "agent-training-orchestration"),
        "Approve or reject a briefing pack using promotion-stage language.",
        "Decision uses approve, reject, watch, paper-test-only, or risk-review.",
        "executive_review",
    ),
    AgentSkillAssignment(
        "Local AI Staff",
        "Executive Control",
        "agent-training-orchestration",
        ("day-trading-research", "multi-desk-portfolio-risk"),
        "Summarize the run in five bullets focused on evidence, not confidence.",
        "Memo flags at least one data gap, risk gap, or promotion blocker when present.",
    ),
    AgentSkillAssignment(
        "Opportunity Scout",
        "Discovery And Research Intake",
        "equities-momentum-desk",
        ("day-trading-research", "multi-desk-portfolio-risk"),
        "Rank a liquid universe and tag each symbol by desk and setup type.",
        "Top candidates include liquidity, relative volume, volatility, and desk tag.",
    ),
    AgentSkillAssignment(
        "Stock Discovery Researcher",
        "Discovery And Research Intake",
        "day-trading-research",
        ("equities-momentum-desk", "news-catalyst-reversion"),
        "Build a 10-symbol research list with catalyst, risk owner, and invalidation.",
        "Every selected symbol has a reason it is actionable now or marked watch-only.",
    ),
    AgentSkillAssignment(
        "Technology Scout",
        "Discovery And Research Intake",
        "financial-ai-technology-scout",
        ("data-quality-strategy-governance",),
        "Convert one outside repo/tool idea into a concrete workflow upgrade or reject it.",
        "Recommendation includes license caution, integration cost, and next implementation step.",
    ),
    AgentSkillAssignment(
        "Backtest Lab",
        "Evidence And Governance",
        "quant-strategy-research",
        ("day-trading-research", "news-catalyst-reversion"),
        "Audit a strategy result for sample size, leakage, event dedupe, and slippage assumptions.",
        "Backtest verdict includes pass, weak, insufficient sample, or research-only.",
    ),
    AgentSkillAssignment(
        "News Reversion Desk",
        "Discovery And Research Intake",
        "news-catalyst-reversion",
        ("data-quality-strategy-governance",),
        "Run an event study with price before news, price after news, and one-day-after price.",
        "Report dedupes same-session headlines and states whether reversion is viable.",
    ),
    AgentSkillAssignment(
        "Data Quality Officer",
        "Data Quality And Strategy Governance",
        "data-quality-strategy-governance",
        ("agent-training-orchestration",),
        "Review a run for stale data, missing bars, weak samples, and unsupported asset routing.",
        "All data gaps are converted into promote, demote, block, or retest actions.",
    ),
    AgentSkillAssignment(
        "Experiment / Backtest Auditor",
        "Data Quality And Strategy Governance",
        "quant-strategy-research",
        ("day-trading-research", "news-catalyst-reversion"),
        "Challenge one backtest and identify the weakest assumption.",
        "No strategy is promoted without sample size and out-of-sample notes.",
    ),
    AgentSkillAssignment(
        "Strategy Promotion Committee",
        "Data Quality And Strategy Governance",
        "data-quality-strategy-governance",
        ("multi-desk-portfolio-risk",),
        "Move strategies through research idea, paper watchlist, paper candidate, or approved paper strategy.",
        "Every promoted strategy has a desk cap, stop rule, and measurable success condition.",
        "promotion_gate",
    ),
    AgentSkillAssignment(
        "P&L Attribution Analyst",
        "Data Quality And Strategy Governance",
        "data-quality-strategy-governance",
        ("multi-desk-portfolio-risk",),
        "Attribute daily P&L by desk, strategy, symbol, and blocker reason.",
        "Post-market review shows which desk helped or hurt performance.",
    ),
    AgentSkillAssignment(
        "Equities Momentum Desk",
        "Specialist Trading Desks",
        "equities-momentum-desk",
        ("day-trading-research", "multi-desk-portfolio-risk"),
        "Promote only momentum setups with fresh quotes, spread checks, and bracket exits.",
        "No watch-only setup is treated as an autonomous paper entry.",
    ),
    AgentSkillAssignment(
        "Crypto Desk",
        "Specialist Trading Desks",
        "crypto-desk-research",
        ("multi-desk-portfolio-risk", "data-quality-strategy-governance"),
        "Separate crypto spot/proxy ideas and list missing adapter/risk requirements.",
        "Crypto ideas remain research-only until adapter, fee, and 24/7 risk gates pass.",
    ),
    AgentSkillAssignment(
        "Forex Research Desk",
        "Specialist Trading Desks",
        "forex-macro-research",
        ("multi-desk-portfolio-risk",),
        "Convert one FX theme into ETF/equity context without suggesting direct FX execution.",
        "Every output says context-only, macro ETF watch, or risk-review.",
    ),
    AgentSkillAssignment(
        "Macro ETF Desk",
        "Specialist Trading Desks",
        "forex-macro-research",
        ("multi-desk-portfolio-risk", "equities-momentum-desk"),
        "Translate a rates/inflation/dollar catalyst into an ETF watch or hedge note.",
        "ETF idea includes correlation impact on existing equity exposure.",
    ),
    AgentSkillAssignment(
        "Market Analyst",
        "Core Analyst Team",
        "equities-momentum-desk",
        ("day-trading-research", "multi-desk-portfolio-risk"),
        "Explain price, volume, volatility, VWAP, and regime before any directional claim.",
        "Report includes setup classification and invalidation.",
    ),
    AgentSkillAssignment(
        "Social Media Analyst",
        "Core Analyst Team",
        "news-catalyst-reversion",
        ("data-quality-strategy-governance",),
        "Extract social sentiment as untrusted catalyst evidence with source risk.",
        "No social claim becomes a trade trigger without price and liquidity confirmation.",
    ),
    AgentSkillAssignment(
        "News Analyst",
        "Core Analyst Team",
        "news-catalyst-reversion",
        ("forex-macro-research", "data-quality-strategy-governance"),
        "Classify headlines by catalyst tag, direction, risk tag, and action.",
        "Risk headlines are marked risk-review instead of auto-trade.",
    ),
    AgentSkillAssignment(
        "Fundamentals Analyst",
        "Core Analyst Team",
        "data-quality-strategy-governance",
        ("day-trading-research",),
        "Separate long-term fundamentals from intraday tradeability.",
        "Report states whether fundamentals support, conflict with, or do not matter for the day setup.",
    ),
    AgentSkillAssignment(
        "Current News Scout",
        "Research Department",
        "news-catalyst-reversion",
        ("forex-macro-research", "crypto-desk-research"),
        "Build a dated catalyst queue with direct headlines and theme-linked tickers.",
        "Queue has action, direction, confidence, tags, and verification needs.",
    ),
    AgentSkillAssignment(
        "Strategy Researcher",
        "Research Department",
        "quant-strategy-research",
        ("data-quality-strategy-governance", "equities-momentum-desk"),
        "Turn one candidate into setup, trigger, confirmation, invalidation, sizing, and paper-test note.",
        "Strategy memo is testable and names the data needed for promotion.",
    ),
    AgentSkillAssignment(
        "Copy Trading Researcher",
        "Research Department",
        "copy-flow-research",
        ("data-quality-strategy-governance",),
        "Review a public disclosure for lag, price move since transaction, and risk.",
        "Output is context-only, watch, confirm-with-price, or risk-review.",
    ),
    AgentSkillAssignment(
        "GitHub Researcher",
        "Research Department",
        "financial-ai-technology-scout",
        ("data-quality-strategy-governance",),
        "Assess one repo/tool for practical adoption in the trading workflow.",
        "Memo includes adoption status, license caution, and implementation next step.",
    ),
    AgentSkillAssignment(
        "Research Director",
        "Research Department",
        "data-quality-strategy-governance",
        ("day-trading-research", "multi-desk-portfolio-risk"),
        "Synthesize research into conflicts, highest-value signals, and debate questions.",
        "Brief separates evidence, uncertainty, and decision questions.",
    ),
    AgentSkillAssignment(
        "Bull Researcher",
        "Bull / Bear Debate",
        "day-trading-research",
        ("equities-momentum-desk", "news-catalyst-reversion"),
        "Build the best evidence-backed bullish case and state what would disprove it.",
        "Bull case includes trigger, confirmation, and invalidation.",
    ),
    AgentSkillAssignment(
        "Bear Researcher",
        "Bull / Bear Debate",
        "data-quality-strategy-governance",
        ("multi-desk-portfolio-risk", "news-catalyst-reversion"),
        "Challenge liquidity, catalyst, valuation, correlation, and backtest quality.",
        "Bear case identifies at least one concrete blocker or missing evidence item.",
    ),
    AgentSkillAssignment(
        "Research Manager",
        "Bull / Bear Debate",
        "data-quality-strategy-governance",
        ("multi-desk-portfolio-risk",),
        "Resolve bull/bear conflict into approve, reject, watch, or risk-review.",
        "Decision cites the decisive evidence and the rejected alternative.",
    ),
    AgentSkillAssignment(
        "Chief Investment Officer",
        "Investment And Trading Department",
        "multi-desk-portfolio-risk",
        ("data-quality-strategy-governance",),
        "Convert research into a capital-aware investment stance across desks.",
        "Memo states capital cap, desk cap, and portfolio conflict.",
    ),
    AgentSkillAssignment(
        "Trader",
        "Investment And Trading Department",
        "equities-momentum-desk",
        ("multi-desk-portfolio-risk", "day-trading-research"),
        "Turn approved stance into an execution idea with entry, stop, target, and no-trade condition.",
        "Plan has named setup, timing, invalidation, and expected holding period.",
    ),
    AgentSkillAssignment(
        "Trading Desk Strategist",
        "Investment And Trading Department",
        "equities-momentum-desk",
        ("multi-desk-portfolio-risk",),
        "Check order type, timing, liquidity, slippage, and stand-down conditions.",
        "Desk plan can be executed or blocked by deterministic risk code.",
    ),
    AgentSkillAssignment(
        "Risk Office Guardian",
        "Risk Department",
        "multi-desk-portfolio-risk",
        ("data-quality-strategy-governance",),
        "Audit the proposed trade for max loss, correlation, stale data, and execution readiness.",
        "Risk memo blocks unsupported, oversized, stale, or correlated entries.",
    ),
    AgentSkillAssignment(
        "Aggressive Analyst",
        "Risk Department",
        "day-trading-research",
        ("equities-momentum-desk",),
        "Find the best risk-taking version of the trade without removing stops.",
        "Aggressive view improves opportunity while preserving order caps.",
    ),
    AgentSkillAssignment(
        "Conservative Analyst",
        "Risk Department",
        "multi-desk-portfolio-risk",
        ("data-quality-strategy-governance",),
        "Find the smallest viable size or explain why the trade should be blocked.",
        "Conservative view reduces exposure or tightens invalidation when evidence is weak.",
    ),
    AgentSkillAssignment(
        "Neutral Analyst",
        "Risk Department",
        "data-quality-strategy-governance",
        ("multi-desk-portfolio-risk",),
        "Balance upside and downside into a final risk-adjusted stance.",
        "Neutral view states whether risk/reward justifies paper exposure.",
    ),
    AgentSkillAssignment(
        "Portfolio Manager",
        "Risk Department",
        "multi-desk-portfolio-risk",
        ("data-quality-strategy-governance",),
        "Approve final allocation only after desk caps, exposure, and blocker checks.",
        "Final decision has position cap, capital cap, and rejection reason if blocked.",
        "portfolio_decision",
    ),
    AgentSkillAssignment(
        "Portfolio Office Allocator",
        "Portfolio And Operations",
        "multi-desk-portfolio-risk",
        ("data-quality-strategy-governance",),
        "Allocate across desks and reserve cash when setups are weak.",
        "Allocation table sums within caps and flags correlated exposure.",
    ),
    AgentSkillAssignment(
        "Operations Compliance Auditor",
        "Portfolio And Operations",
        "data-quality-strategy-governance",
        ("multi-desk-portfolio-risk",),
        "Audit whether the proposed action obeys paper-only, market, order, and data rules.",
        "Audit records every compliance blocker and required artifact.",
    ),
    AgentSkillAssignment(
        "Alpaca Paper Execution Controller",
        "Portfolio And Operations",
        "multi-desk-portfolio-risk",
        ("equities-momentum-desk", "data-quality-strategy-governance"),
        "Submit only orders that pass market-open, notional, bracket, and duplicate-order gates.",
        "Every accepted or rejected order has a recorded reason and broker response.",
        "deterministic_order_submission",
    ),
    AgentSkillAssignment(
        "Evaluation Analyst",
        "Review Learning And Training",
        "agent-training-orchestration",
        ("data-quality-strategy-governance",),
        "Score each agent by evidence quality, handoff quality, and outcome relevance.",
        "Evaluation produces measurable next actions, not generic praise.",
    ),
    AgentSkillAssignment(
        "Training Development Coach",
        "Review Learning And Training",
        "agent-training-orchestration",
        ("data-quality-strategy-governance", "multi-desk-portfolio-risk"),
        "Assign each role one drill and one success metric for the next run.",
        "Training memo covers every active role and maps it to a skill.",
    ),
)


def agent_skill_assignments_by_agent(
    assignments: Sequence[AgentSkillAssignment] = DEFAULT_AGENT_SKILL_ASSIGNMENTS,
) -> dict[str, AgentSkillAssignment]:
    return {assignment.agent: assignment for assignment in assignments}


def assignments_for_department(
    department: str,
    assignments: Sequence[AgentSkillAssignment] = DEFAULT_AGENT_SKILL_ASSIGNMENTS,
) -> list[AgentSkillAssignment]:
    normalized = department.strip().lower()
    return [
        assignment
        for assignment in assignments
        if assignment.department.strip().lower() == normalized
    ]


def missing_skill_folders(
    *,
    project_root: str | Path,
    skills: Sequence[str] = AVAILABLE_AGENT_SKILLS,
) -> list[str]:
    root = Path(project_root)
    return [
        skill
        for skill in skills
        if not (root / ".agents" / "skills" / skill / "SKILL.md").is_file()
    ]


def validate_agent_skill_assignments(
    assignments: Sequence[AgentSkillAssignment] = DEFAULT_AGENT_SKILL_ASSIGNMENTS,
    *,
    available_skills: Sequence[str] = AVAILABLE_AGENT_SKILLS,
) -> list[str]:
    errors: list[str] = []
    available = set(available_skills)
    agents = [assignment.agent for assignment in assignments]
    if len(set(agents)) != len(agents):
        errors.append("agent names must be unique")
    for assignment in assignments:
        if assignment.primary_skill not in available:
            errors.append(f"{assignment.agent}: unknown primary skill {assignment.primary_skill}")
        for skill in assignment.supporting_skills:
            if skill not in available:
                errors.append(f"{assignment.agent}: unknown supporting skill {skill}")
        if not assignment.training_drill:
            errors.append(f"{assignment.agent}: missing training drill")
        if not assignment.success_metric:
            errors.append(f"{assignment.agent}: missing success metric")
    return errors


def render_agent_skill_matrix_markdown(
    assignments: Sequence[AgentSkillAssignment] = DEFAULT_AGENT_SKILL_ASSIGNMENTS,
) -> str:
    errors = validate_agent_skill_assignments(assignments)
    lines = [
        "# AI Agent Skill Matrix",
        "",
        f"- Agents covered: {len(assignments)}",
        f"- Assignment status: {'valid' if not errors else 'needs review'}",
    ]
    if errors:
        lines.extend(f"- Issue: {error}" for error in errors)
    lines.extend(
        [
            "",
            "## Skill Assignments",
            "| Agent | Department | Primary Skill | Supporting Skills | Authority | Drill | Success Metric |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for assignment in assignments:
        lines.append(
            "| {agent} | {department} | {primary} | {supporting} | {authority} | {drill} | {metric} |".format(
                agent=_md_cell(assignment.agent),
                department=_md_cell(assignment.department),
                primary=_md_cell(assignment.primary_skill),
                supporting=_md_cell(", ".join(assignment.supporting_skills) or "none"),
                authority=_md_cell(assignment.authority),
                drill=_md_cell(assignment.training_drill, max_len=180),
                metric=_md_cell(assignment.success_metric, max_len=180),
            )
        )
    lines.extend(
        [
            "",
            "## Training Rule",
            "Each agent should apply its primary skill first. Supporting skills are loaded only when the task crosses desks, requires promotion evidence, or touches execution/risk authority.",
            "",
            "## Weekly Review",
            "- Demote skills that produce noisy or duplicated analysis.",
            "- Promote skills only when scorecards and P&L attribution show improved decisions.",
            "- Keep research-only desks out of order submission until governance promotes them.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_compact_agent_skill_context(
    assignments: Sequence[AgentSkillAssignment] = DEFAULT_AGENT_SKILL_ASSIGNMENTS,
) -> str:
    lines = [
        "Current AI Agent Skill Assignments:",
        "| Agent | Primary Skill | Supporting Skills | Drill | Success Metric |",
        "| --- | --- | --- | --- | --- |",
    ]
    for assignment in assignments:
        lines.append(
            "| {agent} | {primary} | {supporting} | {drill} | {metric} |".format(
                agent=_md_cell(assignment.agent),
                primary=_md_cell(assignment.primary_skill),
                supporting=_md_cell(", ".join(assignment.supporting_skills) or "none"),
                drill=_md_cell(assignment.training_drill, max_len=120),
                metric=_md_cell(assignment.success_metric, max_len=120),
            )
        )
    return "\n".join(lines)


def _md_cell(value: object, *, max_len: int = 120) -> str:
    text = str(value or "").replace("|", "/").replace("\n", " ").strip()
    if len(text) > max_len:
        return f"{text[: max_len - 3]}..."
    return text
