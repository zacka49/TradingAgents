---
name: day-trading-research
description: Research and operationalize day-trading, volatility, momentum, breakout, range, news-based, scalping, fading, VWAP, and intraday risk-management strategies for the TradingAgents paper-trading business. Use when Codex is asked to improve the trading business, create/update trading strategy knowledge, evaluate short-term trading setups, or modify autonomous Alpaca paper-trading rules.
---

# Day Trading Research

## Workflow

1. Read `references/day-trading-playbook.md` for the current strategy library and risk gates.
2. Check live/current sources before changing strategy assumptions, broker behavior, market rules, or automation schedules.
3. Keep autonomous execution paper-only unless the user explicitly requests a separate live-broker project.
4. Prefer compute-light deterministic filters before LLM calls: price momentum, relative volume, volatility, support/resistance, VWAP, and news flags.
5. When updating code, preserve market-open gates, max deployed capital, max order notional, and per-trade stop/take-profit planning.
6. Write new durable research into `knowledge/` and cross-link it from this skill reference when it should guide future agents.

## Strategy Mapping

- Trending, high relative-volume names: prefer `momentum_breakout` or `relative_strength_continuation`.
- Strong trend with latest-session weakness: mark as `pullback_watch`; do not auto-buy without confirmation.
- Choppy/high-volatility names without direction: mark as `range_reversion_watch`; require support/resistance confirmation.
- Extended or news-shock moves: mark as `fade_or_news_watch`; require fresh catalyst review.

## Execution Rules

- Use Alpaca paper only.
- Autonomous paper runs may skip CEO approval, but must keep market-open and size gates.
- Use protective exits where the broker/order type supports them; if rejected, record the failure in artifacts instead of crashing silently.
- Avoid scalping automation unless real-time quotes, spread checks, and latency-aware execution are available.

## Resources

- `references/day-trading-playbook.md`: strategy definitions, trigger ideas, risk controls, and source links.
