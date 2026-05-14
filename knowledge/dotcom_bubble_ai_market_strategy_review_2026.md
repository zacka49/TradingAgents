# Dot-Com Bubble Research And Day-Trader Strategy Review

Date: 2026-05-14

Scope: review the current TradingAgents paper-trading strategy features, especially the new stop-loss and exit behavior, then use dot-com bubble economic lessons to guide the business and trading roadmap. This is research and product/risk analysis, not financial advice.

## Executive View

The stop-loss change is moving in the right direction, but it is not yet "optimal." The current system has two layers of protection:

- Bracket stops on entry, generated from `MarketCandidate.stop_loss_pct`.
- A live risk monitor that exits stale losers, profit givebacks, unprotected positions, and momentum-decay trades.

The live monitor is currently the real stop. Day 5 evidence shows the bot cutting losers around the 0.75% stale-loser threshold, while the average Day 5 risky bracket stop in saved artifacts was about 2.5%. That means the bracket stop is more like a disaster stop, not the practical stop-loss. That is acceptable if intentional, but the code and reporting should make that explicit.

The best next improvement is not simply tightening the stop again. It is measuring expectancy by strategy, symbol, time-of-day, and exit reason, then tuning thresholds from replay and forward paper evidence.

## Repo Findings

Relevant files:

- `tradingagents/company/strategy_profiles.py`
- `tradingagents/company/day_trading_strategy.py`
- `tradingagents/company/codex_ceo_company.py`
- `tradingagents/company/autonomous_ceo.py`
- `run_day_trader_bot.py`
- `scripts/run_autonomous_day_trader.py`
- `results/autonomous_day_trader/day_summaries/*.md`
- `results/autonomous_day_trader/backtests/exit_policy_replay_2026-05-14.md`

### What Looks Strong

1. Strategy classification is explicit.

   The intraday playbook now separates `opening_range_breakout_15m`, `momentum_breakout`, `relative_strength_continuation`, and watch-only states. That is much healthier than trading one generic score.

2. The profile gates are much better than the early runs.

   Safe has higher confidence, lower active position count, stricter risk flags, fit-score requirements, and tighter profit targets. Risky is allowed to trade more, but still has max active positions, news-risk blocking, and stale-loser trimming.

3. Active-position caps fixed a real failure mode.

   Day 2 reached 13 open positions and around 41% gross exposure. Later summaries show the caps doing useful work, especially on Day 3 and Day 5.

4. Risk exits are practical rather than theoretical.

   `autonomous_ceo.py` now handles:
   - stale losers
   - profit giveback
   - momentum decay
   - unprotected positions
   - cooldowns after failed/stalled exits
   - session loss/drawdown halt

5. The stop-change has some evidence behind it.

   The local replay backtest covered 41 symbol episodes and estimated +$90.07 net P/L improvement for the new policy. It changed 25 cases, with 13 positive and 12 negative, so the signal is useful but not overwhelming.

### What Does Not Look Optimal Yet

1. Bracket stop and live stop are misaligned.

   Day 5 artifact aggregation:

   | Profile | Buy plans | Avg bracket stop | Avg take profit | Avg notional |
   | --- | ---: | ---: | ---: | ---: |
   | risky | 12 | 2.50% | 2.76% | ~$2,862 |
   | safe | 2 | 1.20% | 1.80% | ~$2,321 |

   But the live stale-loser exit cuts around 0.75% by default. If the monitor is the intended stop, the bracket stop should be labeled as a backup stop and the trade plan should show both: "monitor stop" and "catastrophic bracket stop."

2. Risk/reward is thin on risky entries.

   Risky can have stops nearly equal to, or wider than, take-profit distance. A 2.5% stop and 2.5% to 2.8% target needs a high win rate after slippage. In a chop regime, that becomes churn.

3. Momentum decay can cut slow builders.

   The replay shows benefits, but the largest estimated costs included XLV, IBIT, PLTR, and TSLA cases where an earlier exit missed later improvement. That means `momentum_decay` should become conditional on market context, not just time and gain.

4. The launcher defaults diverge.

   `run_day_trader_bot.py` defaults to tighter profit protection:
   - min gain 0.50%
   - max giveback 0.45%
   - giveback fraction 0.40

   `scripts/run_autonomous_day_trader.py` still defaults to the older:
   - min gain 0.75%
   - max giveback 0.60%
   - giveback fraction 0.50

   That can create different behavior depending on which entrypoint is used. It should be harmonized or clearly documented.

