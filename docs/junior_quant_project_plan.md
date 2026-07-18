# Junior Quant Project Plan

Created: 2026-06-05

Time window: 2026-06-08 to 2026-08-30

Current profile:
- Data science degree completed through a GSK apprenticeship.
- Around 4 years of applied data science work experience.
- Strongest current skills: Python, R, statistics, modelling, pharma CMC statistics, cell line development data science, regulated scientific analysis.
- Main gap: finance context, market data habits, portfolio/risk language, and quant interview practice.

Target outcome by the end of August 2026:
- Have 4 to 6 quant-relevant projects that prove you can handle financial data, risk, backtesting, and model validation.
- Be ready to apply for junior quant-adjacent roles with a credible story.
- Use your GSK experience as a strength, not something to hide.

## Positioning

Your strongest positioning is not "new graduate trying to enter finance".

Use this:

> Data Scientist with around 4 years of applied experience at GSK, using Python/R, statistical modelling, experimental data analysis, and regulated model documentation on complex scientific datasets. Now specialising toward quantitative finance through market data analysis, risk modelling, portfolio analytics, and systematic strategy backtesting.

The hiring story:
- CMC statistics maps to model validation, process monitoring, uncertainty, quality control, and statistical governance.
- Cell line development data science maps to modelling noisy, high-dimensional, real-world data.
- Regulated pharma work maps to banks, model risk, auditability, documentation, and reproducibility.
- Python/R modelling maps directly to quant analytics, investment data science, portfolio analytics, and risk analytics.
- The missing layer is finance domain knowledge, not general data science ability.

## Weekly Time Split

Assume 8 to 12 hours per week outside work.

Minimum week:
- 4 hours project building
- 2 hours finance/statistics learning
- 1 hour interview maths/coding
- 1 hour applications/networking

Ideal week:
- 5 to 6 hours project building
- 2 hours finance/statistics learning
- 2 hours interview maths/coding
- 2 hours applications/networking

Application split:
- 20% stretch: quant trader, quant researcher, junior quant researcher.
- 55% realistic quant-adjacent: market risk, model validation, pricing analyst, portfolio analytics, investment data scientist, quant analyst in risk/index/portfolio teams.
- 25% safety: data scientist or ML analyst roles in finance, fintech, banking, insurance, asset management.

## Portfolio Projects

| Project | Main Skill | Output | Why It Helps |
| --- | --- | --- | --- |
| 1. Market Data Foundations | Financial data basics | Notebook with returns, volatility, drawdowns, correlations | Shows you understand market data beyond generic data science |
| 2. Financial Data Quality Pipeline | Data engineering and validation | Python script or notebook that validates price data | Converts your pharma data quality experience into finance language |
| 3. Risk Engine | Risk modelling | VaR, Expected Shortfall, stress tests, drawdown analysis | Fits market risk, model validation, and portfolio analytics roles |
| 4. Portfolio Construction Lab | Portfolio maths | Optimiser, risk parity, benchmark comparison | Shows finance-specific quantitative reasoning |
| 5. Backtest Validation Case Study | Strategy research discipline | TradingAgents strategy audit with costs and leakage checks | Gives you a quant research style portfolio piece |
| 6. Application Pack | Career conversion | CV bullets, project README, interview examples | Turns the learning into job applications |

## Week 1: Financial Data Basics

Dates: 2026-06-08 to 2026-06-14

Project: Market Data Foundations

Goal:
- Learn how financial data differs from pharma or experimental data.
- Build intuition for returns, volatility, correlation, beta, Sharpe ratio, and drawdown.

Build:
- `notebooks/01_market_data_foundations.ipynb`

Use:
- 10 liquid assets, for example SPY, QQQ, AAPL, MSFT, NVDA, JPM, XLF, GLD, TLT, BTC-USD.
- Daily price data.

Tasks:
- Download or load price data.
- Convert prices into simple returns and log returns.
- Plot cumulative returns.
- Calculate annualised return, annualised volatility, Sharpe ratio, max drawdown, skew, kurtosis.
- Build a rolling 30-day volatility chart.
- Build a correlation heatmap.
- Compare one stock against SPY using beta and alpha.

Definition of done:
- You can explain why quant models usually use returns rather than raw prices.
- You can explain volatility, drawdown, Sharpe, correlation, beta, and alpha in plain English.
- You have 5 to 8 clean charts in one notebook.

Visual learning:
- MIT Finance Theory I: Risk and Return
- 3Blue1Brown: Bayes theorem
- StatQuest: standard deviation, correlation, p-values, regression

CV/interview angle:
- "Built a Python market data analysis notebook calculating returns, volatility, drawdown, Sharpe ratio, rolling risk, correlation, and beta across equities, bonds, commodities, and crypto."

