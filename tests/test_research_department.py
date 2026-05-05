from unittest.mock import MagicMock, patch

import pytest

from tradingagents.agents.research_department.research_director import (
    create_research_director,
)
from tradingagents.agents.business_departments.chief_investment_officer import (
    create_chief_investment_officer,
)
from tradingagents.agents.utils.market_scanner_tools import (
    get_discovery_market_snapshot,
)
from tradingagents.agents.utils.github_research_tools import (
    get_popular_financial_ai_repos,
)
from tradingagents.agents.utils.copy_trading_tools import (
    get_congressional_trades,
    get_sec_disclosure_filings,
)
from tradingagents.graph.propagation import Propagator


@pytest.mark.unit
def test_initial_state_includes_research_department_slots():
    state = Propagator().create_initial_state("NVDA", "2026-01-15")

    assert state["stock_discovery_report"] == ""
    assert state["current_news_report"] == ""
    assert state["strategy_report"] == ""
    assert state["copy_trading_report"] == ""
    assert state["github_research_report"] == ""
    assert state["research_department_report"] == ""
    assert state["investment_committee_report"] == ""
    assert state["trading_desk_report"] == ""
    assert state["risk_office_report"] == ""
    assert state["portfolio_office_report"] == ""
    assert state["operations_compliance_report"] == ""
    assert state["evaluation_report"] == ""


@pytest.mark.unit
def test_research_director_synthesizes_specialist_reports():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Director brief")
    director = create_research_director(llm)

    result = director(
        {
            "company_of_interest": "NVDA",
            "stock_discovery_report": "Ten-stock watchlist",
            "current_news_report": "News catalyst",
            "strategy_report": "Breakout strategy",
            "copy_trading_report": "Politician flow",
            "github_research_report": "Backtrader lesson",
            "market_report": "Market",
            "sentiment_report": "Sentiment",
            "news_report": "News",
            "fundamentals_report": "Fundamentals",
        }
    )

    prompt = llm.invoke.call_args.args[0]
    assert "Ten-stock watchlist" in prompt
    assert "News catalyst" in prompt
    assert "Breakout strategy" in prompt
    assert "Politician flow" in prompt
    assert "Backtrader lesson" in prompt
    assert result["research_department_report"] == "Director brief"


@pytest.mark.unit
def test_github_repo_scout_falls_back_to_curated_rows():
    with patch(
        "tradingagents.agents.utils.github_research_tools._github_search",
        side_effect=RuntimeError("offline"),
    ):
        report = get_popular_financial_ai_repos.invoke({"query": "", "limit": 12})

    assert "# GitHub financial AI repository scout" in report
    assert "TauricResearch/TradingAgents" in report
    assert "AI4Finance-Foundation/FinRobot" in report


@pytest.mark.unit
def test_chief_investment_officer_uses_research_plan_and_department_brief():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Committee memo")
    cio = create_chief_investment_officer(llm)

    result = cio(
        {
            "company_of_interest": "NVDA",
            "stock_discovery_report": "Ten-stock watchlist",
            "market_report": "Market",
            "sentiment_report": "Sentiment",
            "news_report": "News",
            "fundamentals_report": "Fundamentals",
            "research_department_report": "Director brief",
            "investment_plan": "Research manager plan",
        }
    )

    prompt = llm.invoke.call_args.args[0]
    assert "Director brief" in prompt
    assert "Research manager plan" in prompt
    assert result["investment_committee_report"] == "Committee memo"


@pytest.mark.unit
def test_discovery_market_snapshot_formats_ranked_rows():
    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, start, end):
            import pandas as pd

            return pd.DataFrame(
                {
                    "Close": [100.0, 105.0, 110.0],
                    "Volume": [1000, 1200, 3000],
                }
            )

    with patch("tradingagents.agents.utils.market_scanner_tools.yf.Ticker", FakeTicker):
        report = get_discovery_market_snapshot.invoke(
            {"tickers": "AAA,BBB", "look_back_days": 10, "limit": 2}
        )

    assert "# Discovery market snapshot" in report
    assert "| 1 | AAA |" in report
    assert "| 2 | BBB |" in report


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
