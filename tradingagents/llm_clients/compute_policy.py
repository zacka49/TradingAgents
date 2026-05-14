"""Local-first LLM budget policy.

The trading business can iterate many times per day, so cloud LLM calls must be
an explicit opt-in. This module keeps the default path on local Ollama models
and avoids accidental token spend from environment variables or CLI selections.
"""

from __future__ import annotations

from copy import deepcopy
import logging
import os
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

LOCAL_LLM_PROVIDER = "ollama"
LOCAL_OLLAMA_BASE_URL = "http://localhost:11434"
LOCAL_OLLAMA_BACKEND_URL = f"{LOCAL_OLLAMA_BASE_URL}/v1"
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}

ONLINE_LLM_PROVIDERS = {
    "anthropic",
    "azure",
    "deepseek",
    "glm",
    "google",
    "groq",
    "openai",
    "openrouter",
    "qwen",
    "xai",
}

LOCAL_QUICK_MODEL_PRIORITY = (
    "qwen3:8b",
    "qwen3:latest",
    "qwen3:4b",
    "qwen3:1.7b",
    "qwen3:0.6b",
)

LOCAL_DEEP_MODEL_PRIORITY = (
    "gpt-oss:20b",
    "gpt-oss:latest",
    "qwen3:30b",
    "qwen3:32b",
    "qwen3:14b",
    "qwen3:8b",
    "qwen3:latest",
    "qwen3:4b",
    "qwen3:0.6b",
)


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def online_llm_allowed(config: Dict[str, Any]) -> bool:
    return _truthy(config.get("allow_online_llm")) or env_flag(
        "TRADINGAGENTS_ALLOW_ONLINE_LLM", False
    )


def llm_budget_mode(config: Dict[str, Any]) -> str:
    return str(
        os.getenv(
            "TRADINGAGENTS_LLM_BUDGET_MODE",
            config.get("llm_budget_mode", "local_only"),
        )
    ).strip().lower()


def hosted_llm_allowed(config: Dict[str, Any]) -> bool:
    return llm_budget_mode(config) != "local_only" and online_llm_allowed(config)


def is_cloud_ollama_model(model: str | None) -> bool:
    return bool(model) and str(model).strip().lower().endswith(":cloud")


def ollama_base_url_from_config(config: Dict[str, Any]) -> str:
    explicit = str(config.get("ollama_base_url") or "").strip()
    if explicit:
        return explicit.rstrip("/")

    backend = str(config.get("backend_url") or "").strip()
    if backend:
        return backend.removesuffix("/v1").rstrip("/")

    return LOCAL_OLLAMA_BASE_URL


def is_local_url(url: str | None) -> bool:
    if not url:
        return True
    parsed = urlparse(str(url))
    if not parsed.scheme and not parsed.netloc:
        return True
    return parsed.hostname in LOCAL_HOSTS


