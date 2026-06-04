# News Reversion Desk

The News Reversion Desk is a research function for the Codex CEO paper-trading
business. It studies whether a popular stock or ETF moves sharply after a dated
headline and then closes back toward the pre-news price on the next trading day.

This desk is evidence-only by default. It can produce a watchlist or a
paper-research note, but order submission still belongs to the existing
execution controller and must pass market-open, spread, liquidity, sizing,
stop-loss, and take-profit gates.

## Event Study

For each recent dated headline, the desk records:

- previous trading-session close as `price_before_news`;
- event-session close as `price_after_news`;
- next trading-session close as `price_one_day_after`;
- the event-session move away from the pre-news close;
- the one-day fade return from taking the opposite side of that event move;
- the percentage of the event move captured by reversion toward the pre-news
  close.

The daily-bar study intentionally avoids pretending it has intraday precision.
Headlines published after the US cash close are assigned to the next available
trading session.

Run the standalone report:

```powershell
.\.venv\Scripts\python.exe scripts\backtest_news_reversion_strategy.py `
  --results-dir results/news_reversion_desk `
  --lookback-days 21 `
  --max-events-per-symbol 3
```

Use a smaller hand-picked universe:

```powershell
.\.venv\Scripts\python.exe scripts\backtest_news_reversion_strategy.py `
  --universe NVDA,TSLA,AMD,PLTR,COIN,QQQ,SPY `
  --lookback-days 30 `
  --results-dir results/news_reversion_desk
```

Artifacts:

- `news_reversion_event_study.json`
- `news_reversion_event_study.md`

## Viability Standard

The desk keeps the strategy research-only when the eligible event sample is
small. A recent sample becomes `promising_for_paper_research` only when it has
at least five eligible events, a win rate of at least 55%, positive average
fade return, and meaningful average reversion capture.

Even a positive report is not approval for live trading. It only means the next
step is paper testing with live confirmation: tight spread, enough volume,
clear invalidation, and no major risk tags such as halt, fraud, dilution,
bankruptcy, or regulatory enforcement.