5. The system still needs a proper expectancy dashboard.

   The code has event logs and summaries, but the next decision should be based on:
   - win rate by strategy
   - average win/loss by strategy
   - exit reason P/L
   - time-in-trade distribution
   - re-entry after cooldown outcome
   - slippage versus planned price
   - same-symbol churn

## Strategy Feature Assessment

Current features are directionally good:

- momentum windows: 1m, 5m, 15m, session return
- volume ratio
- volatility
- spread and stale-trade flags
- opening-range breakout
- risk flags from news and order flow
- day-trade fit score
- backtest gate/min closed trades
- max active positions
- stale-loser trim
- profit-giveback monitor
- unprotected-position monitor
- session halt

Missing or underdeveloped features:

1. Market regime filter

   Add QQQ/SPY/SMH trend, VIX, 10-year yield movement, dollar index, and market breadth. In a dot-com-like melt-up, single-name momentum can work until it suddenly does not; regime should decide whether the bot is in "press", "normal", "defensive", or "capital preservation" mode.

2. Breadth and concentration

   Track whether gains are broad or concentrated in a few AI/mega-cap names. Narrow leadership is a warning that momentum entries need tighter size and faster confirmation.

3. AI sentiment and capex narrative

   Current market risk is heavily tied to AI expectations. Add a daily/weekly AI-sentiment feature from headlines, mega-cap earnings guidance, hyperscaler capex commentary, semiconductor lead times, and data-center power constraints.

4. Time-of-day behavior

   Opening-range breakouts, midday continuation, and late-day squeezes are different games. Stop and take-profit thresholds should be tuned per time bucket.

5. Post-exit re-entry quality

   Cooldowns are good. Next step: learn whether 30 minutes is too short or too long by exit reason. A stale-loser exit should likely block longer than a profit-giveback exit.

6. Slippage and spread realized cost

   A 0.75% stop can be sensible only if actual slippage is small. Every live/paper fill should store planned price, submitted price, fill price, spread, and latency.

## Dot-Com Bubble Research

### What Happened

The late-1990s internet wave was a real technological revolution wrapped in extreme financing conditions. The internet was not fake. The prices, business models, and capital discipline around many companies were the fragile part.

Key sequence:

- 1995-2000: internet adoption and public-market enthusiasm pushed Nasdaq valuations dramatically higher.
- 1999-2000: IPO markets became speculative. Loughran and Ritter found average first-day IPO returns jumped to 65% in the 1999-2000 internet bubble years, versus about 15% in 1990-1998.
- May 16, 2000: the Fed raised the federal funds target by 50 bps to 6.5%, citing demand running ahead of supply and inflation risks.
- March 2001: NBER later dated the business-cycle peak to March 2001, so the market peak came before the wider recession.
- October 2002: Nasdaq was down roughly 78% from peak.

Sources:

- Federal Reserve May 16, 2000 FOMC release: https://www.federalreserve.gov/boarddocs/press/general/2000/20000516/default.htm
- NBER, business-cycle peak of March 2001: https://www.nber.org/reporter/fall-2001/business-cycle-peak-march-2001
- NBER, Ofek and Richardson, "DotCom Mania": https://www.nber.org/papers/w8630
- Loughran and Ritter IPO underpricing summary: https://ideas.repec.org/a/fma/fmanag/loughranritter04.html

### Economic Lessons

1. Bubbles can form around real technology.

   The internet became enormous. That did not save weak companies with bad unit economics, no durable distribution, and constant financing needs.

2. Liquidity turns before narratives do.

   The story can still sound right while funding conditions are already changing. The Fed tightening cycle in 1999-2000 made long-duration promises more fragile.

3. Public-market access can hide weak economics.

   The IPO boom rewarded companies for being in the right category. Once financing windows shut, burn rate and cash runway became existential.

4. Market breaks precede economic recognition.

   The Nasdaq peak came in March 2000. The recession was dated to March 2001. Waiting for recession confirmation is too late for trading risk control.

5. Shorting mania is not simple.

   NBER's dot-com research highlights short-sale constraints and optimistic-investor dominance. That means a bubble can go further than fundamentals suggest, then fall quickly when sellers arrive.

6. The survivors were not the loudest.

   Survivors generally had real demand, operating discipline, distribution, balance-sheet resilience, and the ability to buy or outlast weaker peers.

## Current-Market Parallel: AI Cycle In 2026

As of May 14, 2026, current conditions do have dot-com echoes:

