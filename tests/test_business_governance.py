from tradingagents.company.business_governance import (
    business_lines_by_name,
    executable_business_lines,
    render_business_line_model_markdown,
    research_only_business_lines,
    total_executable_allocation_pct,
    validate_business_line_model,
)


def test_default_business_line_model_is_valid():
    assert validate_business_line_model() == []
    assert total_executable_allocation_pct() <= 100.0


def test_forex_and_crypto_are_not_accidentally_executable():
    by_name = business_lines_by_name()

    assert by_name["Forex Research Desk"].can_submit_orders is False
    assert by_name["Forex Research Desk"].max_capital_allocation_pct == 0.0
    assert by_name["Crypto Desk"].can_submit_orders is False


def test_executable_lines_stay_under_central_execution_controller():
    executable = executable_business_lines()

    assert executable
    assert all(
        line.execution_authority == "alpaca_paper_execution_controller"
        for line in executable
    )


def test_research_only_lines_include_governance_and_news_reversion():
    names = {line.name for line in research_only_business_lines()}

    assert "Data Quality And Strategy Governance" in names
    assert "News Catalyst And Reversion Desk" in names


def test_business_line_model_markdown_renders_key_desks():
    markdown = render_business_line_model_markdown()

    assert "Equities Momentum Desk" in markdown
    assert "Crypto Desk" in markdown
    assert "Forex Research Desk" in markdown
    assert "Promotion Gate" in markdown
