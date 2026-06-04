from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _load_app_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "control_room_app.py"
    spec = importlib.util.spec_from_file_location("control_room_app", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_control_room_path_resolution_stays_inside_repo():
    app = _load_app_module()

    resolved = app.resolve_repo_path("results")
    assert app.REPO_ROOT.resolve() in resolved.parents

    with pytest.raises(ValueError):
        app.resolve_repo_path("..")


def test_department_prompt_is_research_only():
    app = _load_app_module()
    prompt = app.build_department_prompt(
        department_key="risk_office",
        department=app.DEPARTMENTS["risk_office"],
        topic="startup gate",
        task="Review carry risk.",
        context={
            "alpaca": {"account": {"status": "ACTIVE", "equity": "1000"}, "positions": [], "open_orders": []},
            "log": {"latest_log": {"name": "run.jsonl"}},
            "strategy": {"summary": {"top_strategy_scores": {}}},
        },
    )

    assert "Do not place orders" in prompt
    assert "Risk Office" in prompt
    assert "Review carry risk." in prompt


def test_save_department_task_writes_json_and_markdown(tmp_path):
    app = _load_app_module()
    app.TASK_DIR = tmp_path

    saved = app.save_department_task(
        department_key="training_development",
        department=app.DEPARTMENTS["training_development"],
        topic="agent scorecards",
        task="Create lessons.",
        model="qwen3:4b-instruct",
        prompt="prompt",
        memo="# Memo\n\nLesson.",
        used_ollama=False,
    )

    json_path = Path(saved["json_path"])
    markdown_path = Path(saved["markdown_path"])
    assert json_path.exists()
    assert markdown_path.exists()
    assert "Create lessons." in markdown_path.read_text(encoding="utf-8")
    assert "Lesson." in markdown_path.read_text(encoding="utf-8")


def test_control_room_meta_exposes_org_flow_and_crypto_coverage():
    app = _load_app_module()

    assert any(node["name"] == "CEO" for node in app.ORG_FLOW)
    assert app.UNIVERSE_GROUPS["crypto_linked_tradeable"]["symbols"]
    assert "MSTR" in app.UNIVERSE_GROUPS["crypto_linked_tradeable"]["symbols"]
    assert "BTC-USD" in app.UNIVERSE_GROUPS["direct_crypto_research"]["symbols"]
    assert app.UNIVERSE_GROUPS["direct_crypto_research"]["mode"] == "research only"


def test_compact_event_preserves_operational_detail():
    app = _load_app_module()

    event = app.compact_event(
        {
            "logged_at": "2026-06-03T12:00:00+00:00",
            "event": "autonomous_ceo_startup_flat_gate_blocked",
            "reason": "account_not_flat_at_start",
            "positions_count": 2,
            "open_orders_count": 3,
        }
    )

    assert event["event"] == "autonomous_ceo_startup_flat_gate_blocked"
    assert "account_not_flat_at_start" in event["detail"]
    assert "positions: 2" in event["detail"]
    assert "orders: 3" in event["detail"]