- AP reported the S&P 500 at a record close of 7,501.24 and the Nasdaq at a record 26,635.22, with Nasdaq up 14.6% year to date.
- The Fed's November 2025 Financial Stability Report flagged that a turn in AI sentiment could trigger a correction in risk assets.
- The Fed also noted S&P 500 P/E ratios were near the high end of the historical range.
- State Street/FactSet reported that Magnificent Seven stocks contributed 61% of Q1 S&P 500 earnings growth and information technology was about 36% of the S&P 500.
- NVIDIA reported fiscal 2026 revenue of $215.9 billion, up 65%, and Q4 data-center revenue of $62.3 billion, up 75% year over year.

Sources:

- AP market close, May 14, 2026: https://apnews.com/article/wall-street-stocks-dow-nasdaq-d3ef3c2cfc7ae85a9c9f7b3d42b20a2e
- Federal Reserve November 2025 Financial Stability Report overview: https://www.federalreserve.gov/publications/november-2025-financial-stability-report-overview.htm
- Federal Reserve asset valuations section: https://www.federalreserve.gov/publications/november-2025-financial-stability-report-asset-valuations.htm
- State Street market note, May 8, 2026: https://www.ssga.com/be/en_gb/institutional/insights/mind-on-the-market-08-may-2026
- NVIDIA FY2026 results: https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Fourth-Quarter-and-Fiscal-2026/

Important difference from 2000: today's AI leaders are often highly profitable, cash-generative mega-caps. The bubble risk may sit less in "no revenue" companies and more in expectations, capex duration, concentration, second-order suppliers, and crowded positioning.

## Business Implications For TradingAgents

1. Build the company like capital gets expensive tomorrow.

   Dot-com lesson: default-alive beats narrative strength. Keep compute/data costs variable. Avoid locking into expensive infrastructure until the trading/product ROI is proven.

2. Make risk tooling the product edge.

   In bubble-like markets, users do not just need more signals. They need auditability, stop discipline, exposure caps, drawdown halts, and post-trade learning. Your current repo is moving toward that.

3. Sell "decision discipline", not "magic prediction."

   The market already has AI hype. A credible product says: here is the setup, the invalidation level, the expected reward, the regime, and the exact reason we exited.

4. Treat AI market concentration as both opportunity and threat.

   AI momentum can produce great intraday opportunities. It can also cause correlated reversals. The system should reduce size or stop trading new longs when leadership narrows, rates/yields rise sharply, or mega-cap AI guidance disappoints.

5. Use the dot-com pattern in the daily briefing.

   Add a "bubble regime board" to the morning process:
   - Nasdaq/QQQ distance from moving averages
   - market breadth
   - mega-cap contribution to index move
   - VIX and credit spreads
   - 10-year yield and Fed expectations
   - AI capex headline direction
   - semiconductor and power/data-center stress signals

6. Do not increase real-money risk yet.

   The exit-policy replay supports testing, but it is too small and mixed for scaling. Stay in paper until the bot shows stable positive expectancy after slippage assumptions.

## Recommended Next Actions

1. Harmonize launcher defaults.

   Make `scripts/run_autonomous_day_trader.py` use the same profit-protection defaults as `run_day_trader_bot.py`, or document why it is intentionally slower to exit.

2. Add dual-stop reporting.

   Every buy plan should show:
   - monitor stale-loser stop
   - momentum-decay rule
   - bracket disaster stop
   - take-profit
   - reward/risk using the practical monitor stop

3. Add expectancy analytics.

   Create a daily artifact:

   | Strategy | Trades | Win % | Avg Win | Avg Loss | Profit Factor | Avg Hold | Best Exit | Worst Exit |
   | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |

4. Add a regime multiplier.

   Example:
   - green regime: normal target positions
   - yellow regime: halve new exposure, require higher fit score
   - red regime: no new longs except best setups, flatten faster

5. Tune stops per strategy.

   Opening range, momentum breakout, and relative-strength continuation should not share the same practical exit logic. Run threshold sweeps separately by strategy and time bucket.

6. Promote "paper evidence threshold" before scaling.

   A reasonable gate:
   - at least 100 closed paper trades
   - positive expectancy after assumed slippage
   - no single day below max session loss
   - strategy-level profit factor above 1.2
   - no uncontrolled overnight exposure

## Bottom Line

Your features are not perfect, but they are becoming structurally sound. The biggest improvement was moving from passive bracket hopes to active risk management. The next leap is measurement: stop arguing whether 0.75%, 1.0%, or 2.5% is "right" in the abstract, and let replay plus forward paper trading decide per strategy, symbol class, time-of-day, and market regime.

The dot-com lesson for the business is blunt: in speculative technology markets, the winner is not the one with the loudest thesis. It is the one with real unit economics, cash discipline, adaptive risk controls, and enough patience to survive the shakeout.
