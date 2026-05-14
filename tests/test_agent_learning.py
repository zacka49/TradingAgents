import json
from pathlib import Path

import pytest

from tradingagents.company import (
    SpecialistMemoryLog,
    build_agent_scorecards,
    find_company_run_payloads,
    write_post_market_review,
)


def _payload() -> dict:
    return {
        "trade_date": "2026-05-11",
        "account": {"status": "ACTIVE"},
        "clock": {"is_open": False},
        "paper_account_only": True,
        "submit_requested": True,
        "ceo_approved": False,
        "compute_policy_report": {
            "provider": "ollama",
            "online_llm_allowed": False,
        },
        "staff_memo": "Review QQQ risk and wait for confirmation.",
        "catalyst_context": {
            "ranked_research_queue": [
                {"symbol": "QQQ", "action": "watch", "score": 4.0}
            ]
        },
        "candidates": [
            {
                "ticker": "QQQ",
                "score": 8.0,
                "risk_flags": ["volume_spike"],
                "auto_trade_allowed": True,
                "backtest_passed": True,
                "day_trade_fit_score": 4.5,
                "catalyst_tags": ["index_strength"],
                "news_risk_tags": ["macro"],
            }
        ],
        "target_weights": {"QQQ": 0.2},
        "order_plans": [
            {
                "ticker": "QQQ",
                "side": "buy",
                "submitted": False,
                "blocked_reason": "market_closed",
            }
        ],
        "order_plan_diagnostics": [
            {"ticker": "QQQ", "reason": "market_closed"}
        ],
    }


@pytest.mark.unit
def test_build_agent_scorecards_covers_specialist_roles():
    scorecards = build_agent_scorecards(_payload())

    names = {card.agent for card in scorecards}
    assert "Market Analyst" in names
    assert "News Catalyst Analyst" in names
    assert "Risk Officer" in names
    assert "Portfolio Manager" in names
    assert "CEO Agent" in names
    assert "Local AI Staff" in names
    assert all(0 <= card.score <= 100 for card in scorecards)


@pytest.mark.unit
def test_write_post_market_review_updates_specialist_memory(tmp_path):
    run_dir = tmp_path / "results" / "codex_ceo_company" / "2026-05-11" / "run_1"
    run_dir.mkdir(parents=True)
    (run_dir / "company_run.json").write_text(
        json.dumps(_payload(), indent=2),
        encoding="utf-8",
    )

    summary = write_post_market_review(
        results_dir=tmp_path / "results",
        trade_date="2026-05-11",
        memory_dir=tmp_path / "memory",
    )

    assert summary["run_count"] == 1
    assert Path(summary["review_markdown"]).exists()
    assert Path(summary["review_json"]).exists()
    assert any("market_analyst_memory.md" in path for path in summary["memory_paths"])

    context = SpecialistMemoryLog(tmp_path / "memory").get_context("Market Analyst")
    assert "Market Analyst" in context
    assert "LESSONS:" in context

    contexts = SpecialistMemoryLog(tmp_path / "memory").get_contexts(
        ["Market Analyst", "Risk Officer", "Missing Agent"]
    )
    assert "Market Analyst" in contexts
    assert "Risk Officer" in contexts
    assert "Missing Agent" not in contexts


@pytest.mark.unit
def test_find_company_run_payloads_filters_by_trade_date(tmp_path):
    first = tmp_path / "results" / "a" / "company_run.json"
    second = tmp_path / "results" / "b" / "company_run.json"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text(json.dumps(_payload()), encoding="utf-8")
    other = {**_payload(), "trade_date": "2026-05-12"}
    second.write_text(json.dumps(other), encoding="utf-8")

    payloads = find_company_run_payloads(tmp_path / "results", "2026-05-11")

    assert len(payloads) == 1
    assert payloads[0][1]["trade_date"] == "2026-05-11"