## Week 2: Visual Market Dashboard

Dates: 2026-06-15 to 2026-06-21

Project: Market Data Foundations, part 2

Goal:
- Make your analysis visual and explainable.
- Start building outputs that look useful to a portfolio manager, risk manager, or quant analyst.

Build:
- `notebooks/02_market_dashboard.ipynb`

Tasks:
- Create a reusable function that takes a ticker list and returns a summary table.
- Create a visual dashboard with:
  - cumulative return chart
  - rolling volatility chart
  - rolling drawdown chart
  - correlation heatmap
  - return distribution chart
  - best and worst return days
- Add a short written interpretation under each chart.

Definition of done:
- Someone can open the notebook and understand which assets were riskier, which had worse drawdowns, and which moved together.
- You can talk through the analysis without sounding like you only followed a tutorial.

Quant skill learned:
- Exploratory data analysis for financial markets.
- Communicating risk visually.

Pharma-to-finance translation:
- This is similar to exploratory analysis of assay or process data, but the target variable is market return and the risk is capital loss.

## Week 3: Financial Data Quality Pipeline

Dates: 2026-06-22 to 2026-06-28

Project: Data Quality Pipeline

Goal:
- Turn your GSK regulated data experience into a finance-relevant project.
- Show that you understand bad data can create fake trading signals.

Build:
- `notebooks/03_financial_data_quality.ipynb`
- Optional later script: `scripts/validate_market_data.py`

Tasks:
- Check for missing dates.
- Check for duplicate timestamps.
- Check for impossible prices.
- Check for extreme returns.
- Check for stale prices.
- Check for ticker alignment problems.
- Compare adjusted close vs close.
- Produce a validation report table.

Definition of done:
- You have a data validation checklist.
- You can explain how bad financial data creates false signals.
- You can connect this to your pharma CMC experience with data quality, outliers, batch effects, and auditability.

Quant skill learned:
- Data validation for systematic research.
- Avoiding false conclusions from dirty market data.

CV/interview angle:
- "Built a market data validation workflow to detect missing observations, stale prices, duplicate timestamps, extreme returns, and adjustment issues before downstream modelling."

## Week 4: Time Series Validation and Leakage

Dates: 2026-06-29 to 2026-07-05

Project: Time Series Modelling Discipline

Goal:
- Learn the most important difference between normal ML and finance ML: time ordering.
- Avoid look-ahead bias, leakage, and overfitting.

Build:
- `notebooks/04_time_series_validation.ipynb`

Tasks:
- Create lagged features from returns and volatility.
- Predict next-day direction or next-day return.
- Compare random train/test split vs chronological train/test split.
- Add walk-forward validation.
- Show how random splitting gives misleading results.
- Track hit rate, precision, recall, mean return, Sharpe, and drawdown.

Definition of done:
- You can explain look-ahead bias.
- You can explain why cross-validation must be adapted for time series.
- You can explain why high ML accuracy does not automatically mean a profitable strategy.

Quant skill learned:
- Finance-aware model validation.
- Walk-forward testing.

Pharma-to-finance translation:
- Similar to avoiding leakage across experimental batches or future process information, but with strict time ordering.

## Week 5: Risk Engine

Dates: 2026-07-06 to 2026-07-12

Project: Risk Engine

Goal:
- Build a small risk analytics engine that is relevant to market risk, model validation, and portfolio analytics jobs.

Build:
- `notebooks/05_risk_engine.ipynb`

Tasks:
- Calculate portfolio daily returns.
- Calculate historical VaR.
- Calculate parametric VaR.
- Calculate Expected Shortfall.
- Calculate max drawdown and drawdown duration.
- Add stress scenarios:
  - equity selloff
  - rates shock
  - high-volatility month
  - asset correlation spike
- Compare equal-weight portfolio risk vs concentrated portfolio risk.

Definition of done:
- You can explain VaR and Expected Shortfall simply.
- You can explain the weakness of VaR.
- You can show how diversification changes risk.

Quant skill learned:
- Risk measurement.
- Stress testing.
- Portfolio loss analysis.

CV/interview angle:
- "Implemented portfolio risk analytics in Python, including historical VaR, parametric VaR, Expected Shortfall, drawdown analysis, and stress testing across multi-asset portfolios."

## Week 6: Portfolio Construction Lab

Dates: 2026-07-13 to 2026-07-19

Project: Portfolio Optimisation

Goal:
- Learn how quants think about combining assets, not just predicting one asset.

Build:
- `notebooks/06_portfolio_construction.ipynb`

