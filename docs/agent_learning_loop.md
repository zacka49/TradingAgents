# Agent Learning Loop

This business now has a local, artifact-driven learning loop. It does not
fine-tune a model and it does not call hosted LLMs. Instead, each run produces
role-specific scorecards, and the post-market review command turns those
scorecards into compact specialist memories.

## What It Adds

- Per-run `agent_scorecards.md` beside each `company_run.json`.
- Scorecards for:
  - Market Analyst
  - News Catalyst Analyst
  - Risk Officer
  - Portfolio Manager
  - CEO Agent
  - Local AI Staff
- A post-market review pack under:
  - `results/post_market_reviews/<date>/post_market_review.md`
  - `results/post_market_reviews/<date>/post_market_review.json`
- Per-agent memory files under the configured specialist memory directory.
- Future Codex CEO briefing packs and optional local staff memos read recent
  specialist memories when they exist.

## Run After Market Close

```powershell
.\.venv\Scripts\python.exe scripts\run_post_market_review.py --date 2026-05-11 --results-dir results
```

Use `--no-memory` if you only want the review pack and do not want to append
specialist memories.

## How To Use The Review

Read the post-market review after the session and look for:

- agents scoring below 65
- repeated gaps across multiple days
- order blockers that appear too often
- candidates with weak backtest or day-trade fit evidence
- cases where the CEO accepted too much risk or blocked too much opportunity

The goal is to improve prompts, thresholds, and checklists before doing any
fine-tuning. Training should come later, after the business has enough reviewed
examples to avoid learning from noise.
