from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any

import requests


DEFAULT_MODELS = [
    "qwen3:4b-instruct",
    "llama3.2:3b",
    "phi4-mini:latest",
    "phi4-mini-reasoning:latest",
    "qwen3:0.6b",
]


TASKS = [
    {
        "name": "risk_veto_json",
        "format": "json",
        "prompt": (
            "Return strict JSON only with keys risk_level, veto, reasons. "
            "Scenario: AI chip stock is up 16% in one day, earnings are tomorrow, "
            "QQQ is below VWAP, spread is 0.18%, and the bot already had two "
            "same-symbol stale-loser exits this week."
        ),
    },
    {
        "name": "catalyst_json",
        "format": "json",
        "prompt": (
            "Return strict JSON only with keys ticker, catalyst_type, direction, "
            "event_time, confidence, verify_after_open. Headline: Broadcom reports "
            "earnings tomorrow after the close while AI custom silicon names rally."
        ),
    },
    {
        "name": "strategy_setup",
        "format": None,
        "prompt": (
            "As a day-trading strategy researcher, write a compact setup for NVDA. "
            "Include trigger, confirmation, invalidation, sizing note, and do-not-trade "
            "condition. Keep it under 120 words."
        ),
    },
    {
        "name": "post_market_critique",
        "format": None,
        "prompt": (
            "A paper trade entered HOOD after a strong open, hit +0.4%, then faded "
            "to -0.8% and was cut by stale-loser logic. Give one lesson, one rule "
            "change to test, and one metric to track next session. Keep it concise."
        ),
    },
]


@dataclass
class BenchmarkResult:
    model: str
    task: str
    elapsed_seconds: float
    valid_json: bool | None
    response_chars: int
    response_preview: str
    error: str = ""


def _generate(
    *,
    base_url: str,
    model: str,
    prompt: str,
    json_format: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 2048,
            "num_predict": 240,
        },
    }
    if json_format:
        payload["format"] = "json"

    response = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json=payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _valid_json(text: str) -> bool:
    try:
        json.loads(text)
    except Exception:
        return False
    return True


def run_benchmark(
    *,
    models: list[str],
    base_url: str,
    timeout_seconds: int,
) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    for model in models:
        for task in TASKS:
            started = time.perf_counter()
            try:
                payload = _generate(
                    base_url=base_url,
                    model=model,
                    prompt=task["prompt"],
                    json_format=bool(task["format"] == "json"),
                    timeout_seconds=timeout_seconds,
                )
                response_text = str(payload.get("response") or "").strip()
                valid_json = (
                    _valid_json(response_text) if task["format"] == "json" else None
                )
                results.append(
                    BenchmarkResult(
                        model=model,
                        task=task["name"],
                        elapsed_seconds=round(time.perf_counter() - started, 2),
                        valid_json=valid_json,
                        response_chars=len(response_text),
                        response_preview=response_text.replace("\n", " ")[:220],
                    )
                )
            except Exception as exc:
                results.append(
                    BenchmarkResult(
                        model=model,
                        task=task["name"],
                        elapsed_seconds=round(time.perf_counter() - started, 2),
                        valid_json=False if task["format"] == "json" else None,
                        response_chars=0,
                        response_preview="",
                        error=str(exc),
                    )
                )
    return results


def render_markdown(results: list[BenchmarkResult]) -> str:
    lines = [
        f"# Local Model Benchmark - {datetime.now(UTC).date()}",
        "",
        "| Model | Task | Seconds | Valid JSON | Chars | Error | Preview |",
        "| --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    for result in results:
        lines.append(
            "| {model} | {task} | {elapsed_seconds:.2f} | {valid_json} | "
            "{response_chars} | {error} | {preview} |".format(
                model=result.model,
                task=result.task,
                elapsed_seconds=result.elapsed_seconds,
                valid_json="" if result.valid_json is None else result.valid_json,
                response_chars=result.response_chars,
                error=_cell(result.error),
                preview=_cell(result.response_preview),
            )
        )
    return "\n".join(lines) + "\n"


def _cell(value: str) -> str:
    return value.replace("|", "/").replace("\n", " ").strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark local Ollama models against trading-agent tasks."
    )
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument(
        "--output",
        default="results/research_department/local_model_benchmark_latest.md",
    )
    parser.add_argument("--json-output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    models = args.models or DEFAULT_MODELS
    results = run_benchmark(
        models=models,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(results), encoding="utf-8")
    print(f"Wrote {output_path}")

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps([asdict(result) for result in results], indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {json_path}")

    failures = [result for result in results if result.error]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
