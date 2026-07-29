import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
import pytest

from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.research_department.strategy_researcher import (
    create_strategy_researcher,
)
from tradingagents.agents.utils import strategy_grounding


def _write_library(root):
    root.mkdir(parents=True)
    approved = [
        {
            "strategy_id": "opening_range_breakout_15m",
            "desk": "Equities Momentum Desk",
            "asset_class": "us_equity",
            "hypothesis": "A volume-confirmed opening-range break may continue.",
            "entry_rules": ["Break opening-range high", "Confirm above VWAP"],
            "risk_rules": ["Fresh quote", "Narrow spread"],
            "required_data": ["5m bars", "latest quote", "volume"],
            "promotion_status": "approved_paper_strategy",
            "decision": "paper_trade_allowed",
            "metrics": {"trades": 371, "profit_factor": 1.46},
        },
        {
            "strategy_id": "momentum_breakout",
            "desk": "Equities Momentum Desk",
            "hypothesis": "Relative volume may support continuation.",
            "entry_rules": ["Break recent high"],
            "risk_rules": ["Cap correlated exposure"],
            "required_data": ["relative volume"],
            "promotion_status": "approved_paper_strategy",
            "decision": "paper_trade_allowed",
            "metrics": {"trades": 358, "profit_factor": 1.69},
        },
    ]
    ideas = [
        {
            "strategy_id": "relative_strength_continuation",
            "desk": "Equities Momentum Desk",
            "hypothesis": "Multi-day strength may continue without exhaustion.",
            "entry_rules": ["5D and 20D strength"],
            "risk_rules": ["Avoid sector stacking"],
            "required_data": ["daily bars", "intraday confirmation"],
            "promotion_status": "paper_trade_candidate",
            "decision": "paper_trade_allowed",
            "metrics": {"trades": 370, "profit_factor": 1.12},
        }
    ]
    retired = [
        {
            "strategy_id": "vwap_reclaim",
            "desk": "Equities Momentum Desk",
            "hypothesis": "A VWAP reclaim may signal returning buyers.",
            "entry_rules": ["Reclaim VWAP"],
            "risk_rules": ["Research-only"],
            "required_data": ["intraday bars", "VWAP"],
            "promotion_status": "retired",
            "decision": "blocked",
            "metrics": {"trades": 339, "profit_factor": 0.97},
        }
    ]
    for filename, payload in (
        ("approved_paper_strategies.json", approved),
        ("research_ideas.json", ideas),
        ("retired_strategies.json", retired),
    ):
        (root / filename).write_text(json.dumps(payload), encoding="utf-8")


class _CapturingToolLLM:
    def __init__(self, captured, content):
        self.captured = captured
        self.content = content

    def bind_tools(self, _tools):
        def invoke(prompt):
            self.captured["prompt"] = prompt.to_string()
            return AIMessage(content=self.content)

        return RunnableLambda(invoke)


def _state():
    return {
        "company_of_interest": "NVDA",
        "trade_date": "2026-07-29",
        "messages": [HumanMessage(content="Analyze NVDA")],
        "stock_discovery_report": "NVDA has high relative volume.",
        "market_report": "Price is above VWAP.",
        "sentiment_report": "",
        "news_report": "",
        "current_news_report": "",
        "fundamentals_report": "",
        "training_context": "",
    }


@pytest.mark.unit
def test_strategy_library_context_ranks_promoted_rows_and_is_bounded(
    tmp_path,
    monkeypatch,
):
    library = tmp_path / "strategy_library"
    _write_library(library)
    monkeypatch.setattr(
        strategy_grounding,
        "get_config",
        lambda: {"strategy_library_dir": str(library)},
    )

    context = strategy_grounding.get_strategy_library_context(
        _state(),
        role="strategy_researcher",
        max_entries=3,
        max_chars=1800,
    )

    assert "strategy_id=opening_range_breakout_15m" in context
    assert "strategy_id=momentum_breakout" in context
    assert "strategy_id=relative_strength_continuation" in context
    assert "strategy_id=vwap_reclaim" not in context
    assert "promotion status" in context
    assert len(context) <= 1800


@pytest.mark.unit
def test_strategy_library_context_tolerates_missing_or_invalid_files(
    tmp_path,
    monkeypatch,
):
    library = tmp_path / "strategy_library"
    library.mkdir()
    (library / "approved_paper_strategies.json").write_text(
        "{invalid",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        strategy_grounding,
        "get_config",
        lambda: {"strategy_library_dir": str(library)},
    )

    assert strategy_grounding.get_strategy_library_context(_state()) == ""


@pytest.mark.unit
def test_strategy_researcher_prompt_cites_grounded_strategy(
    tmp_path,
    monkeypatch,
):
    library = tmp_path / "strategy_library"
    _write_library(library)
    monkeypatch.setattr(
        strategy_grounding,
        "get_config",
        lambda: {"strategy_library_dir": str(library)},
    )
    captured = {}
    llm = _CapturingToolLLM(
        captured,
        "Use strategy_id=opening_range_breakout_15m as a paper-test setup.",
    )

    result = create_strategy_researcher(llm)(_state())

    assert "strategy_id=opening_range_breakout_15m" in captured["prompt"]
    assert "preserve its promotion status" in captured["prompt"]
    assert "strategy_id=opening_range_breakout_15m" in result["strategy_report"]


@pytest.mark.unit
def test_market_analyst_prompt_receives_strategy_library_grounding(
    tmp_path,
    monkeypatch,
):
    library = tmp_path / "strategy_library"
    _write_library(library)
    monkeypatch.setattr(
        strategy_grounding,
        "get_config",
        lambda: {"strategy_library_dir": str(library)},
    )
    captured = {}
    llm = _CapturingToolLLM(captured, "Market setup report")

    result = create_market_analyst(llm)(_state())

    assert "strategy_id=opening_range_breakout_15m" in captured["prompt"]
    assert "local research evidence" in captured["prompt"]
    assert result["market_report"] == "Market setup report"
