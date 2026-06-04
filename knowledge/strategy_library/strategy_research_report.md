# Strategy Research Department Report

- Generated: 2026-06-04T09:38:48.055853+00:00
- Evidence root: results
- Approved paper strategies: opening_range_breakout_15m, momentum_breakout
- Paper trade candidates: relative_strength_continuation
- Blocked/research-only strategies: crypto_momentum, news_reversion_event_study, range_reversion_to_vwap, vwap_reclaim

## Strategy Library
| Strategy | Desk | Status | Decision | Trades | Return | Profit Factor | Max DD | Evidence | Note |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| opening_range_breakout_15m | Equities Momentum Desk | approved_paper_strategy | paper_trade_allowed | 371 | 5.36% | 1.46 | 4.70% | 11.15 | Promoted by intraday aggregate backtest evidence. |
| momentum_breakout | Equities Momentum Desk | approved_paper_strategy | paper_trade_allowed | 358 | 2.58% | 1.70 | 3.37% | 9.39 | Promoted by intraday aggregate backtest evidence. |
| relative_strength_continuation | Equities Momentum Desk | paper_trade_candidate | paper_trade_allowed | 370 | 1.28% | 1.13 | 4.71% | 5.73 | Positive but not strong enough for full approved status. |
| range_reversion_watch | Equities Momentum Desk | paper_watchlist | watch_only | 0 | 0.00% | 0.00 | 0.00% | 0.00 | Watchlist label, not a tradeable strategy. |
| pullback_watch | Equities Momentum Desk | paper_watchlist | watch_only | 0 | 0.00% | 0.00 | 0.00% | 0.00 | Watchlist label, not a tradeable strategy. |
| general_momentum_watch | Equities Momentum Desk | paper_watchlist | watch_only | 0 | 0.00% | 0.00 | 0.00% | 0.00 | Watchlist label, not a tradeable strategy. |
| fade_or_news_watch | News Catalyst And Reversion Desk | paper_watchlist | watch_only | 0 | 0.00% | 0.00 | 0.00% | 0.00 | Watchlist label, not a tradeable strategy. |
| crypto_momentum | Crypto Desk | research_idea | research_only | 7 | -2.58% | 0.00 | 28.84% | 12.41 | Crypto evidence is not strong enough and execution support is incomplete. |
| news_reversion_event_study | News Catalyst And Reversion Desk | research_idea | research_only | 6 | -2.24% | 0.00 | 0.00% | -1.88 | Recent event study is negative; keep research-only. |
| vwap_reclaim | Equities Momentum Desk | retired | blocked | 339 | -0.79% | 0.97 | 3.71% | 4.26 | Demoted by negative aggregate backtest evidence. |
| range_reversion_to_vwap | Equities Momentum Desk | retired | blocked | 525 | -2.27% | 0.84 | 6.19% | 1.60 | Demoted by negative aggregate backtest evidence. |

## Trading Handoff Rule
Trading may only create autonomous paper orders from `paper_trade_candidate` or `approved_paper_strategy` strategies. Research, watchlist, and retired strategies may explain candidates but must not submit orders.
