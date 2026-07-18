# Strategy Audit: Opening Range Breakout (15m)

Author: business analyst engagement / junior quant project plan, Week 7
Date: 2026-07-18
Strategy ID: `opening_range_breakout_15m`
Status at time of audit: `approved_paper_strategy` (per `knowledge/strategy_library/strategy_research_report.md`)

This is a strategy-research-discipline exercise, not investment advice, and
concerns a paper-only trading system. It doubles as Week 7 of
`docs/junior_quant_project_plan.md` and as due diligence for
`docs/business_recovery_plan.md`.

## Hypothesis, In Plain English

When a stock breaks above its first-15-minutes trading range on above-average
volume while trading above the intraday VWAP, that breakout tends to continue
for the rest of the session often enough, and by enough, to be worth taking
with a tight stop. The strategy is a same-day, long-only, single-entry
momentum-confirmation trade: it does not predict direction from nothing, it
waits for the market to show its hand in the first few minutes and then
follows.

## Rules

Source: `scripts/backtest_day_trading_strategies.py::_opening_range_breakout`
(the backtest logic) and `tradingagents/company/day_trading_strategy.py`
(the live classifier used by the day trader).

- **Universe (backtest)**: NVDA, INTC, AMD, MU, PLTR, TSLA, SMCI, COIN, MSTR,
  HOOD, SOFI, QQQ, SPY -- 13 liquid large-cap tech/semi/crypto-adjacent names
  plus two index ETFs.
- **Opening range**: the high and low of the first three 5-minute bars
  (effectively the first 15 minutes of the session).
- **Entry trigger**: at any bar after the opening range, enter long when all
  three hold simultaneously: close > opening-range high, volume >= 1.15x the
  trailing 20-bar average volume, and close > VWAP.
- **Position sizing (backtest)**: one full-notional entry per ticker per day;
  no pyramiding.
- **Stop loss**: `entry * (1 - risk_pct)`, where `risk_pct` is the distance
  from entry to the opening-range low, clamped to 0.35%-1.5%.
- **Take profit**: `entry * (1 + risk_pct * 2)` -- a fixed 2:1 reward-to-risk
  target relative to the stop distance.
- **Exit**: whichever of stop, take-profit, or the 15:55 ET session close
  comes first. No overnight holding under any circumstance.
- **Holding period**: intraday only, same session, typically minutes to a
  few hours.
- **Cost model (backtest)**: 2 bps per side (4 bps round-trip), applied
  uniformly regardless of the actual traded symbol's spread.
