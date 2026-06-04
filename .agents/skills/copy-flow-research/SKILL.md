---
name: copy-flow-research
description: Use when researching TradingAgents copy-trading, politician trades, insider transactions, institutional ownership, delayed disclosures, holder flows, and whether public trade disclosures add useful signal or risk.
---

# Copy Flow Research

## Workflow

1. Identify the source: politician disclosure, insider transaction, holder filing, ETF flow, or public trade commentary.
2. Record disclosure lag, transaction date, filing date, instrument, size range, and confidence.
3. Treat copy-flow data as delayed context, not an entry trigger.
4. Check whether price has already moved since the disclosed transaction.
5. Convert the finding to `context_only`, `watch`, `confirm_with_price`, or `risk_review`.

## Evidence Checklist

- Source URL or dataset name.
- Transaction and disclosure dates.
- Direction and size range.
- Whether the actor has a relevant committee/sector link.
- Price move since transaction date.
- Conflict, legal, or reputation risk.

## Red Flags

- Treating delayed disclosure as live order flow.
- Copying illiquid or option-heavy transactions without context.
- Ignoring partial sales, tax/vesting transactions, or diversified portfolios.
- No price confirmation.
