# Codex CEO Company Mode

Codex CEO mode is the compute-light operating layer for running the business
through Codex while keeping local Ollama models as cheap staff support.

The workflow is intentionally smaller than the full single-ticker LangGraph:

1. Screen a liquid market universe with deterministic price, momentum, volume,
   and volatility rules.
2. Build a top-10 research watchlist.
3. Run a lightweight Backtrader momentum smoke test over each candidate.
4. Produce a starter portfolio target and proposed Alpaca paper orders.
5. Write a `ceo_briefing_pack.md` for Codex/user review.
6. Submit paper orders only when the market is open and CEO approval is present.

Run a dry run:

```powershell
.\.venv\Scripts\python.exe scripts\run_codex_ceo_company.py --results-dir results
```

Run a guarded paper submission:

```powershell
.\.venv\Scripts\python.exe scripts\run_codex_ceo_company.py --results-dir results --submit-paper --ceo-approved
```

Run autonomous paper submission without the CEO approval gate:

```powershell
.\.venv\Scripts\python.exe scripts\run_codex_ceo_company.py `
  --results-dir results `
  --strategy-profile safe `
  --max-deploy-usd 1250 `
  --target-positions 5 `
  --max-order-notional-usd 250 `
  --liquidate-non-targets `
  --autonomous-paper
```

Autonomous mode is still paper-only and still enforces the market-open gate,
order-notional cap, deploy cap, liquidity filter, and strategy-confidence
filter.

Run the full market-hours autonomous loop with both day-trading profiles:

```powershell
.\.venv\Scripts\python.exe scripts\run_autonomous_day_trader.py `
  --strategy both `
  --run-until-close `
  --interval-seconds 30 `
  --position-monitor-seconds 5 `
  --results-dir results/autonomous_day_trader
```

The loop uses Alpaca's trading clock, so it only submits paper orders while the
US market is actually open. It starts a safe profile first, then a risky profile.
Accepted paper orders are written to the local run artifacts and launcher logs.
Between full strategy scans, the autonomous CEO checks open positions and open
orders every few seconds so the terminal does not go quiet while trades are live.

Strategy profiles:

- `safe`: minimum `$2,000` target notional per new paper order, up to about
  `$3,000` per new paper order, up to 20% paper-account deployment by default
  on a `$100k` paper account, higher confidence threshold, tighter stops, and
  blocks wider-spread/high-volatility/weak-backtest setups.
- `risky`: minimum `$2,000` target notional per new paper order, up to about
  `$5,000` per new paper order, up to 30% paper-account deployment by default
  on a `$100k` paper account, lower confidence threshold, wider stops, larger
  take-profit brackets, and permits more momentum breakouts.

Realtime data path:

- Alpaca 1-minute intraday bars rank the liquid universe.
- Alpaca latest trades and quotes refresh prices, spreads, and stale-trade flags.
- Alpaca trade/quote-derived order flow adds volume profile, delta, large prints,
  and absorption flags for the strongest candidates.
- Bracket orders attach stop-loss and take-profit exits to submitted buy orders.

Useful efficiency controls:

```powershell
.\.venv\Scripts\python.exe scripts\run_codex_ceo_company.py `
  --results-dir results `
  --max-deploy-usd 1250 `
  --target-positions 5 `
  --max-order-notional-usd 250 `
  --no-ollama-staff
```

Defaults favor weak local hardware:

- Ollama provider defaults to `qwen3:0.6b`.
- The local staff memo is one short Ollama call.
- Market screening uses batch `yfinance` downloads instead of one LLM call per
  ticker.
- Backtest Lab reuses the downloaded daily bars, so it adds evidence without a
  second market-data pass.
- Alpaca execution remains paper-only in this workflow.
- Day-trading strategy rules live in `tradingagents/company/day_trading_strategy.py`.
- Backtest Lab lives in `tradingagents/company/backtest_lab.py`; use
  `--no-backtest-lab` to skip it or `--allow-weak-backtests` to make it
  advisory only.
- Autonomous safe/risky profile settings live in
  `tradingagents/company/strategy_profiles.py`.
- The market-hours loop lives in `scripts/run_autonomous_day_trader.py`.
- Reusable research lives in `knowledge/day_trading_volatility_research.md` and
  `.agents/skills/day-trading-research/`.
- Financial AI technology scouting lives in
  `knowledge/financial_ai_technology_scouting.md`,
  `.agents/skills/financial-ai-technology-scout/`, and
  `tradingagents/company/technology_scout.py`.
