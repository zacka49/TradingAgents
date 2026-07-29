"""Extract role-specific distillation skeletons from saved run artifacts.

The script reconstructs the information available to a selected role from
``final_state.json`` or ``full_states_log_*.json`` files. It never calls an LLM
and never reads environment files, broker credentials, or order endpoints.
Gold assistant answers remain blank for an operator to generate and review.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


@dataclass(frozen=True)
class RoleSpec:
    role: str
    system_prompt: str
    input_fields: tuple[tuple[str, str], ...]
    output_field: str


ROLE_SPECS: dict[str, RoleSpec] = {
    "strategy_researcher": RoleSpec(
        role="strategy_researcher",
        system_prompt=(
            "You are the Strategy Researcher in the TradingAgents Research "
            "Department. Apply quant-strategy-research first, supported by "
            "data-quality-strategy-governance and equities-momentum-desk. Turn "
            "one candidate into a testable paper-trading memo with a named setup, "
            "trigger, confirmation, invalidation, sizing logic, holding period, "
            "failure mode, required data, promotion evidence, and no-trade "
            "condition. Preserve strategy-library promotion status. Research "
            "authority only: never submit or authorize an order."
        ),
        input_fields=(
            ("Pre-market stock discovery", "stock_discovery_report"),
            ("Market analysis", "market_report"),
            ("Sentiment analysis", "sentiment_report"),
            ("News analysis", "news_report"),
            ("Current-news scout", "current_news_report"),
            ("Fundamentals analysis", "fundamentals_report"),
        ),
        output_field="strategy_report",
    ),
    "risk_office_guardian": RoleSpec(
        role="risk_office_guardian",
        system_prompt=(
            "You are the Risk Office Guardian for TradingAgents. Apply "
            "multi-desk-portfolio-risk first, supported by "
            "data-quality-strategy-governance. Audit max loss, position and "
            "capital caps, correlated exposure, stale or missing data, liquidity, "
            "slippage, bracket protection, and deterministic execution readiness. "
            "Explicitly block unsupported, oversized, stale, correlated, or "
            "policy-violating entries and name the evidence required to unblock "
            "them. Advisory authority only: never submit or authorize an order."
        ),
        input_fields=(
            ("Market analysis", "market_report"),
            ("News analysis", "news_report"),
            ("Fundamentals analysis", "fundamentals_report"),
            ("Research Department synthesis", "research_department_report"),
            ("Research Manager plan", "investment_plan"),
            ("Investment Committee memo", "investment_committee_report"),
            ("Trader plan", "trader_investment_decision"),
            ("Trading Desk plan", "trading_desk_report"),
        ),
        output_field="risk_office_report",
    ),
    "chief_investment_officer": RoleSpec(
        role="chief_investment_officer",
        system_prompt=(
            "You are the Chief Investment Officer for TradingAgents. Apply "
            "multi-desk-portfolio-risk first, supported by "
            "data-quality-strategy-governance. Convert research into a "
            "capital-aware stance that states decision status, decisive evidence, "
            "capital cap, desk cap, portfolio and correlation conflicts, rejection "
            "conditions, and the next approved research or paper action. Keep "
            "research-only strategies out of autonomous execution. Advisory "
            "authority only: never submit or authorize an order."
        ),
        input_fields=(
            ("Pre-market stock discovery", "stock_discovery_report"),
            ("Market analysis", "market_report"),
            ("Sentiment analysis", "sentiment_report"),
            ("News analysis", "news_report"),
            ("Fundamentals analysis", "fundamentals_report"),
            ("Research Department synthesis", "research_department_report"),
            ("Research Manager plan", "investment_plan"),
        ),
        output_field="investment_committee_report",
    ),
}


def _one_line(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _bounded(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 25)].rstrip() + "\n[SECTION TRUNCATED]"


def _redact(value: str) -> str:
    patterns = (
        r"(?i)\b(api[_-]?key|secret|password|access[_-]?token)\b"
        r"(\s*[:=]\s*)([^\s,;]+)",
        r"(?i)\b(bearer)(\s+)([a-z0-9._~+/=-]{16,})",
    )
    result = value
    for pattern in patterns:
        result = re.sub(pattern, r"\1\2[REDACTED]", result)
    return result


def _artifact_paths(results_dir: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    patterns = ("final_state.json", "full_states_log_*.json")
    for pattern in patterns:
        for path in sorted(results_dir.rglob(pattern)):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield path


def _load_state(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def build_role_input(
    state: dict[str, Any],
    spec: RoleSpec,
    *,
    max_input_chars: int,
) -> str:
    ticker = _one_line(state.get("company_of_interest")) or "unknown"
    trade_date = _one_line(state.get("trade_date")) or "unknown"
    sections = [
        "Reconstructed historical role input from a saved paper/research run.",
        "Use only the supplied evidence. Do not invent prices, fills, data quality, "
        "or promotion status. If evidence is missing, state the blocker.",
        f"Instrument: {ticker}",
        f"Trade date: {trade_date}",
    ]
    per_section = max(800, max_input_chars // max(1, len(spec.input_fields)))
    for heading, field in spec.input_fields:
        value = state.get(field, "")
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value or "")
        text = _bounded(_redact(text.strip()), per_section)
        sections.extend(["", f"## {heading}", text or "[not available]"])
    sections.extend(
        [
            "",
            "## Required deliverable",
            "Produce the role-specific memo required by the system instruction. "
            "Use explicit headings and concrete blockers. This is research/paper "
            "analysis only; do not claim an order was submitted.",
        ]
    )
    return _bounded("\n".join(sections), max_input_chars)


def build_skeleton(
    state: dict[str, Any],
    spec: RoleSpec,
    *,
    source: Path,
    max_input_chars: int,
    include_baseline_answer: bool,
) -> dict[str, Any]:
    user_prompt = build_role_input(
        state,
        spec,
        max_input_chars=max_input_chars,
    )
    metadata: dict[str, Any] = {
        "role": spec.role,
        "source": str(source),
        "ticker": _one_line(state.get("company_of_interest")) or "unknown",
        "trade_date": _one_line(state.get("trade_date")) or "unknown",
        "gold_status": "pending_human_review",
        "input_reconstruction": "saved_state_upstream_fields",
    }
    if include_baseline_answer:
        metadata["baseline_answer"] = _redact(
            str(state.get(spec.output_field) or "").strip()
        )
    return {
        "messages": [
            {"role": "system", "content": spec.system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": ""},
        ],
        "metadata": metadata,
    }


def extract_skeletons(
    *,
    results_dir: Path,
    spec: RoleSpec,
    max_examples: int,
    max_input_chars: int,
    include_baseline_answer: bool,
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    fingerprints: set[str] = set()
    for path in _artifact_paths(results_dir):
        state = _load_state(path)
        if state is None or not _one_line(state.get("company_of_interest")):
            continue
        example = build_skeleton(
            state,
            spec,
            source=path,
            max_input_chars=max_input_chars,
            include_baseline_answer=include_baseline_answer,
        )
        user_text = example["messages"][1]["content"]
        fingerprint = hashlib.sha256(
            f"{spec.role}\0{user_text}".encode("utf-8")
        ).hexdigest()
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        examples.append(example)
        if max_examples > 0 and len(examples) >= max_examples:
            break
    return examples


def write_jsonl(examples: Iterable[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract blank conversational JSONL skeletons for optional role "
            "distillation. No LLM or trading endpoint is called."
        )
    )
    parser.add_argument("--role", required=True, choices=sorted(ROLE_SPECS))
    parser.add_argument("--results-dir", default="results")
    parser.add_argument(
        "--output",
        default="",
        help=(
            "Output JSONL path. Defaults to "
            "docs/distillation/datasets/<role>_skeleton.jsonl."
        ),
    )
    parser.add_argument("--max-examples", type=int, default=500)
    parser.add_argument("--max-input-chars", type=int, default=16000)
    parser.add_argument(
        "--include-baseline-answer",
        action="store_true",
        help="Copy the old role output into metadata for comparison, not training.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacement of an existing output file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count extractable examples without writing JSONL.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"Results directory not found: {results_dir}", file=sys.stderr)
        return 2
    if args.max_input_chars < 1000:
        print("--max-input-chars must be at least 1000", file=sys.stderr)
        return 2

    spec = ROLE_SPECS[args.role]
    examples = extract_skeletons(
        results_dir=results_dir,
        spec=spec,
        max_examples=max(0, args.max_examples),
        max_input_chars=args.max_input_chars,
        include_baseline_answer=args.include_baseline_answer,
    )
    if not examples:
        print(
            f"No usable saved-state artifacts found under {results_dir}.",
            file=sys.stderr,
        )
        return 1

    output = Path(
        args.output
        or f"docs/distillation/datasets/{args.role}_skeleton.jsonl"
    )
    if args.dry_run:
        print(
            f"{len(examples)} unique {args.role} inputs are extractable; "
            "no file written."
        )
        return 0
    if output.exists() and not args.overwrite:
        print(
            f"Refusing to replace existing output without --overwrite: {output}",
            file=sys.stderr,
        )
        return 2

    write_jsonl(examples, output)
    print(
        f"Wrote {len(examples)} blank gold-answer skeletons for "
        f"{args.role}: {output}"
    )
    print("Review/redact inputs, then generate and human-check gold answers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