Tasks:
- Build equal-weight portfolios.
- Build volatility-weighted portfolios.
- Build simple risk parity portfolios.
- Build a mean-variance optimiser.
- Add constraints, for example max 25% per asset.
- Compare against SPY or a 60/40 proxy.
- Measure return, volatility, Sharpe, max drawdown, turnover, and stability.

Definition of done:
- You can explain why the highest-return asset is not automatically the best portfolio.
- You can explain diversification, covariance, concentration risk, and turnover.
- You can explain why optimisation can overfit.

Quant skill learned:
- Portfolio analytics.
- Covariance and optimisation.
- Benchmark comparison.

CV/interview angle:
- "Developed portfolio construction notebooks comparing equal weight, volatility weighting, risk parity, and constrained mean-variance optimisation with benchmark and risk analysis."

## Week 7: TradingAgents Strategy Audit

Dates: 2026-07-20 to 2026-07-26

Project: Backtest Validation Case Study

Goal:
- Use this repo as your quant learning project.
- Audit one existing strategy like a junior quant researcher would.

Build:
- `docs/strategy_audit_opening_range_breakout.md`
- or `docs/strategy_audit_momentum_breakout.md`

Tasks:
- Choose one strategy already in this repo.
- Document the strategy hypothesis in plain English.
- Identify the universe, entry rule, exit rule, holding period, risk rule, and benchmark.
- Re-run or inspect the existing backtest.
- Record metrics:
  - number of trades
  - total return
  - Sharpe ratio if available
  - profit factor
  - max drawdown
  - win rate
  - average win/loss
  - turnover
- Add a section called "Ways this backtest could be misleading".

Definition of done:
- You can explain the strategy without relying on code.
- You can explain what evidence supports it and what evidence is weak.
- You have a Markdown research note that can be shown as a portfolio piece.

Quant skill learned:
- Strategy hypothesis writing.
- Research note structure.
- Backtest interpretation.

CV/interview angle:
- "Audited a systematic trading strategy by documenting the hypothesis, entry/exit logic, risk controls, backtest metrics, and model limitations."

## Week 8: Costs, Slippage, and Robustness

Dates: 2026-07-27 to 2026-08-02

Project: Backtest Validation Case Study, part 2

Goal:
- Learn why many strategies look good before costs and weak after costs.

Build:
- Extend the Week 7 strategy audit.

Tasks:
- Add transaction cost assumptions.
- Add slippage assumptions.
- Compare before-cost and after-cost results.
- Test at least 3 cost levels.
- Test at least 2 time periods.
- Test at least 2 asset universes.
- Add walk-forward or out-of-sample testing if practical.

Definition of done:
- You can explain transaction costs, slippage, turnover, and capacity.
- You can explain why a backtest is not proof a strategy will work live.
- Your strategy memo has a realistic limitations section.

Quant skill learned:
- Backtest realism.
- Strategy robustness.
- Research scepticism.

CV/interview angle:
- "Extended a systematic strategy backtest with transaction costs, slippage assumptions, robustness checks, and out-of-sample analysis."

## Week 9: Quant Research Memo

Dates: 2026-08-03 to 2026-08-09

Project: Final Portfolio Research Note

Goal:
- Turn the best project into a clean, employer-readable research memo.

Build:
- `docs/quant_research_case_study.md`

Suggested structure:
- Executive summary
- Research question
- Data used
- Data quality checks
- Method
- Backtest setup
- Results
- Risk analysis
- Robustness checks
- Limitations
- Next steps

Definition of done:
- The memo is readable by someone who does not know the repo.
- The memo includes charts or links to chart outputs.
- The memo is honest about weaknesses.

Quant skill learned:
- Communicating technical research.
- Writing for investment, risk, or model validation audiences.

CV/interview angle:
- "Produced a quant research memo covering market data quality, model assumptions, risk metrics, backtest design, performance results, robustness checks, and limitations."

## Week 10: Applications and CV Conversion

Dates: 2026-08-10 to 2026-08-16

Project: Application Pack

Goal:
- Convert the projects and GSK experience into job applications.

Build:
- `docs/quant_cv_bullet_bank.md`
- `docs/application_tracker_template.md`

Tasks:
- Write 8 to 12 project CV bullets.
- Rewrite 8 to 12 GSK bullets in finance-relevant language.
- Create versions for:
  - investment data scientist
  - model validation analyst
  - market risk analyst
  - portfolio analytics analyst
  - junior quant analyst
- Create an application tracker with columns:
  - company
  - role
  - lane
  - date applied
  - referral contact
  - CV version
  - status
  - notes
  - follow-up date

Definition of done:
- You have a finance-focused CV story.
- You have a tracker.
- You have applied to a first batch of roles.

