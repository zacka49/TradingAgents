from unittest.mock import Mock, patch

import pytest

from tradingagents.llm_clients.compute_policy import (
    apply_compute_policy,
    is_cloud_ollama_model,
)


def _ollama_tags(*names: str) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "models": [{"name": name} for name in names],
    }
    return response


@pytest.mark.unit
def test_local_only_blocks_online_provider_and_chooses_installed_local_models():
    config = {
        "llm_provider": "openai",
        "backend_url": "https://api.openai.com/v1",
        "quick_think_llm": "gpt-5.4-mini",
        "deep_think_llm": "gpt-5.4",
        "llm_budget_mode": "local_only",
        "allow_online_llm": False,
        "ollama_model_probe_timeout_seconds": 0.1,
    }

    with patch(
        "tradingagents.llm_clients.compute_policy.requests.get",
        return_value=_ollama_tags(
            "qwen3:0.6b",
            "qwen3:4b",
            "gpt-oss:20b",
            "kimi-k2.6:cloud",
        ),
    ):
        guarded = apply_compute_policy(config)

    assert guarded["llm_provider"] == "ollama"
    assert guarded["backend_url"] == "http://localhost:11434/v1"
    assert guarded["ollama_base_url"] == "http://localhost:11434"
    assert guarded["quick_think_llm"] == "qwen3:4b"
    assert guarded["deep_think_llm"] == "gpt-oss:20b"
    assert guarded["compute_policy_report"]["action"] == "local_only_guard_applied"
    assert "kimi-k2.6:cloud" not in guarded["compute_policy_report"]["installed_local_models"]


@pytest.mark.unit
def test_allow_online_opt_in_preserves_hosted_provider():
    config = {
        "llm_provider": "groq",
        "backend_url": "https://api.groq.com/openai/v1",
        "quick_think_llm": "openai/gpt-oss-20b",
        "deep_think_llm": "openai/gpt-oss-120b",
        "llm_budget_mode": "allow_online",
        "allow_online_llm": True,
    }

    with patch("tradingagents.llm_clients.compute_policy.requests.get") as mock_get:
        guarded = apply_compute_policy(config)

    mock_get.assert_not_called()
    assert guarded["llm_provider"] == "groq"
    assert guarded["backend_url"] == "https://api.groq.com/openai/v1"
    assert guarded["compute_policy_report"]["online_llm_allowed"] is True


@pytest.mark.unit
def test_allow_online_flag_alone_is_not_enough():
    config = {
        "llm_provider": "groq",
        "backend_url": "https://api.groq.com/openai/v1",
        "quick_think_llm": "openai/gpt-oss-20b",
        "deep_think_llm": "openai/gpt-oss-120b",
        "llm_budget_mode": "local_only",
        "allow_online_llm": True,
        "ollama_model_probe_timeout_seconds": 0.1,
    }

    with patch(
        "tradingagents.llm_clients.compute_policy.requests.get",
        return_value=_ollama_tags("qwen3:0.6b"),
    ):
        guarded = apply_compute_policy(config)

    assert guarded["llm_provider"] == "ollama"
    assert guarded["quick_think_llm"] == "qwen3:0.6b"
    assert guarded["deep_think_llm"] == "qwen3:0.6b"


@pytest.mark.unit
def test_string_false_allow_online_does_not_enable_hosted_provider():
    config = {
        "llm_provider": "openai",
        "backend_url": "https://api.openai.com/v1",
        "quick_think_llm": "gpt-5.4-mini",
        "deep_think_llm": "gpt-5.4",
        "llm_budget_mode": "allow_online",
        "allow_online_llm": "false",
        "ollama_model_probe_timeout_seconds": 0.1,
    }

    with patch(
        "tradingagents.llm_clients.compute_policy.requests.get",
        return_value=_ollama_tags("qwen3:0.6b"),
    ):
        guarded = apply_compute_policy(config)

    assert guarded["llm_provider"] == "ollama"
    assert guarded["hosted_llm_allowed"] is False


@pytest.mark.unit
def test_cloud_ollama_staff_model_replaced_by_local_model():
    config = {
        "llm_provider": "ollama",
        "backend_url": "http://localhost:11434/v1",
        "ollama_base_url": "http://localhost:11434",
        "quick_think_llm": "qwen3:0.6b",
        "deep_think_llm": "qwen3:0.6b",
        "ollama_staff_model": "kimi-k2.6:cloud",
        "llm_budget_mode": "local_only",
        "allow_online_llm": False,
        "ollama_model_probe_timeout_seconds": 0.1,
    }

    with patch(
        "tradingagents.llm_clients.compute_policy.requests.get",
        return_value=_ollama_tags("qwen3:0.6b", "kimi-k2.6:cloud"),
    ):
        guarded = apply_compute_policy(config)

    assert guarded["ollama_staff_model"] == "qwen3:0.6b"
    assert is_cloud_ollama_model("kimi-k2.6:cloud")
