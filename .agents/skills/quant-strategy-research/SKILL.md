---
name: quant-strategy-research
description: Use when the TradingAgents Strategy Research Department should autonomously generate, backtest, score, promote, demote, or retire trading strategies from price, volume, catalyst, crypto, macro, and post-market evidence.
---

# Quant Strategy Research

## Workflow

1. Generate hypotheses from market behavior, failed trades, missed winners, news shocks, volume anomalies, macro regimes, and prior backtest artifacts.
2. Convert every idea into a structured strategy candidate: setup, trigger, confirmation, invalidation, exit, risk, universe, and required data.
3. Backtest or event-study the idea before promotion.
4. Score strategies by trade count, expectancy, profit factor, drawdown, data quality, and execution feasibility.
5. Promote only to `paper_trade_candidate` or `approved_paper_strategy` when evidence clears thresholds.
6. Send only promoted strategy IDs to Trading; keep research/watch/retired ideas out of autonomous execution.

## Strategy Card Fields

- Strategy ID.
- Desk and asset class.
- Hypothesis.
- Entry rules.
- Exit rules.
- Risk rules.
- Required data.
- Backtest/event-study metrics.
- Promotion status.
- Last reviewed timestamp.

## Promotion Bias

- Prefer simple rules that can be tested with available data.
- Prefer robust moderate edges over tiny high-complexity edges.
- Penalize low sample size, data leakage, duplicated events, missing spread/slippage assumptions, and unsupported execution paths.
- Treat negative evidence as useful: retire or demote strategies quickly.
