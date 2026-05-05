# GitHub Repository Research

Updated: 2026-05-04

This file supports the GitHub Researcher in the AI research department. The
goal is to learn from popular open-source financial AI, trading, data, agent,
and backtesting projects without blindly copying code or weakening paper-trade
safety rails.

## Seed Repositories

| Repository | Area | Lesson For This Business | Source |
| --- | --- | --- | --- |
| TauricResearch/TradingAgents | Multi-agent trading research | Keep specialist roles, debate, risk review, and durable artifacts. | https://github.com/TauricResearch/TradingAgents |
| AI4Finance-Foundation/FinRobot | Financial AI agents | Borrow layered agent workflows and equity report structure. | https://github.com/AI4Finance-Foundation/FinRobot |
| AI4Finance-Foundation/FinGPT | Financial LLMs | Use finance-specific NLP ideas before attempting local fine-tuning. | https://github.com/AI4Finance-Foundation/FinGPT |
| AI4Finance-Foundation/FinRL | Financial reinforcement learning | Watch portfolio/rebalance evaluation ideas; keep RL out of autonomous paper execution for now. | https://github.com/AI4Finance-Foundation/FinRL |
| OpenBB-finance/OpenBB | Financial data platform | Prototype optional data adapters only after they improve signal. | https://github.com/OpenBB-finance/OpenBB |
| QuantConnect/Lean | Algorithmic trading engine | Mirror universe, alpha, portfolio, execution, risk, and result-processing boundaries. | https://github.com/QuantConnect/Lean |
| mementum/backtrader | Backtesting | Continue using it for lightweight local candidate validation. | https://github.com/mementum/backtrader |
| polakowo/vectorbt | Vectorized backtesting | Consider for fast batch strategy research if Backtest Lab becomes too slow. | https://github.com/polakowo/vectorbt |
| kernc/backtesting.py | Backtesting API | Study simple strategy APIs and plotting; check license before reuse. | https://github.com/kernc/backtesting.py |
| freqtrade/freqtrade | Trading bot operations | Borrow dry-run discipline, lookahead checks, and status reporting concepts. | https://github.com/freqtrade/freqtrade |

## Operating Rules

- Treat GitHub findings as architecture research, not trading signals.
- Prefer `adopt_now` only for low-risk patterns: artifacts, tests, dry-run
  checks, status reporting, and optional adapters.
- Require license review before copying any code or strategy template.
- Require a failing test or a measurable workflow gap before adding a new
  dependency.
- Keep autonomous Alpaca execution paper-only and behind existing market-open,
  order-size, liquidity, and confidence gates.

## Implemented Hooks

- `tradingagents/agents/research_department/github_researcher.py`
- `tradingagents/agents/utils/github_research_tools.py`
- `github_research_report` state slot and per-run artifact output
- Research Director synthesis now includes the GitHub Researcher memo
