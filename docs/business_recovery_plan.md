# Business Recovery And Operating Plan

Created: 2026-07-18 (Saturday)
Owner: Human CEO (Zack)
Prepared by: freelance business analyst engagement
Status: paper-only. Nothing in this plan enables live trading.

## Purpose

Get the paper-trading business from its current state (deadlocked, zero trades
since 2026-06-04) to a state where it:

1. Runs every US market session unattended on this PC.
2. Trades only the safe profile through promoted strategies.
3. Produces evidence (P&L attribution, scorecards, fix tickets) that either
   improves the strategies or honestly demotes them.
4. Feeds the junior quant career plan (which remains business line #1).

## Root Cause Being Fixed

The firm deadlocked itself in early June:

- Four stale positions (BITO, ETHE, IBIT, NVO) blocked the day trader's
  startup flat gate (`account_not_flat_at_start`), so the only vehicle for the
  approved intraday strategies never started.
- The CEO runner that plans the liquidation was only run manually outside
  market hours, so its sell orders always hit the `market_closed` gate.
- The catalyst/news pipeline died for a month on one bad symbol (`CL=F` from
  Yahoo `relatedTickers`) because the path-safety validator aborts the whole
  run instead of skipping the symbol.
- Local Ollama staff were unreachable (HTTP 404) on 2026-06-03 and degraded to
  fallback memos silently.

None of these were strategy failures. All were operations failures.

## Operating Decisions (approved by CEO 2026-07-18)

| Decision | Value |
| --- | --- |
| Priority | Career portfolio first; trading firm is its case study |
| Stale positions | No loyalty; flatten at next market open |
| Profile | `safe` only until the learning loop proves itself |
| Upstream repo | Standalone project now; no upstream merges |
| Desks | Hiring freeze; Forex and Crypto desks mothballed |
| Machine | This PC is the whole firm; can stay on for market hours |
| Caps | Set by risk policy below, not ad hoc |

## Single-Book Rule (new)

Until further notice, only the **autonomous day trader (safe profile)**
submits paper orders. The Codex CEO runner becomes research/briefing-only
(its default dry-run mode; never pass `--submit-paper` or
`--autonomous-paper`). One order source means clean P&L attribution and no
duplicate-book risk.

## Risk Policy v1 (paper account, ~$100k equity)

Position sizing is risk-based: size derives from the distance to the stop, not
from a fixed notional wish.

| Control | Initial value | Rationale |
| --- | ---: | --- |
| Per-trade risk (entry to stop) | ~$75 (0.075% of equity) | With safe-profile stops of 1.4-2.8%, implies ~$2.7k-$5.4k notional, consistent with existing safe caps |
| Max order notional | keep safe profile (~$3k) | Secondary bound |
| Max concurrent positions | 4 | Keeps correlated intraday exposure reviewable |
| Max intraday deployment | 15% of equity | Below the current 20% until evidence accrues |
| Daily max session loss | $500 (0.5%) | Tighter than the current $750; halt + flatten on breach (mechanism exists) |
| Weekly circuit breaker | -1.5% equity on the week | Stand down until the weekly review |
| Overnight holds | none | `flatten_at_close` stays on |
| Startup flat gate | auto-resolve | `--flatten-existing-at-start` always on, so the June deadlock cannot recur |

### Scaling ladder (deterministic, no discretion)

- **Scale up** (per-trade risk to 0.10%, deployment to 20%) only when ALL hold:
  at least 30 closed trades, profit factor >= 1.2, no daily-loss breach in the
  last 10 sessions.
- **Scale down** (halve per-trade risk) automatically on: any daily-loss
  breach, or rolling-20-trade profit factor < 0.9.
- A strategy that stays below profit factor 1.0 after 40 closed trades goes
  back to the Strategy Research Department as `paper_watchlist` (demotion path
  already exists).

## Phases

### Phase 0 - Unblock (this weekend, 18-19 Jul)

| # | Task | Owner | Acceptance |
| --- | --- | --- | --- |
| 0.1 | Fix `CL=F` catalyst crash: invalid symbols are skipped, not fatal, at all four `_clean_symbols`-style call sites; add regression tests | Analyst | Full test suite passes; a synthetic `CL=F` in `relatedTickers` no longer kills catalyst research |
| 0.2 | Ollama health check at run startup: ping the server, log model used, fall back loudly (memo marked DEGRADED) | Analyst | Health status appears in run artifacts |
| 0.3 | Refresh strategy library (stale since 04 Jun): `run_strategy_research_department.py` | Analyst | New `knowledge/strategy_library/` artifacts dated this weekend |
| 0.4 | Write incident postmortem doc (also a career portfolio artifact) | Analyst | `docs/incident_postmortem_stale_book_deadlock.md` |

### Phase 1 - Scheduler / operations layer (weekend + Monday)

Windows Task Scheduler tasks, all launching thin PowerShell wrappers in
`scripts/ops/` that log to `results/ops/`. Times are UK local with generous
margins; the scripts themselves wait on the **Alpaca trading clock**
(`--max-wait-open-seconds`), so UK/US daylight-saving drift cannot misfire a
session.

| Task | Schedule (UK) | Command (essence) |
| --- | --- | --- |
| T1 Pre-market prep | Mon-Fri 13:45 | preflight checks (Alpaca reachable, data fresh, Ollama up, disk space); strategy library freshness check |
| T2 Trading session | Mon-Fri 14:20 | `run_autonomous_day_trader.py --strategy safe --run-until-close --flatten-existing-at-start` + risk-policy caps |
| T3 Post-market review | Mon-Fri 21:15 | `run_post_market_review.py` + CEO briefing (dry-run) + scorecards + daily digest file |
| T4 Weekly research | Sat 10:00 | strategy research department refresh, tech scout, P&L attribution rollup, weekly review doc |

Additional ops hardening:

- **Heartbeat**: every task writes `results/ops/heartbeat/<task>_<date>.json`;
  T3 flags any missed heartbeat in the daily digest.
- **Daily digest**: one markdown file per day answering: did we run, what
  traded, P&L, breaches, errors, scorecard grades, open fix tickets. This is
  the only thing the CEO needs to read daily (~2 minutes).
- **Stop control**: `request_day_trader_stop.py` remains the manual kill
  switch; document it in the digest header.

Acceptance for Phase 1: Monday 20 Jul session starts unattended at the open,
flattens the four stale positions first, trades (or correctly declines to
trade) the safe profile, flattens at close, and produces a digest.

### Phase 2 - Close the learning loop (week of 20 Jul)

| # | Task | Acceptance |
| --- | --- | --- |
| 2.1 | Maintenance engineer: deterministic post-run step that converts any run error or scorecard grade below C into a fix ticket in `results/ops/fix_tickets/` | June-style silent failures become visible tickets |
| 2.2 | P&L attribution by strategy/symbol/session appended to a rolling CSV | Weekly review can say which strategy earned or lost |
| 2.3 | Supervised week: CEO skims the daily digest each evening | Five sessions of artifacts reviewed |

This week is also **career-plan Week 7** (strategy audit). The audit target is
`opening_range_breakout_15m`, written as
`docs/strategy_audit_opening_range_breakout.md` using the library backtest
plus the first live paper sessions. One piece of work, two business lines.

### Phase 3 - Unattended operation and evidence (weeks of 27 Jul - 10 Aug)

- Run unattended; CEO reads digests only.
- Career-plan Week 8 (costs/slippage robustness) doubles as the firm's
  slippage audit: compare assumed vs. realized fill quality from Alpaca paper
  fills; feed corrections into the risk policy caps.
- Apply the scaling ladder strictly as trades accumulate.
- Weekly review (T4 output) decides per strategy: continue / adjust / demote,
  using the promotion stages that already exist.

### Phase 4 - Only if evidence supports it (mid-Aug onward)

- Walk-forward promotion job (expansion plan item) so promotion evidence stops
  being a single frozen backtest.
- A/B: safe profile with vs. without catalyst-queue input, measured by P&L
  attribution, not vibes.
- Revisit mothballed desks only if the equities book is demonstrably healthy.

Explicitly out of scope: live trading, new desks, new agent roles, crypto/forex
adapters, hosted LLM spend.

## Definitions (so "running" and "profitable" are testable)

- **Running**: 5 consecutive scheduled sessions executed unattended with
  complete artifacts and zero manual intervention.
- **Profitable (paper)**: rolling 4-week net P&L > 0 after realized paper
  costs, profit factor >= 1.2 across >= 40 closed trades, no daily-loss
  breaches. Anything less is "collecting evidence", and saying so honestly is
  itself the product - this firm's real output is a documented, disciplined
  evidence machine.

Expectation management: the approved strategies' backtest edge is modest
(ORB 15m: +5.36% over 371 trades, PF 1.46; momentum breakout: +2.58%, PF
1.70). A realistic good outcome for August is a small positive P&L with clean
risk behavior and a defensible audit trail. That outcome is worth more to the
career plan than a lucky big number.

## CEO Time Budget

- Daily: read the digest (~2 minutes), nothing else required.
- Weekly: 30-60 minutes on the T4 weekly review + career-plan deliverable.
- The analyst (Claude) performs all builds, fixes, and reviews on request;
  "set up builds whenever" is the working mode.
