---
name: multi-desk-portfolio-risk
description: Use when allocating risk across TradingAgents desks, managing simultaneous trades, checking correlated exposure, setting desk capital caps, or coordinating Equities, News, Crypto, Macro ETF, and Forex research desks.
---

# Multi-Desk Portfolio Risk

## Workflow

1. Treat desks as specialists, not independent order submitters.
2. Route every idea through one Portfolio Office and one execution controller.
3. Check desk capital cap, max active positions, symbol overlap, sector overlap, and market-regime correlation.
4. Prefer cash over forced deployment when no desk has a high-quality setup.
5. Separate 24/7 crypto risk from US cash-session equity risk.
6. Keep forex research-only until a dedicated FX broker, data feed, and risk policy exist.

## Default Desk Caps

- Equities Momentum Desk: up to 45% paper allocation.
- Macro ETF Desk: up to 20% paper allocation.
- News Catalyst And Reversion Desk: up to 15% watchlist/research cap.
- Crypto Desk: up to 10% only after crypto adapter approval.
- Forex Research Desk: 0% until execution support exists.
- Reserve: at least 10% unallocated.

## Simultaneous Trade Checks

- Do not buy multiple symbols that express the same risk without portfolio approval.
- Count QQQ, NVDA, AMD, AVGO, ARM, MU, and SMH/SOXX as potentially correlated AI/semiconductor exposure.
- Count COIN, MSTR, HOOD, IBIT, GBTC, BITO, ETHA, and ETHE as crypto-linked exposure.
- Count SPY, QQQ, IWM, TLT, GLD, XLE, and UUP as macro exposure.
- Block new entries when session loss, drawdown, spread, stale data, or duplicate-order guards trigger.

## Outputs

Return allocation decisions as `approve`, `reduce`, `watch`, `block`, or `research_only`, with the desk cap, risk reason, and exposure conflict.
