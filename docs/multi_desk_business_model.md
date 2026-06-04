# Multi-Desk Business Model

The business should split by market, strategy behavior, and execution readiness
rather than by individual ticker. Trading many symbols at once is reasonable
only if each desk has its own risk budget and the Portfolio Office controls
correlated exposure across desks.

## Recommended Split

```text
Owner / Human CEO
`-- Codex CEO Runner
    |-- Data Quality And Strategy Governance
    |   |-- Data Quality Officer
    |   |-- Experiment / Backtest Auditor
    |   |-- Strategy Promotion Committee
    |   `-- P&L Attribution Analyst
    |
    |-- Strategy Research Department
    |   |-- Strategy Idea Generator
    |   |-- Backtest Lab
    |   |-- Event Study Lab
    |   `-- Strategy Library Maintainer
    |
    |-- Equities Momentum Desk
    |   |-- Momentum Breakout
    |   |-- Relative Strength Continuation
    |   `-- Opening Range Breakout
    |
    |-- News Catalyst And Reversion Desk
    |   |-- Current News Scout
    |   |-- News Reversion Event Study
    |   `-- Catalyst Risk Review
    |
    |-- Crypto Desk
    |   |-- Crypto Momentum Research
    |   |-- Crypto Range Reversion Research
    |   `-- Crypto News Catalyst Research
    |
    |-- Macro ETF Desk
    |   |-- Rates / Inflation
    |   |-- Risk-On / Risk-Off
    |   `-- Geopolitics / Commodities Proxy
    |
    |-- Forex Research Desk
    |   |-- USD / Rates Context
    |   |-- FX Macro Research
    |   `-- Currency Risk Notes
    |
    `-- Central Portfolio And Execution
        |-- Portfolio Office Allocator
        |-- Risk Office Guardian
        |-- Operations Compliance Auditor
        `-- Alpaca Paper Execution Controller
```

## Operating Rule

Each desk can research, rank, and explain. Only the central execution
controller can submit paper orders. A desk must pass the Data Quality And
Strategy Governance gate before it can move from research to paper trading.

The Strategy Research Department is the quant gate between desk research and
trading. It promotes strategies through evidence stages, and the CEO runner can
only allocate to strategies promoted to `paper_trade_candidate` or
`approved_paper_strategy`.

## Current Execution Readiness

| Desk | Status | Execution |
| --- | --- | --- |
| Equities Momentum Desk | Paper trading enabled for promoted strategies | Alpaca paper controller |
| Macro ETF Desk | Paper watchlist | Alpaca paper controller after strategy promotion |
| News Catalyst And Reversion Desk | Research and paper watchlist | Research only by default |
| Crypto Desk | Research first | Needs crypto-specific adapter and 24/7 risk gates |
| Forex Research Desk | Research only | Not supported by current execution stack |
| Data Quality And Strategy Governance | Required gate | No order authority |
| Strategy Research Department | Required promotion gate | No order authority |

## Is This A Good Idea?

Yes, but only if the split reduces risk instead of multiplying it. A
multi-desk business is useful because crypto, equities, macro ETFs, and news
reversion behave differently. It becomes dangerous if every desk can trade at
the same time without a central allocator.

The right model is not "many bots all trading." The right model is:

```text
many specialist desks -> one evidence gate -> one portfolio allocator -> one execution controller
```

## Capital Split For Paper Mode

Start with conservative caps:

| Desk | Paper Allocation Cap |
| --- | ---: |
| Equities Momentum Desk | 45% |
| Macro ETF Desk | 20% |
| News Catalyst And Reversion Desk | 15% watchlist/research cap |
| Crypto Desk | 10% research-to-paper cap only after adapter approval |
| Forex Research Desk | 0% until broker/data/execution support exists |
| Reserve / unallocated | 10% |

The cap is a maximum, not a target. If no desk has a high-quality setup, cash is
an acceptable position.

## Promotion Gate

Strategies move through these stages:

1. Research idea
2. Paper watchlist
3. Paper trade candidate
4. Approved paper strategy
5. Live candidate

This project remains paper-only unless live trading is explicitly approved as a
separate project.

## Implementation Notes

The durable desk model lives in:

`tradingagents/company/business_governance.py`

It defines the default desks, allocation caps, execution authority, and
evidence requirements. The model intentionally keeps crypto and forex from
accidentally using the existing equity execution path.

The strategy promotion engine lives in:

`tradingagents/company/strategy_research_department.py`

The generated strategy library lives in:

`knowledge/strategy_library/`

## Current Source Notes

- Alpaca Trading API documentation describes stock and crypto trading support.
- Alpaca crypto documentation describes 24/7 crypto trading and crypto-specific
  order constraints.
- Alpaca docs currently describe FX/futures as roadmap rather than the current
  Trading API execution path, so forex stays research-only here.