Weekly application target:
- 2 stretch roles.
- 5 realistic quant-adjacent roles.
- 3 safety finance data roles.

## Week 11: Quant Interview Prep

Dates: 2026-08-17 to 2026-08-23

Project: Interview Practice Pack

Goal:
- Prepare for the first round of interviews and screens.

Build:
- `docs/quant_interview_practice_log.md`

Topics:
- Probability:
  - conditional probability
  - Bayes theorem
  - expected value
  - variance
  - distributions
  - coin/dice/card problems
- Statistics:
  - hypothesis testing
  - confidence intervals
  - p-values
  - regression
  - overfitting
  - cross-validation
- Finance:
  - returns
  - volatility
  - Sharpe ratio
  - drawdown
  - VaR
  - beta
  - alpha
  - transaction costs
- Coding:
  - pandas groupby
  - rolling windows
  - vectorised returns
  - simulation
  - basic optimisation

Tasks:
- Do 20 probability questions.
- Do 10 pandas/time-series coding exercises.
- Prepare 6 stories using STAR:
  - difficult dataset
  - model that failed
  - stakeholder communication
  - regulated documentation
  - debugging a modelling issue
  - learning finance quickly

Definition of done:
- You can explain each portfolio project in under 2 minutes.
- You can answer "why quant finance?" without sounding vague.
- You have examples from GSK that show judgement, not just technical skill.

## Week 12: Polish, Apply, and Network

Dates: 2026-08-24 to 2026-08-30

Project: Final Push Before Contract End

Goal:
- Make the work usable for applications before your GSK contract ends.

Tasks:
- Clean the notebooks.
- Make sure every project has a short README-style explanation.
- Put the best 2 or 3 outputs at the top of your GitHub or portfolio.
- Apply to 20 to 30 roles across the three lanes.
- Message 10 people on LinkedIn:
  - quant analysts
  - investment data scientists
  - model validation analysts
  - market risk analysts
  - alumni or apprenticeship contacts in finance
- Ask for 3 referrals where there is a real connection.

Definition of done:
- Your portfolio does not look like random tutorial work.
- Your CV clearly connects GSK data science to finance.
- You have live applications in all three lanes.

## Suggested Project Order If Time Is Tight

If you only have time for 3 projects:
1. Market Data Foundations
2. Risk Engine
3. Backtest Validation Case Study

If you only have time for 2 projects:
1. Risk Engine
2. Backtest Validation Case Study

If you only have time for 1 project:
1. Backtest Validation Case Study with costs, leakage checks, and a written research memo

## Skills Checklist

By the end of this plan, aim to be comfortable with:

Finance data:
- prices vs returns
- simple returns
- log returns
- volatility
- rolling windows
- drawdown
- Sharpe ratio
- beta
- alpha
- benchmark comparison

Market structure:
- bid/ask spread
- volume
- liquidity
- order types
- transaction costs
- slippage
- turnover

Time series:
- stationarity
- autocorrelation
- regime change
- rolling validation
- walk-forward testing
- look-ahead bias
- survivorship bias
- data leakage

Risk:
- VaR
- Expected Shortfall
- stress testing
- covariance
- correlation breakdown
- diversification
- concentration risk
- portfolio drawdown

Backtesting:
- hypothesis definition
- entry and exit rules
- train/test split by time
- out-of-sample testing
- transaction costs
- slippage
- robustness checks
- benchmark comparison
- limitations

Interview:
- probability
- expected value
- Bayes theorem
- variance
- distributions
- mental maths
- pandas
- Python functions
- explaining projects clearly

## What Not To Prioritise Yet

Do not make these the main focus before the end of August:
- Advanced stochastic calculus.
- Exotic derivatives pricing.
- Expensive certificates.
- Building a complex trading bot before you understand risk and backtesting.
- Deep reinforcement learning for trading.
- High-frequency trading infrastructure.

Those can come later. Right now, your best route is:

1. Prove strong applied statistics.
2. Prove finance data literacy.
3. Prove risk and backtesting discipline.
4. Prove you can explain your work clearly.
5. Apply across quant-adjacent roles while still taking shots at stretch quant roles.

## Final Portfolio Shape

By 2026-08-30, aim to have:

- 2 clean notebooks:
  - market data foundations
  - risk engine or portfolio construction
- 1 serious Markdown research memo:
  - backtest validation case study
- 1 CV bullet bank:
  - GSK bullets rewritten for finance
  - project bullets written for quant-adjacent roles
- 1 application tracker:
  - roles split by stretch, realistic, and safety lanes

This is enough to make you look like an applied data scientist deliberately moving into quantitative finance, rather than someone randomly applying to quant jobs.