- **Benchmark**: buy-and-hold on the same ticker over the same window (per
  the daily CEO briefing's Backtest Lab table); this audit also compares
  against a naive equal-weight portfolio of the 13-ticker universe.

## Backtest Re-Run / Inspection

The promotion-driving evidence is
`results/company_validation/2026-06-04/intraday_strategy_backtest/`
(generated 2026-06-04T09:23:22Z, a 60-day/5-minute yfinance window). This is
the file the Strategy Promotion Committee actually used: the promotion code
(`tradingagents/company/strategy_research_department.py::_apply_intraday_backtest_evidence`)
sorts every `strategy_aggregate.csv` under the evidence root by file
modification time and uses **only the single most recent one**, discarding
all others. As of this audit, three independent backtest runs of the same
strategy over the same universe exist on disk; only the newest was ever
consulted for the live promotion decision.

### Metrics (aggregate, from the promotion-driving run)

| Metric | Value |
| --- | ---: |
| Trades | 371 |
| Tickers | 13 |
| Trading days covered | 58 |
| Total return (compounded, pooled) | 5.36% |
| Profit factor | 1.46 |
| Max drawdown | 4.70% |
| Win rate (pooled, trade-weighted) | 52.56% |
| Win rate (per-ticker average, as reported) | 51.81% |
| Average win | +1.23% |
| Average loss | -0.97% |
| Exit via stop-loss | 95 trades (25.6%) |
| Exit via take-profit | 44 trades (11.9%) |
| Exit via end-of-day close | 232 trades (62.5%) |
| Turnover | 100% same-day round-trip on every trade; no overnight exposure |
| Sharpe ratio | Not computed -- see Limitations |

Sharpe ratio was not computed by the existing pipeline, and this audit does
not fabricate one: trade returns are ragged in time (0-13 trades/day across
13 tickers, not one evenly-spaced return series), so a naive per-trade Sharpe
would silently misstate the actual time-weighted volatility. A defensible
Sharpe needs a proper daily equity curve, which would require simulating
capital allocation across simultaneous positions -- a reasonable next build,
not something to approximate here.

### Per-Ticker Dispersion (same run)

| Ticker | Trades | Total Return | Profit Factor | Max Drawdown |
| --- | ---: | ---: | ---: | ---: |
| SMCI | 28 | 21.75% | 2.41 | 3.49% |
| AMD | 32 | 19.22% | 2.60 | 3.06% |
| COIN | 25 | 10.45% | 1.71 | 5.18% |
| SOFI | 19 | 7.23% | 1.76 | 3.32% |
| INTC | 25 | 6.09% | 1.47 | 3.30% |
| QQQ | 38 | 2.82% | 1.44 | 2.48% |
| SPY | 37 | 2.08% | 1.46 | 1.00% |
| PLTR | 24 | 1.09% | 1.12 | 4.03% |
| HOOD | 27 | 0.93% | 1.07 | 4.60% |
| TSLA | 28 | 0.92% | 1.08 | 5.63% |
| MSTR | 27 | 1.49% | 1.09 | 7.99% |
| NVDA | 32 | -2.37% | 0.86 | 7.60% |
| MU | 29 | -2.07% | 0.92 | 9.44% |

## Ways This Backtest Could Be Misleading

1. **Single-snapshot promotion evidence, no stability check.** Two other
   backtests of the identical strategy and universe exist
   (`results/research/strategy_backtests/20260505T215251Z/` and
   `.../20260510T192516Z/`), generated 4 and 9 weeks apart from the
   promotion-driving run respectively. Their aggregate metrics for this same
   strategy: 393 trades / 1.28% return / PF 1.18 / 6.02% drawdown (05-05
   run), and 397 trades / 2.70% return / PF 1.28 / 5.51% drawdown (05-10
   run). Applying the promotion engine's own rule (`trades>=100 and
   total_return>1.0 and profit_factor>=1.15 and max_drawdown<=6.0`) to the
   05-05 run specifically: it fails on drawdown alone (6.02% > 6.0% cap) --
   this strategy would **not** have been promoted from that window's
   evidence. The strategy is currently approved because the most recent scan
   happened to land on a favorable 60-day window, not because performance has
   been shown stable across windows.
2. **Concentration, hidden by the aggregate.** Two of thirteen tickers
   (SMCI, AMD) generate the large majority of the pooled return; two tickers
   (NVDA, MU) are net losers with profit factors below 1.0. The 5.36%
   "aggregate return" and 1.46 "aggregate profit factor" describe a
   portfolio outcome, not a typical single-ticker outcome, and the actual
   live day trader does not allocate capital evenly across all 13 backtest
   tickers -- its allocation depends on which symbols the daily screener
   surfaces, which does not guarantee exposure to the strategy's actual
   winners.
3. **Aggregation method understates dispersion further.** The reported
   `avg_win_rate_pct` and `avg_profit_factor` are unweighted averages across
   13 tickers, so a ticker with 19 trades (SOFI) counts equally to one with
   38 (SPY, QQQ) in the "average." The pooled, trade-weighted win rate
   (52.56%) happens to sit close to the reported average (51.81%) in this
   case, but the methodology does not guarantee that in general.
4. **The backtest's exit model is simpler than the live trader's.** 62.5%
   of backtested trades exit at the 15:55 ET close, not via the strategy's
   own stop or take-profit -- meaning most realized returns depend on
   wherever price happened to sit at end of day, not on the risk management
   the strategy is nominally built around. Separately, the live day trader
   (`tradingagents/company/autonomous_ceo.py`) layers five additional exit
   policies on top of bracket orders -- profit-giveback, momentum-decay,
   stale-loser, early-adverse, and unprotected-position exits -- none of
   which this backtest simulates. Live behavior will diverge from backtested
   behavior in ways this evidence does not capture.
5. **Universe mismatch against actual paper holdings.** The backtest
   universe is mega-cap tech, semiconductors, and crypto-adjacent equities.
   The paper account's actual historical holdings during the period covered
   by this review (BITO, ETHE, IBIT, NVO) share zero tickers with the
   backtest universe. The promotion evidence has never been tested against
   the assets the account has actually held.
6. **Flat cost assumption.** 2 bps/side slippage is applied uniformly. It
   does not vary by the actual bid/ask spread of the traded symbol at the
   time, which the live day trader does check in real time via order-flow
   enrichment -- so the backtest cost assumption is a simplification in both
   directions (too generous for illiquid names, possibly too conservative
   for the most liquid ones).
7. **No train/test split.** The same 60-day window both exposes the pattern
   (entry thresholds like `volume_ratio >= 1.15`, the 2:1 reward:risk ratio,
   the 0.35%-1.5% stop clamp look like reasonable, round, hand-set values
   rather than fitted ones, which is a mitigating factor) and evaluates it.
   There is no held-out period, so window-specific regime effects (a
   volatile stretch that happened to favor breakout continuation) cannot be
   ruled out from this evidence alone.

## Recommendations

- Change the promotion engine to require evidence from at least two or three
  independent backtest windows to agree (not just the most recently
  generated file) before granting `approved_paper_strategy`. This is a
  change to `_apply_intraday_backtest_evidence` in
  `tradingagents/company/strategy_research_department.py`, not the ops
  layer, and should be scoped as its own deliberate piece of work given it
  changes trading-relevant logic.
- Weight aggregate metrics by trade count, not by ticker.
- Extend the Backtest Lab to simulate the live day trader's full exit-policy
  set, not just stop/take-profit/EOD, so backtested and live behavior are
  comparable.
- Either restrict the backtest universe to what the live screener actually
  tends to surface, or accept that the promotion evidence is a plausibility
  check on the *rule*, not a forecast of return on the *specific assets
  traded* -- and say so explicitly in the strategy library output.
- Add a walk-forward or simple train/test split before the next promotion
  cycle (this is exactly the Phase 4 item already flagged in
  `docs/business_recovery_plan.md` as "only if evidence supports it" -- this
  audit is evidence that it should move up the priority list).

## Limitations Of This Audit

This audit inspects existing backtest artifacts rather than re-running the
backtest from scratch (the underlying yfinance data window has since rolled
forward, so an exact re-run today would not reproduce these exact numbers --
that instability is itself finding #1 above). No live paper-trading results
for this strategy exist yet to compare against; that comparison becomes
possible once the scheduled operations layer (`docs/business_recovery_plan.md`
Phase 1) accumulates real sessions, and should be revisited in the Phase 2
weekly review.
