"""Explicit Ollama health check for the pre-market ops task (T1).

The 2026-06-03 control-room incident showed the failure mode this guards
against: Ollama was unreachable (HTTP 404), local staff memos silently
degraded to a fallback template, and nobody noticed for weeks. This script
makes that state loud and recorded instead of silent.

This check is informational only. Core paper trading does not depend on
Ollama (``--with-staff-memo`` is opt-in), so a degraded result here should
not by itself block the trading session -- it should be visible in the daily
digest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients.compute_policy import (
    LOCAL_OLLAMA_BASE_URL,
    list_local_ollama_models,
    ollama_base_url_from_config,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opslib import ops_root, today_str, utc_now  # noqa: E402


def check_ollama_health(config: dict | None = None) -> dict:
    config = config or DEFAULT_CONFIG
    base_url = ollama_base_url_from_config(config) or LOCAL_OLLAMA_BASE_URL
    installed_models = list_local_ollama_models(base_url, timeout_seconds=3.0)
    reachable = bool(installed_models) or _server_responds(base_url)

    quick_model = str(config.get("quick_think_llm", "qwen3:0.6b"))
    deep_model = str(config.get("deep_think_llm", "qwen3:0.6b"))
    quick_ready = quick_model in installed_models
    deep_ready = deep_model in installed_models

    if not reachable:
        status = "error"
        summary = f"Ollama unreachable at {base_url}. Staff memos will fall back or be skipped."
    elif not (quick_ready and deep_ready):
        status = "degraded"
        missing = [m for m, ready in ((quick_model, quick_ready), (deep_model, deep_ready)) if not ready]
        summary = f"Ollama reachable but missing configured model(s): {', '.join(missing)}."
    else:
        status = "ok"
        summary = f"Ollama reachable with {len(installed_models)} model(s); quick/deep models present."

    return {
        "checked_at": utc_now().isoformat(),
        "base_url": base_url,
        "reachable": reachable,
        "installed_models": installed_models,
        "quick_model": quick_model,
        "deep_model": deep_model,
        "quick_model_ready": quick_ready,
        "deep_model_ready": deep_ready,
        "status": status,
        "summary": summary,
    }


def _server_responds(base_url: str) -> bool:
    """list_local_ollama_models returns [] both when the server is down and when
    it legitimately has zero models installed; do one more direct check to
    tell those apart before declaring the server unreachable."""
    import requests

    try:
        response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
        return True
    except Exception:
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check local Ollama reachability and model readiness.")
    parser.add_argument("--results-dir", default="results/ops")
    parser.add_argument("--date", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env")
    args = build_parser().parse_args(argv)
    trade_date = args.date or today_str()

    report = check_ollama_health()

    output_dir = ops_root(args.results_dir) / "health"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"ollama_{trade_date}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"[{report['status'].upper()}] {report['summary']}", file=sys.stderr)
    return 0 if report["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
