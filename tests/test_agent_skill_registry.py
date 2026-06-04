from pathlib import Path

from tradingagents.company.agent_skill_registry import (
    AVAILABLE_AGENT_SKILLS,
    DEFAULT_AGENT_SKILL_ASSIGNMENTS,
    agent_skill_assignments_by_agent,
    missing_skill_folders,
    render_agent_skill_matrix_markdown,
    render_compact_agent_skill_context,
    validate_agent_skill_assignments,
)


EXPECTED_AGENTS = {
    "Codex CEO Company Runner",
    "Autonomous Paper CEO Agent",
    "CEO Agent",
    "Local AI Staff",
    "Opportunity Scout",
    "Stock Discovery Researcher",
    "Technology Scout",
    "Backtest Lab",
    "News Reversion Desk",
    "Data Quality Officer",
    "Experiment / Backtest Auditor",
    "Strategy Promotion Committee",
    "P&L Attribution Analyst",
    "Equities Momentum Desk",
    "Crypto Desk",
    "Forex Research Desk",
    "Macro ETF Desk",
    "Market Analyst",
    "Social Media Analyst",
    "News Analyst",
    "Fundamentals Analyst",
    "Current News Scout",
    "Strategy Researcher",
    "Copy Trading Researcher",
    "GitHub Researcher",
    "Research Director",
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
    "Chief Investment Officer",
    "Trader",
    "Trading Desk Strategist",
    "Risk Office Guardian",
    "Aggressive Analyst",
    "Conservative Analyst",
    "Neutral Analyst",
    "Portfolio Manager",
    "Portfolio Office Allocator",
    "Operations Compliance Auditor",
    "Alpaca Paper Execution Controller",
    "Evaluation Analyst",
    "Training Development Coach",
}


def test_agent_skill_registry_covers_every_expected_agent():
    by_agent = agent_skill_assignments_by_agent()

    assert EXPECTED_AGENTS <= set(by_agent)
    assert len(DEFAULT_AGENT_SKILL_ASSIGNMENTS) == len(by_agent)
    assert validate_agent_skill_assignments() == []


def test_all_referenced_skill_folders_exist():
    project_root = Path(__file__).resolve().parents[1]

    assert missing_skill_folders(project_root=project_root) == []
    assert "day-trading-research" in AVAILABLE_AGENT_SKILLS
    assert "data-quality-strategy-governance" in AVAILABLE_AGENT_SKILLS


def test_critical_roles_have_correct_primary_skills():
    by_agent = agent_skill_assignments_by_agent()

    assert by_agent["Crypto Desk"].primary_skill == "crypto-desk-research"
    assert by_agent["Forex Research Desk"].primary_skill == "forex-macro-research"
    assert by_agent["News Reversion Desk"].primary_skill == "news-catalyst-reversion"
    assert by_agent["Strategy Promotion Committee"].primary_skill == "data-quality-strategy-governance"
    assert by_agent["Portfolio Office Allocator"].primary_skill == "multi-desk-portfolio-risk"


def test_agent_skill_matrix_markdown_renders_training_table():
    markdown = render_agent_skill_matrix_markdown()

    assert "# AI Agent Skill Matrix" in markdown
    assert "Crypto Desk" in markdown
    assert "Training Development Coach" in markdown
    assert "Weekly Review" in markdown


def test_compact_skill_context_is_prompt_ready():
    context = render_compact_agent_skill_context()

    assert "Current AI Agent Skill Assignments" in context
    assert "Portfolio Office Allocator" in context
    assert "multi-desk-portfolio-risk" in context
