"""Informational structural evaluation for local TradingAgents personas.

This script is deliberately separate from trading and order-submission paths.
It sends canned drills to the local Ollama API and checks that each persona
returns the structural elements required by ``docs/agent_skill_training_matrix.md``.

Codex Track B authors this harness but does not run model inference during the
parallel phase. Run it after the ``ta-*`` models have been built and merged.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Iterable, Sequence

import requests


@dataclass(frozen=True)
class Requirement:
    name: str
    alternatives: tuple[str, ...]

    def matches(self, response: str) -> bool:
        return any(re.search(pattern, response, re.IGNORECASE) for pattern in self.alternatives)


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    model: str
    role: str
    prompt: str
    requirements: tuple[Requirement, ...]


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    model: str
    role: str
    passed: bool
    elapsed_seconds: float
    missing: tuple[str, ...]
    response_preview: str
    error: str = ""


def _require(name: str, *alternatives: str) -> Requirement:
    return Requirement(name=name, alternatives=tuple(alternatives))


CASES: tuple[EvalCase, ...] = (
    EvalCase(
        "screener_liquid_rank",
        "ta-screener:latest",
        "Opportunity Scout",
        (
            "Rank AMD, NVDA, and PLTR for an intraday paper-trading watchlist. "
            "For every ticker include liquidity, relative volume, volatility, and "
            "a desk tag. Use compact headings or a table."
        ),
        (
            _require("liquidity", r"\bliquidity\b", r"\bspread\b"),
            _require("relative volume", r"relative volume", r"\brvol\b"),
            _require("volatility", r"\bvolatil"),
            _require("desk tag", r"\bdesk\b"),
        ),
    ),
    EvalCase(
        "screener_actionability",
        "ta-screener:latest",
        "Stock Discovery Researcher",
        (
            "Create a compact research list for NVDA and TSLA after a volatile "
            "premarket move. State the catalyst, risk owner, invalidation, and "
            "whether each is actionable now or watch-only."
        ),
        (
            _require("catalyst", r"\bcatalyst\b"),
            _require("risk owner", r"risk owner", r"\bowner\b"),
            _require("invalidation", r"\binvalidat"),
            _require("action status", r"actionable", r"watch[- ]only"),
        ),
    ),
    EvalCase(
        "screener_news_confirmation",
        "ta-screener:latest",
        "News Analyst",
        (
            "Classify this headline: 'Chip supplier raises guidance; shares gap "
            "8% premarket.' Include catalyst tag, direction, risk tag, action, "
            "and verification needs. Do not treat news alone as a trade trigger."
        ),
        (
            _require("catalyst tag", r"catalyst"),
            _require("direction", r"\bdirection\b", r"\bbullish\b", r"\bbearish\b"),
            _require("risk tag", r"risk"),
            _require("price/liquidity confirmation", r"\bprice\b.*\bliquid", r"\bliquid\b.*\bprice\b"),
        ),
    ),
    EvalCase(
        "analyst_market_setup",
        "ta-analyst:latest",
        "Market Analyst",
        (
            "AMD is above VWAP, relative volume is 1.8, ATR is elevated, and QQQ "
            "is below VWAP. Explain price, volume, volatility, VWAP, and regime; "
            "then name the setup classification and invalidation."
        ),
        (
            _require("price", r"\bprice\b"),
            _require("volume", r"\bvolume\b", r"\brvol\b"),
            _require("volatility", r"\bvolatil", r"\batr\b"),
            _require("VWAP", r"\bvwap\b"),
            _require("setup classification", r"\bsetup\b", r"\bclassification\b"),
            _require("invalidation", r"\binvalidat"),
        ),
    ),
    EvalCase(
        "analyst_fundamental_relevance",
        "ta-analyst:latest",
        "Fundamentals Analyst",
        (
            "A profitable mega-cap reports next week while today's intraday move "
            "is driven by index rebalancing. Separate long-term fundamentals from "
            "intraday tradeability and state whether fundamentals support, conflict "
            "with, or do not matter for today's setup."
        ),
        (
            _require("long-term fundamentals", r"long[- ]term", r"\bfundamental"),
            _require("intraday tradeability", r"\bintraday\b", r"tradeab"),
            _require("relevance verdict", r"\bsupport", r"\bconflict", r"do not matter", r"not material"),
        ),
    ),
    EvalCase(
        "analyst_data_gap",
        "ta-analyst:latest",
        "Market Analyst",
        (
            "Assess a possible breakout when the latest quote is stale and spread "
            "is unknown. Give the setup classification, invalidation, evidence "
            "limits, and whether the idea is tradeable or watch-only."
        ),
        (
            _require("setup classification", r"\bsetup\b", r"\bclassification\b"),
            _require("invalidation", r"\binvalidat"),
            _require("data gap", r"stale", r"missing", r"unknown"),
            _require("blocked/watch status", r"watch[- ]only", r"\bblock", r"not tradeable"),
        ),
    ),
    EvalCase(
        "quant_testable_setup",
        "ta-quant:latest",
        "Strategy Researcher",
        (
            "Turn an NVDA opening-range breakout candidate into a testable paper "
            "strategy. Include named setup, trigger, confirmation, invalidation, "
            "sizing, failure mode, required data, and promotion test."
        ),
        (
            _require("named setup", r"\bsetup\b", r"opening[- ]range"),
            _require("trigger", r"\btrigger\b", r"\bentry\b"),
            _require("confirmation", r"\bconfirm"),
            _require("invalidation", r"\binvalidat", r"\bstop\b"),
            _require("sizing", r"\bsiz"),
            _require("required data", r"required data", r"\bdata needed\b"),
            _require("paper-test/promotion", r"paper[- ]test", r"\bpromotion\b"),
        ),
    ),
    EvalCase(
        "quant_backtest_audit",
        "ta-quant:latest",
        "Backtest Lab",
        (
            "Audit a 24-trade backtest with no out-of-sample split and zero "
            "slippage. Address sample size, leakage, event dedupe, slippage, and "
            "give one verdict: pass, weak, insufficient sample, or research-only."
        ),
        (
            _require("sample size", r"sample"),
            _require("leakage", r"leak"),
            _require("event dedupe", r"dedup", r"duplicate"),
            _require("slippage", r"slippage"),
            _require("verdict", r"\bpass\b", r"\bweak\b", r"insufficient sample", r"research[- ]only"),
        ),
    ),
    EvalCase(
        "quant_promotion_data",
        "ta-quant:latest",
        "Strategy Researcher",
        (
            "A relative-strength continuation idea has positive in-sample return "
            "but weak profit factor. Write a compact memo with hypothesis, entry "
            "rules, invalidation, required data, paper-only status, and measurable "
            "promotion condition."
        ),
        (
            _require("hypothesis", r"\bhypothesis\b"),
            _require("entry rules", r"\bentry\b", r"\btrigger\b"),
            _require("invalidation", r"\binvalidat", r"\bstop\b"),
            _require("required data", r"\bdata\b"),
            _require("paper-only", r"paper[- ]only", r"paper test"),
            _require("promotion condition", r"\bpromotion\b", r"promot"),
        ),
    ),
    EvalCase(
        "bull_evidence_case",
        "ta-bull:latest",
        "Bull Researcher",
        (
            "Build the strongest evidence-backed bull case for AMD after a "
            "volume-confirmed breakout. Include a trigger, confirmation, upside "
            "case, and an invalidation that would disprove the thesis."
        ),
        (
            _require("trigger", r"\btrigger\b", r"\bentry\b"),
            _require("confirmation", r"\bconfirm"),
            _require("bull thesis", r"\bbull", r"\bupside\b"),
            _require("invalidation", r"\binvalidat"),
        ),
    ),
    EvalCase(
        "bull_preserves_caps",
        "ta-bull:latest",
        "Aggressive Analyst",
        (
            "Find the best risk-taking version of a PLTR momentum trade while "
            "preserving stops and order caps. State entry, stop, target, cap, and "
            "what evidence cancels the idea."
        ),
        (
            _require("entry", r"\bentry\b", r"\btrigger\b"),
            _require("stop", r"\bstop\b"),
            _require("target", r"\btarget\b"),
            _require("cap", r"\bcap\b", r"maximum"),
            _require("cancellation evidence", r"\bcancel", r"\binvalidat", r"do not trade"),
        ),
    ),
    EvalCase(
        "bull_catalyst_limits",
        "ta-bull:latest",
        "Bull Researcher",
        (
            "Make the bullish case for a stock gapping on an unverified social "
            "rumor. Be opinionated but evidence-first; include confirmation needs "
            "and a concrete invalidation."
        ),
        (
            _require("bull case", r"\bbull", r"\bupside\b"),
            _require("verification/confirmation", r"\bverif", r"\bconfirm"),
            _require("invalidation", r"\binvalidat"),
            _require("rumor risk", r"\brumor\b", r"unverified"),
        ),
    ),
    EvalCase(
        "bear_blocker",
        "ta-bear:latest",
        "Bear Researcher",
        (
            "Challenge a long NVDA thesis when the spread is wide, QQQ is weak, "
            "and the backtest has no out-of-sample split. Identify a concrete "
            "blocker or missing evidence item and state the invalidation level "
            "that would prove the bearish view wrong."
        ),
        (
            _require("blocker/missing evidence", r"\bblock", r"missing evidence", r"data gap"),
            _require("invalidation", r"\binvalidat"),
            _require("liquidity", r"\bspread\b", r"\bliquidity\b"),
            _require("backtest quality", r"out[- ]of[- ]sample", r"\bbacktest\b"),
        ),
    ),
    EvalCase(
        "bear_smallest_size",
        "ta-bear:latest",
        "Conservative Analyst",
        (
            "Review a volatile TSLA paper setup with mixed evidence. Find the "
            "smallest viable size or block it. Include exposure reduction, tighter "
            "invalidation, and the decisive reason."
        ),
        (
            _require("size/block", r"\bsize\b", r"\bblock"),
            _require("reduced exposure", r"\breduc", r"smallest"),
            _require("invalidation", r"\binvalidat", r"\bstop\b"),
            _require("decisive reason", r"\breason\b", r"because"),
        ),
    ),
    EvalCase(
        "bear_correlation",
        "ta-bear:latest",
        "Bear Researcher",
        (
            "The portfolio already owns AMD and QQQ. Challenge a proposed NVDA "
            "long for correlation, catalyst, liquidity, and valuation risk. End "
            "with block, watch, or risk-review plus the missing evidence."
        ),
        (
            _require("correlation", r"\bcorrel"),
            _require("catalyst", r"\bcatalyst\b"),
            _require("liquidity", r"\bliquid", r"\bspread\b"),
            _require("verdict", r"\bblock\b", r"\bwatch\b", r"risk[- ]review"),
            _require("missing evidence", r"missing", r"data gap", r"need"),
        ),
    ),
    EvalCase(
        "synth_risk_reward",
        "ta-synth:latest",
        "Neutral Analyst",
        (
            "Balance a bullish momentum case against stale-data and correlation "
            "risks. Separate upside, downside, uncertainty, and state whether "
            "risk/reward justifies paper exposure."
        ),
        (
            _require("upside", r"\bupside\b"),
            _require("downside", r"\bdownside\b", r"\brisk\b"),
            _require("uncertainty", r"\buncertain"),
            _require("paper-exposure verdict", r"paper exposure", r"risk.?reward"),
        ),
    ),
    EvalCase(
        "synth_director_questions",
        "ta-synth:latest",
        "Research Director",
        (
            "Synthesize conflicting market, news, and fundamentals reports. "
            "Return sections for evidence, uncertainty, conflicts, and decision "
            "questions. Do not make an order decision."
        ),
        (
            _require("evidence", r"\bevidence\b"),
            _require("uncertainty", r"\buncertain"),
            _require("conflicts", r"\bconflict"),
            _require("decision questions", r"decision question", r"\bquestions?\b"),
        ),
    ),
    EvalCase(
        "synth_research_only",
        "ta-synth:latest",
        "Neutral Analyst",
        (
            "A news-reversion idea has six trades and negative return. Weigh the "
            "possible edge against evidence quality and deliver a balanced final "
            "stance with the promotion blocker."
        ),
        (
            _require("possible upside", r"\bupside\b", r"\bedge\b"),
            _require("evidence quality", r"\bevidence\b", r"\bsample\b"),
            _require("balanced stance", r"\bstance\b", r"\bverdict\b", r"research[- ]only"),
            _require("promotion blocker", r"\bblock", r"not promot", r"promotion"),
        ),
    ),
    EvalCase(
        "decider_conflict",
        "ta-decider:latest",
        "Research Manager",
        (
            "Resolve a bull/bear disagreement into approve, reject, watch, or "
            "risk-review. Cite the decisive evidence and explicitly name the "
            "rejected alternative."
        ),
        (
            _require("decision", r"\bapprove\b", r"\breject\b", r"\bwatch\b", r"risk[- ]review"),
            _require("decisive evidence", r"decisive evidence", r"\bevidence\b"),
            _require("rejected alternative", r"rejected alternative", r"alternative rejected"),
        ),
    ),
    EvalCase(
        "decider_capital_caps",
        "ta-decider:latest",
        "Chief Investment Officer",
        (
            "Convert an approved AMD stance into a portfolio-aware memo. Include "
            "capital cap, desk cap, portfolio conflict, and a rejection reason "
            "that would block allocation."
        ),
        (
            _require("capital cap", r"capital cap"),
            _require("desk cap", r"desk cap"),
            _require("portfolio conflict", r"portfolio conflict", r"\bcorrel"),
            _require("rejection reason", r"rejection reason", r"\bblock"),
        ),
    ),
    EvalCase(
        "decider_execution_plan",
        "ta-decider:latest",
        "Trader",
        (
            "Turn an approved momentum stance into a paper execution idea. Include "
            "named setup, timing, entry, stop, target, no-trade condition, expected "
            "holding period, and position cap."
        ),
        (
            _require("named setup", r"\bsetup\b"),
            _require("timing", r"\btiming\b", r"\bopen\b"),
            _require("entry", r"\bentry\b"),
            _require("stop", r"\bstop\b"),
            _require("target", r"\btarget\b"),
            _require("no-trade condition", r"no[- ]trade", r"stand[- ]down"),
            _require("holding period", r"holding period", r"\bintraday\b"),
            _require("position cap", r"\bcap\b"),
        ),
    ),
    EvalCase(
        "risk_trade_audit",
        "ta-risk:latest",
        "Risk Office Guardian",
        (
            "Audit a proposed paper long with a stale quote, 0.25% spread, high "
            "semiconductor exposure, and excessive notional. Cover max loss, "
            "correlation, stale data, execution readiness, and final block status."
        ),
        (
            _require("max loss", r"max(?:imum)? loss"),
            _require("correlation", r"\bcorrel"),
            _require("stale data", r"\bstale\b"),
            _require("execution readiness", r"execution readiness", r"not ready"),
            _require("block status", r"\bblock"),
        ),
    ),
    EvalCase(
        "risk_compliance",
        "ta-risk:latest",
        "Operations Compliance Auditor",
        (
            "Audit a proposed action for paper-only, market-open, order, and data "
            "rules. Record every compliance blocker and required artifact."
        ),
        (
            _require("paper-only", r"paper[- ]only"),
            _require("market rule", r"market[- ]open", r"market open"),
            _require("order rule", r"\border\b"),
            _require("data rule", r"\bdata\b"),
            _require("blockers", r"\bblock"),
            _require("required artifact", r"\bartifact"),
        ),
    ),
    EvalCase(
        "risk_supported_trade",
        "ta-risk:latest",
        "Risk Office Guardian",
        (
            "A small paper trade has fresh data, narrow spread, bracket exits, and "
            "low correlation. State approval conditions, deterministic blockers, "
            "maximum loss, and monitoring requirements without submitting an order."
        ),
        (
            _require("approval conditions", r"approval condition", r"\bapprove"),
            _require("deterministic blockers", r"\bblock"),
            _require("maximum loss", r"max(?:imum)? loss"),
            _require("monitoring", r"\bmonitor"),
        ),
    ),
    EvalCase(
        "coach_measurable_actions",
        "ta-coach:latest",
        "Evaluation Analyst",
        (
            "Score a Market Analyst whose report omitted invalidation. Assess "
            "evidence quality, handoff quality, and outcome relevance, then give "
            "a measurable next action rather than generic praise."
        ),
        (
            _require("evidence quality", r"evidence quality"),
            _require("handoff quality", r"handoff quality"),
            _require("outcome relevance", r"outcome relevance"),
            _require("measurable action", r"next action", r"next run", r"\bmeasure"),
        ),
    ),
    EvalCase(
        "coach_role_drill",
        "ta-coach:latest",
        "Training Development Coach",
        (
            "Assign the Market Analyst and Risk Office Guardian one primary skill, "
            "one drill, and one success metric each for the next run. Cover both "
            "active roles in a compact table."
        ),
        (
            _require("agent/role", r"\bagent\b", r"\brole\b"),
            _require("skill", r"\bskill\b"),
            _require("drill", r"\bdrill\b"),
            _require("success metric", r"success metric"),
            _require("both roles", r"market analyst", r"risk office guardian"),
        ),
    ),
    EvalCase(
        "coach_promotion_trigger",
        "ta-coach:latest",
        "Training Development Coach",
        (
            "Create a one-week coaching plan for a noisy Strategy Researcher. "
            "Include evidence to collect, blocker checks, output schema, drill, "
            "success metric, and promotion or demotion trigger."
        ),
        (
            _require("evidence", r"\bevidence\b"),
            _require("blockers", r"\bblock"),
            _require("output schema", r"output schema", r"\bformat\b"),
            _require("drill", r"\bdrill\b"),
            _require("success metric", r"success metric"),
            _require("promotion/demotion", r"\bpromotion\b", r"\bdemotion\b"),
        ),
    ),
)


def evaluate_response(case: EvalCase, response: str) -> tuple[bool, tuple[str, ...]]:
    missing = tuple(
        requirement.name
        for requirement in case.requirements
        if not requirement.matches(response)
    )
    return not missing, missing


def _generate(
    *,
    base_url: str,
    model: str,
    prompt: str,
    timeout_seconds: int,
) -> str:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096,
                "num_predict": 512,
            },
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    return str(payload.get("response") or "").strip()


def run_cases(
    cases: Sequence[EvalCase],
    *,
    base_url: str,
    timeout_seconds: int,
) -> list[EvalResult]:
    results: list[EvalResult] = []
    for case in cases:
        started = time.perf_counter()
        try:
            response = _generate(
                base_url=base_url,
                model=case.model,
                prompt=case.prompt,
                timeout_seconds=timeout_seconds,
            )
            passed, missing = evaluate_response(case, response)
            results.append(
                EvalResult(
                    case_id=case.case_id,
                    model=case.model,
                    role=case.role,
                    passed=passed,
                    elapsed_seconds=round(time.perf_counter() - started, 2),
                    missing=missing,
                    response_preview=_one_line(response)[:220],
                )
            )
        except Exception as exc:
            results.append(
                EvalResult(
                    case_id=case.case_id,
                    model=case.model,
                    role=case.role,
                    passed=False,
                    elapsed_seconds=round(time.perf_counter() - started, 2),
                    missing=tuple(requirement.name for requirement in case.requirements),
                    response_preview="",
                    error=str(exc),
                )
            )
    return results


def render_table(results: Sequence[EvalResult]) -> str:
    headers = ("Model", "Case", "Role", "Pass", "Seconds", "Missing / Error")
    rows = [
        (
            result.model,
            result.case_id,
            result.role,
            "PASS" if result.passed else "FAIL",
            f"{result.elapsed_seconds:.2f}",
            result.error or ", ".join(result.missing) or "-",
        )
        for result in results
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    lines = [
        " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        "-+-".join("-" * width for width in widths),
    ]
    lines.extend(
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


def _select_cases(models: Iterable[str] | None) -> tuple[EvalCase, ...]:
    if not models:
        return CASES
    wanted = set(models)
    return tuple(case for case in CASES if case.model in wanted)


def _one_line(value: str) -> str:
    return " ".join(value.strip().split())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run informational structural checks against local ta-* persona models. "
            "This command never gates or submits trades."
        )
    )
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Evaluate only this model; repeat to select more than one.",
    )
    parser.add_argument("--json-output", default="")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List cases without contacting Ollama.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = _select_cases(args.models)
    if not cases:
        print("No evaluation cases matched the requested model(s).", file=sys.stderr)
        return 2

    if args.dry_run:
        for case in cases:
            requirements = ", ".join(item.name for item in case.requirements)
            print(f"{case.model}\t{case.case_id}\t{case.role}\t{requirements}")
        print(f"\n{len(cases)} cases; no inference performed.")
        return 0

    results = run_cases(
        cases,
        base_url=args.base_url,
        timeout_seconds=max(1, args.timeout_seconds),
    )
    print(render_table(results))

    model_count = len({result.model for result in results})
    passed = sum(result.passed for result in results)
    print(
        f"\nInformational result: {passed}/{len(results)} cases passed "
        f"across {model_count} persona models."
    )
    print("This result is not connected to paper-trading execution gates.")

    if args.json_output:
        output = Path(args.json_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps([asdict(result) for result in results], indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {output}")

    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
