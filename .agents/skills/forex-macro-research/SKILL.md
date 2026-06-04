---
name: forex-macro-research
description: Use when researching TradingAgents forex, currency, USD, rates, macro, inflation, central bank, or FX-sensitive equity and ETF context. Keep direct forex execution research-only until a dedicated FX broker and risk adapter exist.
---

# Forex Macro Research

## Workflow

1. Treat direct spot forex as research-only in the current TradingAgents stack.
2. Use FX research to inform macro ETFs, gold, treasuries, multinational equities, and risk-on/risk-off context.
3. Track central-bank policy, CPI/PPI/jobs data, yields, dollar strength, and geopolitical shocks.
4. Translate FX observations into trade context, not direct FX orders.
5. Require a dedicated broker/data/execution adapter before forex becomes paper-tradeable.

## Research Outputs

- Currency pair or dollar theme.
- Macro catalyst and timestamp.
- Expected impact on ETFs/sectors.
- Confidence and uncertainty.
- What would invalidate the macro view.
- Whether the insight is `context_only`, `macro_etf_watch`, or `risk_review`.

## Blockers

- No FX broker adapter.
- No base/quote currency sizing.
- No rollover/leverage policy.
- No 24/5 market supervision.
- Attempt to route FX through equity ticker execution.
