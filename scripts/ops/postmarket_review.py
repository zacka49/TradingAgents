"""T3 - post-market review and daily digest.

Runs a research-only CEO briefing (no --submit-paper, no --autonomous-paper --
the single-book rule keeps order submission inside T2 alone), scores the
day's runs with the existing post-market review, then writes one markdown
digest the CEO can read in about two minutes instead of opening run
artifacts by hand.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from digest import build_daily_digest, gather_daily_digest_inputs, write_daily_digest  # noqa: E402
from fix_tickets import generate_fix_tickets  # noqa: E402
from opslib import read_heartbeat, today_str, write_heartbeat  # noqa: E402
from pnl_attribution import run_pnl_attribution  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CEO_SCRIPT = REPO_ROOT / "scripts" / "run_codex_ceo_company.py"
POST_MARKET_SCRIPT = REPO_ROOT / "scripts" / "run_post_market_review.py"
SUBPROCESS_TIMEOUT_SECONDS = 20 * 60


def _run_json_subprocess(command: list[str]) -> tuple[dict | None, str | None]:
    try:
        result = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        return None, f"timed out after {exc.timeout}s"

    if result.returncode != 0:
        return None, f"exit {result.returncode}: {result.stderr[-1000:]}"

    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return None, f"could not parse JSON stdout: {result.stdout[-1000:]}"


def _merge_review_detail(post_market_review: dict) -> dict:
    """write_post_market_review's CLI summary only has paths, not the scorecards
    themselves; read review_json to get the detail the digest table needs."""
    review_json_path = post_market_review.get("review_json")
    if not review_json_path:
        return post_market_review
    path = Path(review_json_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        return post_market_review
    try:
        detail = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return post_market_review
    merged = dict(post_market_review)
    merged.update(detail)
    return merged


def run_postmarket_review(
    *, results_dir: str, day_trader_results_dir: str = "results/autonomous_day_trader", trade_date: str
) -> dict:
    ceo_summary, ceo_error = _run_json_subprocess(
        [
            sys.executable,
            str(CEO_SCRIPT),
            "--date",
            trade_date,
            "--results-dir",
            "results",
        ]
    )

    post_market_review, post_market_error = _run_json_subprocess(
        [
            sys.executable,
            str(POST_MARKET_SCRIPT),
            "--date",
            trade_date,
            "--results-dir",
            "results",
        ]
    )
    if post_market_review and not post_market_error:
        post_market_review = _merge_review_detail(post_market_review)

    t1_heartbeat = read_heartbeat("T1_premarket", trade_date, results_dir)
    t2_heartbeat = read_heartbeat("T2_trading_session", trade_date, results_dir)
    t2_details = (t2_heartbeat or {}).get("details", {})

    generate_fix_tickets(
        ops_results_dir=results_dir,
        trade_date=trade_date,
        post_market_review=post_market_review,
        ceo_error=ceo_error,
        post_market_error=post_market_error,
        t1_status=(t1_heartbeat or {}).get("status"),
        t2_status=(t2_heartbeat or {}).get("status"),
        t2_error_detail=t2_details.get("stderr_tail"),
    )

    pnl_report = run_pnl_attribution(
        trade_date=trade_date,
        day_trader_results_dir=day_trader_results_dir,
        ops_results_dir=results_dir,
    )

    inputs = gather_daily_digest_inputs(
        trade_date=trade_date,
        ops_results_dir=results_dir,
        day_trader_results_dir=day_trader_results_dir,
        ceo_summary=ceo_summary,
        ceo_error=ceo_error,
        post_market_review=post_market_review,
        post_market_error=post_market_error,
        pnl_attribution=pnl_report,
    )
    md_path, json_path = write_daily_digest(inputs, ops_results_dir=results_dir)

    status = "ok" if not (ceo_error or post_market_error) else "degraded"
    write_heartbeat(
        "T3_postmarket",
        status,
        trade_date=trade_date,
        results_dir=results_dir,
        details={
            "ceo_error": ceo_error,
            "post_market_error": post_market_error,
            "open_fix_tickets": len(inputs.open_fix_tickets),
        },
    )

    return {
        "trade_date": trade_date,
        "status": status,
        "digest_markdown": str(md_path),
        "digest_json": str(json_path),
        "ceo_error": ceo_error,
        "post_market_error": post_market_error,
        "open_fix_tickets": len(inputs.open_fix_tickets),
        "pnl_attribution": pnl_report,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="T3 post-market review and daily digest.")
    parser.add_argument("--results-dir", default="results/ops")
    parser.add_argument("--day-trader-results-dir", default="results/autonomous_day_trader")
    parser.add_argument("--date", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env")
    args = build_parser().parse_args(argv)
    trade_date = args.date or today_str()

    report = run_postmarket_review(
        results_dir=args.results_dir,
        day_trader_results_dir=args.day_trader_results_dir,
        trade_date=trade_date,
    )
    print(json.dumps(report, indent=2))
    print(f"Digest written: {report['digest_markdown']}", file=sys.stderr)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