def list_local_ollama_models(base_url: str, timeout_seconds: float = 2.0) -> List[str]:
    try:
        response = requests.get(
            f"{base_url.rstrip('/')}/api/tags",
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Could not inspect local Ollama models: %s", exc)
        return []

    names: List[str] = []
    for model in response.json().get("models", []):
        name = str(model.get("name") or model.get("model") or "").strip()
        if name and not is_cloud_ollama_model(name):
            names.append(name)
    return names


def _choose_local_model(
    current_model: str,
    installed_models: Iterable[str],
    priority: Iterable[str],
    *,
    allow_current_fallback: bool = True,
) -> str:
    installed = set(installed_models)
    current = str(current_model or "").strip()

    for candidate in priority:
        if candidate in installed:
            return candidate

    if allow_current_fallback and current and not is_cloud_ollama_model(current):
        return current

    return "qwen3:0.6b"


def apply_compute_policy(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a guarded config that avoids accidental paid/cloud LLM usage.

    In ``local_only`` mode, any online provider or Ollama cloud model is moved
    back to local Ollama. Set ``TRADINGAGENTS_ALLOW_ONLINE_LLM=1`` and
    ``TRADINGAGENTS_LLM_BUDGET_MODE=allow_online`` when you intentionally want
    hosted LLM calls.
    """
    guarded = deepcopy(config)
    mode = llm_budget_mode(guarded)
    allow_online = online_llm_allowed(guarded)
    allow_hosted = hosted_llm_allowed(guarded)
    provider = str(guarded.get("llm_provider", LOCAL_LLM_PROVIDER)).lower()

    guarded["llm_budget_mode"] = mode
    guarded["allow_online_llm"] = allow_online
    guarded["hosted_llm_allowed"] = allow_hosted

    if allow_hosted:
        guarded["compute_policy_report"] = {
            "mode": mode,
            "online_llm_allowed": True,
            "action": "online_provider_allowed",
            "provider": provider,
        }
        return guarded

    reasons: List[str] = []
    forced_local_provider = provider != LOCAL_LLM_PROVIDER
    if provider in ONLINE_LLM_PROVIDERS:
        reasons.append(f"online provider '{provider}' blocked")
        guarded["llm_provider"] = LOCAL_LLM_PROVIDER
        guarded["backend_url"] = LOCAL_OLLAMA_BACKEND_URL
        guarded["ollama_base_url"] = LOCAL_OLLAMA_BASE_URL
    elif provider == LOCAL_LLM_PROVIDER:
        backend_url = str(guarded.get("backend_url") or LOCAL_OLLAMA_BACKEND_URL)
        base_url = ollama_base_url_from_config(guarded)
        if not is_local_url(backend_url) or not is_local_url(base_url):
            reasons.append("non-local Ollama URL blocked")
            guarded["backend_url"] = LOCAL_OLLAMA_BACKEND_URL
            guarded["ollama_base_url"] = LOCAL_OLLAMA_BASE_URL
            forced_local_provider = True
    else:
        reasons.append(f"unknown provider '{provider}' forced to local Ollama")
        guarded["llm_provider"] = LOCAL_LLM_PROVIDER
        guarded["backend_url"] = LOCAL_OLLAMA_BACKEND_URL
        guarded["ollama_base_url"] = LOCAL_OLLAMA_BASE_URL

    if not guarded.get("backend_url"):
        guarded["backend_url"] = LOCAL_OLLAMA_BACKEND_URL
    if not guarded.get("ollama_base_url"):
        guarded["ollama_base_url"] = LOCAL_OLLAMA_BASE_URL

    base_url = ollama_base_url_from_config(guarded)
    installed_models = list_local_ollama_models(
        base_url,
        timeout_seconds=float(guarded.get("ollama_model_probe_timeout_seconds", 2.0)),
    )

    original_quick = str(guarded.get("quick_think_llm", "qwen3:0.6b"))
    original_deep = str(guarded.get("deep_think_llm", "qwen3:0.6b"))
    quick = _choose_local_model(
        original_quick,
        installed_models,
        guarded.get("local_quick_model_priority", LOCAL_QUICK_MODEL_PRIORITY),
        allow_current_fallback=not forced_local_provider,
    )
    deep = _choose_local_model(
        original_deep,
        installed_models,
        guarded.get("local_deep_model_priority", LOCAL_DEEP_MODEL_PRIORITY),
        allow_current_fallback=not forced_local_provider,
    )

    if quick != original_quick:
        reasons.append(f"quick model '{original_quick}' replaced with '{quick}'")
    if deep != original_deep:
        reasons.append(f"deep model '{original_deep}' replaced with '{deep}'")

    guarded["quick_think_llm"] = quick
    guarded["deep_think_llm"] = deep

    staff_model = str(guarded.get("ollama_staff_model", quick))
    if is_cloud_ollama_model(staff_model):
        reasons.append(f"staff model '{staff_model}' replaced with '{quick}'")
        guarded["ollama_staff_model"] = quick

    guarded["compute_policy_report"] = {
        "mode": mode,
        "online_llm_allowed": False,
        "action": "local_only_guard_applied" if reasons else "local_only_no_change",
        "provider": guarded.get("llm_provider"),
        "quick_model": guarded.get("quick_think_llm"),
        "deep_model": guarded.get("deep_think_llm"),
        "installed_local_models": installed_models,
        "reasons": reasons,
    }
    if reasons:
        logger.warning("Local-first compute policy applied: %s", "; ".join(reasons))
    return guarded
