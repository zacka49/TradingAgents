# Incident Postmortem: Six-Week Trading Deadlock

Status: resolved 2026-07-18
Severity: total loss of trading function (zero paper trades for six weeks);
no capital-loss impact (paper account only)
Author: business analyst engagement, freelance review

## Summary

From 2026-06-04 to 2026-07-08 the business submitted zero paper orders. Every
Codex CEO run in that window ended `blocked_trade` (37 runs) or `no_trade`
(17 runs). The cause was not a strategy failure or a market condition. It was
a self-inflicted deadlock between two independent safety gates, compounded by
three smaller operational failures that made the deadlock invisible.

## Timeline

- **2026-05-xx**: normal paper trading; account accumulates four positions
  (BITO, ETHE, IBIT, NVO) via earlier day-trader sessions.
- **2026-06-03**: control room records a Risk Office memo about the startup
  flat gate, noting the account is not flat (5 open positions at that point)
  and that Ollama returned `HTTPError: HTTP Error 404: Not Found`. No action
  taken; the memo itself was a graceful fallback template, not a live model
  response.
- **2026-06-04**: last successful strategy library refresh before this
  incident review. Last commit before a long gap in the run history.
- **2026-06-04 to 2026-07-08**: `run_autonomous_day_trader.py` sessions
  observed in `results/autonomous_day_trader/session_reports/` consistently
  show `cycles_completed: 0` and the flatten result
  `event: not_attempted, reason: no_flatten_requested` -- the day trader
  refused to start because the account was not flat, and nobody passed
  `--flatten-existing-at-start`.
- Separately, `results/codex_ceo_company/**/ceo_briefing_pack.md` for this
  window shows repeated `Proposed Paper Orders` to sell the same four
  positions, all with `Status: market_closed` -- the CEO runner that could
  have flattened the book was only ever invoked manually, outside market
  hours.
- **2026-07-08**: last observed run before this review began; catalyst
  research shows `Status: error`, `Errors: ValueError: ticker contains
  characters not allowed in a filesystem path: 'CL=F'`.
- **2026-07-18**: business review begins; root cause identified; fixes
  applied same day.

## Root Cause

Two gates, each individually reasonable, combined into a deadlock:

1. The autonomous day trader's **startup flat gate**
   (`tradingagents/company/autonomous_ceo.py`) refuses to run trading cycles
   while the account holds positions from a prior session, unless
   `--flatten-existing-at-start` is passed. This is the only vehicle that
   runs the two approved intraday strategies (`opening_range_breakout_15m`,
   `momentum_breakout`), so nothing traded while positions were open.
2. The Codex CEO runner's own liquidation plan for those same positions is
   gated by `evaluate_order_policy` (`tradingagents/execution/risk_policy.py`)
   requiring `market_open`. Every run that could have sold the stale
   positions was executed manually, outside market hours, so the sell orders
   were always rejected with `market_closed`.

Neither gate was wrong on its own. The failure was structural: there was no
scheduled process running the CEO cycle *during* market hours, and the day
trader was never invoked with the flag that lets it clear its own way. A
human had to either (a) run the day trader with
`--flatten-existing-at-start`, or (b) run the CEO liquidation plan while the
market was open, and neither happened for six weeks because all runs were
manual and the operator was away.

## Contributing Failures

These did not cause the deadlock, but they hid it and degraded the business
while it was live:

1. **No scheduler existed.** A `Get-ScheduledTask` audit of this machine on
   2026-07-18 found zero scheduled tasks for this project. Every run in the
   incident window was triggered by hand, at inconsistent times, mostly
   outside market hours.
2. **Catalyst research crashed on one bad symbol.** Yahoo `relatedTickers`
   can include futures symbols such as `CL=F`. `safe_ticker_component`
   (`tradingagents/dataflows/utils.py`) correctly rejects such values for
   path-safety reasons, but `_clean_symbols`-style callers in
   `news_politics_discovery.py`, `news_reversion_desk.py`,
   `codex_ceo_company.py`, and `autonomous_discovery.py` let that
   `ValueError` propagate and abort the entire catalyst run instead of
   skipping the one symbol. The News Catalyst Analyst scored F for roughly a
   month as a result.
3. **Ollama was unreachable and degraded silently.** The 2026-06-03
   control-room memo shows a 404 from the local model server. Nothing
   surfaced this outside that one memo; the CEO briefing pack does not
   distinguish "Ollama down" from "Ollama fine, model just had little to
   say."
4. **The Python package's editable install pointed at a stale path.**
   Discovered 2026-07-18 while building the fix for this incident: the repo
   had been moved from `D:\AI projects\Git repo for inspection\TradingAgents`
   to its current location, but `pip install -e .` was never rerun. Every
   directly-invoked script (`python scripts/run_codex_ceo_company.py ...`,
   exactly as documented in `docs/codex_ceo_company.md`) failed with
   `ModuleNotFoundError: No module named 'tradingagents'` unless run through
   pytest or `python -c`, which use different import-path resolution. This
   would independently have made the deadlock harder to fix by hand and
   would have silently broken every scheduled task this plan introduces.

## What Actually Fixed It

1. Reinstalled the package in editable mode from the current path
   (`pip install -e . --no-deps`), restoring direct script invocation.
2. Fixed the catalyst crash: added `sanitize_ticker_component` (a
   non-raising variant of `safe_ticker_component`) in
   `tradingagents/dataflows/utils.py` and switched the six ingestion call
   sites to use it. Bad symbols are now skipped, not fatal. Verified live:
   the News Catalyst Analyst scored 80 (B) on the first run after the fix,
   versus 30 (F) beforehand.
3. Refreshed the strategy library (was six weeks stale).
4. Built a scheduled operations layer (`scripts/ops/`, see
   `docs/business_recovery_plan.md` Phase 1) so the CEO cycle and day trader
   run automatically during market hours instead of depending on a human
   remembering to do it manually at the right time. The trading session
   script (T2) always launches with `--flatten-existing-at-start`, so this
   specific deadlock cannot recur -- a non-flat account is now something the
   system clears itself instead of something that silently blocks it forever.
5. Added an explicit Ollama health check (`scripts/ops/check_ollama_health.py`)
   that records reachability and model readiness on every pre-market run,
   so a repeat of the June 404 shows up in the daily digest instead of only
   in a buried department-task memo.

## Prevention

- **Single-book rule**: only the scheduled day trader (T2) submits orders;
  the CEO runner stays research/briefing-only. This removes the
  market-hours/manual-run mismatch that caused half of this incident.
- **Daily digest**: T3 now produces one markdown file per day that states
  whether each scheduled task ran, whether the account is flat, and any
  scorecard grade below C. A repeat of "quietly broken for a month" should
  now be visible within one day, not six weeks.
- **Ingestion boundary rule**: any function that turns an external feed
  value (news API, discovery API) into a path component or strategy input
  must use the non-raising `sanitize_ticker_component`, not the raising
  `safe_ticker_component`. The raising variant stays reserved for path
  construction sites where an invalid value indicates a bug or an attack,
  not a routine data-quality issue.
- **Environment check**: after any repo move, rerun `pip install -e .` before
  relying on directly-invoked scripts; pytest and `python -c` import
  resolution can mask a stale editable install.
