from unittest.mock import MagicMock, patch

import pytest

from tradingagents.agents.research_department.research_director import (
    create_research_director,
)
from tradingagents.agents.utils.copy_trading_tools import (
    get_congressional_trades,
    get_sec_disclosure_filings,
)
from tradingagents.graph.propagation import Propagator


@pytest.mark.unit
def test_initial_state_includes_research_department_slots():
    state = Propagator().create_initial_state("NVDA", "2026-01-15")

    assert state["current_news_report"] == ""
    assert state["strategy_report"] == ""
    assert state["copy_trading_report"] == ""
    assert state["research_department_report"] == ""


@pytest.mark.unit
def test_research_director_synthesizes_specialist_reports():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Director brief")
    director = create_research_director(llm)

    result = director(
        {
            "company_of_interest": "NVDA",
            "current_news_report": "News catalyst",
            "strategy_report": "Breakout strategy",
            "copy_trading_report": "Politician flow",
            "market_report": "Market",
            "sentiment_report": "Sentiment",
            "news_report": "News",
            "fundamentals_report": "Fundamentals",
        }
    )

    prompt = llm.invoke.call_args.args[0]
    assert "News catalyst" in prompt
    assert "Breakout strategy" in prompt
    assert "Politician flow" in prompt
    assert result["research_department_report"] == "Director brief"


@pytest.mark.unit
def test_congressional_trades_filters_by_ticker_and_formats_rows():
    senate_rows = [
        {
            "ticker": "NVDA",
            "senator": "Jane Example",
            "transaction_date": "01/05/2026",
            "disclosure_date": "01/10/2026",
            "type": "Purchase",
            "amount": "$15,001 - $50,000",
            "asset_description": "NVIDIA Corp",
        },
        {"ticker": "MSFT", "senator": "Other", "transaction_date": "01/05/2026"},
    ]
    house_rows = [
        {
            "ticker": "NVDA",
            "representative": "Pat Example",
            "transaction_date": "01/07/2026",
            "disclosure_date": "01/12/2026",
            "type": "Sale",
            "amount": "$1,001 - $15,000",
            "asset_description": "NVIDIA Corp",
        }
    ]

    with patch(
        "tradingagents.agents.utils.copy_trading_tools._fetch_json",
        side_effect=[senate_rows, house_rows],
    ):
        report = get_congressional_trades.invoke(
            {"ticker": "NVDA", "look_back_days": 5000, "limit": 10}
        )

    assert "Jane Example" in report
    assert "Pat Example" in report
    assert "MSFT" not in report
    assert "Source status: Senate: 1 matching rows; House: 1 matching rows" in report


@pytest.mark.unit
def test_sec_disclosure_tool_requires_declared_user_agent(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)

    report = get_sec_disclosure_filings.invoke({"ticker": "NVDA"})

    assert "SEC_USER_AGENT is not set" in report
