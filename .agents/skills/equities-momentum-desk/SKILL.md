---
name: equities-momentum-desk
description: Use when researching or operating the TradingAgents Equities Momentum Desk, including US stocks and ETFs, momentum breakouts, relative strength continuation, opening range breakout, VWAP confirmation, liquidity filters, and Alpaca paper equity execution readiness.
---

# Equities Momentum Desk

## Workflow

1. Screen only liquid US stocks/ETFs unless the user explicitly changes the universe.
2. Prefer compute-light filters: price, 1D/5D/20D momentum, relative volume, volatility, VWAP, spread, and order-flow flags.
3. Classify the setup before sizing: `momentum_breakout`, `relative_strength_continuation`, `pullback_watch`, `range_reversion_watch`, or `fade_or_news_watch`.
4. Allow autonomous paper entries only for promoted strategies with live data gates and bracket exits.
5. Flatten intraday positions by the configured close guard unless a separate overnight mandate exists.

## Entry Evidence

- Fresh live price and quote.
- Tight spread and useful volume.
- Relative volume or order-flow confirmation.
- Named strategy and invalidation.
- Stop and take-profit plan.
- No duplicate working order.

## Stand-Down Conditions

- Wide spread or stale trade.
- Weak or insufficient backtest when the safe profile requires it.
- News risk tag requiring review.
- Excessive same-sector exposure.
- Session drawdown or max loss guard.
