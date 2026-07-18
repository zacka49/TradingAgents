"""T4 - weekly research (Saturday).

Refreshes the strategy library, captures a fresh Technology Scout read, rolls
up the week's day-trader P&L by day, and writes one weekly review doc. This
is where the scaling ladder and strategy demotions in
docs/business_recovery_plan.md get decided once enough weeks of evidence
exist -- for now it just makes the evidence visible.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opslib import (  # noqa: E402
    ops_root,
    read_heartbeat,
    today_str,
    trading_days_in_week,
    utc_now,
    weekly_circuit_breaker_status,
    weekly_pnl_breakdown,
    write_heartbeat,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGY_SCRIPT = REPO_ROOT / "scripts" / "run_strategy_research_department.py"
CEO_SCRIPT = REPO_ROOT / "scripts" / "run_codex_ceo_company.py"
SUBPROCESS_TIMEOUT_SECONDS = 20 * 60


def _run(command: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _refresh_strategy_library() -> dict:
    code, stdout, stderr = _run(
        [
            sys.executable,
            str(STRATEGY_SCRIPT),
            "--evidence-root",
            "results",
            "--output-dir",
            "knowledge/strategy_library",
        ]
    )
    if code != 0:
        return {"ok": False, "error": stderr[-1000:]}
    try:
        return {"ok": True, "summary": json.loads(stdout)}
    except json.JSONDecodeError:
        return {"ok": True, "summary": None, "raw_stdout": stdout[-1000:]}


def _capture_tech_scout(trade_date: str) -> dict:
    code, stdout, stderr = _run(
        [sys.executable, str(CEO_SCRIPT), "--date", trade_date, "--results-dir", "results"]
    )
    if code != 0:
        return {"ok": False, "error": stderr[-1000:]}
    try:
        summary = json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": f"could not parse CEO run stdout: {stdout[-1000:]}"}

    artifact_dir = summary.get("artifact_dir")
    tech_scout_text = ""
    if artifact_dir:
        tech_scout_path = Path(artifact_dir) / "technology_scout_report.md"
        if not tech_scout_path.is_absolute():
            tech_scout_path = REPO_ROOT / tech_scout_path
        if tech_scout_path.exists():
            tech_scout_text = tech_scout_path.read_text(encoding="utf-8")

    return {"ok": True, "artifact_dir": artifact_dir, "technology_scout_report": tech_scout_text}


def _week_heartbeat_summary(week_days: list[str], results_dir: str) -> list[dict]:
    rows = []
    for day in week_days:
        row = {"date": day}
        for task in ("T1_premarket", "T2_trading_session", "T3_postmarket"):
            hb = read_heartbeat(task, day, results_dir)
            row[task] = hb["status"] if hb else "missing"
        rows.append(row)
    return rows


def _adopt_now_names(tech_scout_text: str) -> list[str]:
    names: list[str] = []
    in_section = False
    for line in tech_scout_text.splitlines():
        if line.strip() == "## Adopt Now":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("### "):
            names.append(line[4:].strip())
    return names


def build_weekly_review(
    *,
    trade_date: str,
    library_result: dict,
    tech_scout_result: dict,
    pnl_rows: list[dict],
    breaker,
    heartbeat_rows: list[dict],
) -> str:
    lines = [f"# Weekly Review - week of {breaker.week_start}", "", f"Generated: {utc_now().isoformat()}", ""]

    lines.append("## Operations")
    lines.append("| Date | T1 Pre-market | T2 Trading | T3 Post-market |")
    lines.append("| --- | --- | --- | --- |")
    for row in heartbeat_rows:
        lines.append(f"| {row['date']} | {row['T1_premarket']} | {row['T2_trading_session']} | {row['T3_postmarket']} |")
    missed = [row["date"] for row in heartbeat_rows if "missing" in row.values()]
    lines.append("")
    if missed:
        lines.append(f"Missed session(s): {', '.join(missed)}")
    else:
        lines.append("No missed scheduled sessions this week.")
    lines.append("")

    lines.append("## Weekly P&L")
    lines.append("| Date | Sessions | P&L |")
    lines.append("| --- | ---: | ---: |")
    week_total = 0.0
    for row in pnl_rows:
        lines.append(f"| {row['date']} | {row['sessions']} | ${row['pnl_usd']:+.2f} |")
        week_total += row["pnl_usd"]
    lines.append(f"| **Total** |  | **${week_total:+.2f}** |")
    lines.append("")
    lines.append(
        f"Circuit breaker: breached={breaker.breached}, cumulative={breaker.cumulative_pnl_pct}% "
        f"against a -1.5% weekly limit, baseline equity=${breaker.baseline_equity or 0:,.2f}."
    )
    lines.append("")

    lines.append("## Strategy Library")
    if library_result.get("ok") and library_result.get("summary"):
        summary = library_result["summary"]
        lines.append(f"- Approved: {', '.join(summary.get('approved_strategy_ids', [])) or 'none'}")
        lines.append(f"- Paper trade candidates: {', '.join(summary.get('paper_candidate_strategy_ids', [])) or 'none'}")
        lines.append(f"- Blocked/research-only: {', '.join(summary.get('blocked_strategy_ids', [])) or 'none'}")
    else:
        lines.append(f"- Refresh failed: {library_result.get('error', 'unknown error')}")
    lines.append("")

    lines.append("## Technology Scout - Adopt Now")
    if tech_scout_result.get("ok"):
        names = _adopt_now_names(tech_scout_result.get("technology_scout_report", ""))
        if names:
            for name in names:
                lines.append(f"- {name}")
        else:
            lines.append("- No adopt-now items captured this run.")
    else:
        lines.append(f"- Capture failed: {tech_scout_result.get('error', 'unknown error')}")
    lines.append("")

    lines.append("## Scaling Ladder Status")
    lines.append(
        "- Scale up requires >=30 closed trades, profit factor >=1.2, and no daily-loss breach "
        "in the last 10 sessions (see docs/business_recovery_plan.md). Not yet evaluated automatically; "
        "review manually until Phase 2 P&L attribution lands."
    )
    lines.append("")

    return "\n".join(lines)


def run_weekly_research(*, results_dir: str, day_trader_results_dir: str, trade_date: str) -> dict:
    from datetime import date as date_cls

    as_of = date_cls.fromisoformat(trade_date)
    week_days = trading_days_in_week(as_of)

    library_result = _refresh_strategy_library()
    tech_scout_result = _capture_tech_scout(trade_date)
    pnl_rows = weekly_pnl_breakdown(as_of=as_of, results_dir=day_trader_results_dir)
    breaker = weekly_circuit_breaker_status(as_of=as_of, results_dir=day_trader_results_dir)
    heartbeat_rows = _week_heartbeat_summary(week_days, results_dir)

    markdown = build_weekly_review(
        trade_date=trade_date,
        library_result=library_result,
        tech_scout_result=tech_scout_result,
        pnl_rows=pnl_rows,
        breaker=breaker,
        heartbeat_rows=heartbeat_rows,
    )

    output_dir = ops_root(results_dir) / "weekly_reviews"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{breaker.week_start}.md"
    output_path.write_text(markdown, encoding="utf-8")

    status = "ok" if library_result.get("ok") and tech_scout_result.get("ok") else "degraded"
    write_heartbeat(
        "T4_weekly",
        status,
        trade_date=trade_date,
        results_dir=results_dir,
        details={"weekly_review_path": str(output_path), "circuit_breaker": asdict(breaker)},
    )

    return {
        "trade_date": trade_date,
        "status": status,
        "weekly_review_path": str(output_path),
        "circuit_breaker": asdict(breaker),
        "pnl_rows": pnl_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="T4 weekly research and review.")
    parser.add_argument("--results-dir", default="results/ops")
    parser.add_argument("--day-trader-results-dir", default="results/autonomous_day_trader")
    parser.add_argument("--date", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env")
    args = build_parser().parse_args(argv)
    trade_date = args.date or today_str()

    report = run_weekly_research(
        results_dir=args.results_dir,
        day_trader_results_dir=args.day_trader_results_dir,
        trade_date=trade_date,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
