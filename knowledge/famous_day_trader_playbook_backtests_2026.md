# Famous Day Trader Playbook Research and Proxy Backtests - 2026-05-07

Paper account research only. This is not financial advice and does not claim to
replicate any trader's private edge. The goal is to translate public playbooks
into testable rules for the TradingAgents day-trader business.

## Executive Summary

The useful lesson is not "copy famous traders." The useful lesson is to convert
their public patterns into named, auditable hypotheses: catalyst, compression,
opening range, VWAP, relative volume, pivotal levels, strict stops, and a review
label.

Across the 60-day 5-minute proxy backtest, only four long-only intraday proxies
were positive after 5 bps per side cost:

| Rank | Trader Proxy | Tested Playbook | Trades | Win Rate | Avg Trade | Total Return | Profit Factor | Max DD | System Action |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Jesse Livermore | Pivotal-point volume breakout | 118 | 48.31% | 0.0703% | 8.092% | 1.219 | 7.045% | Paper-watch; needs wider history |
| 2 | Toby Crabel | NR7 opening-range breakout | 92 | 45.65% | 0.0632% | 5.621% | 1.226 | 5.631% | Paper-watch; strong fit for day trading |
| 3 | Dan Zanger | Volume-confirmed chart breakout | 106 | 44.34% | 0.0329% | 3.085% | 1.100 | 7.449% | Paper-watch; add better daily pattern filter |
| 4 | Linda Raschke | Turtle Soup reclaim | 325 | 41.54% | 0.0072% | 1.133% | 1.023 | 21.673% | Research-only until drawdown is reduced |
| 5 | Kristjan Kullamagi | Episodic Pivot ORB | 23 | 34.78% | -0.1061% | -2.696% | 0.836 | 7.054% | Research-only; needs real news/earnings catalyst feed |
| 6 | Ross Cameron | Gap momentum ORB | 50 | 34.00% | -0.1474% | -7.630% | 0.776 | 10.795% | Research-only; broad liquid universe is the wrong habitat |
| 7 | John Carter | TTM Squeeze release | 444 | 38.96% | -0.0338% | -14.725% | 0.861 | 16.697% | Research-only; needs multi-timeframe confirmation |
| 8 | Mark Minervini | SEPA/VCP intraday breakout | 361 | 42.38% | -0.0755% | -25.237% | 0.812 | 31.483% | Research-only; this is mainly a swing playbook |
| 9 | Andrew Aziz | Stocks-in-play ORB/VWAP | 710 | 40.56% | -0.0694% | -41.210% | 0.831 | 41.276% | Tighten stocks-in-play selection before use |
| 10 | Al Brooks | Price-action trend pullback | 589 | 32.77% | -0.1263% | -52.830% | 0.551 | 52.830% | Use as human-readable chart context only |

Top ticker/proxy pockets were still interesting. Linda Raschke-style reclaim on
`SOXX` returned 8.973% over 13 trades; Livermore/Minervini-style AMD and NVDA
breakouts were also strong. This means the bot should learn symbol/regime
specialization, not global trust in a pattern.

## Backtest Method

- Script: `scripts/research_famous_day_trader_backtests.py`.
- Output artifacts: `results/research/famous_day_trader_backtests/20260506T234435Z/`.
- Generated: `2026-05-06T23:45:27Z`, which is `2026-05-07` UK time.
- Data: `yfinance`, `60d`, `5m`, regular US session only, `09:30-15:55` New York time.
- Universe: `SPY`, `QQQ`, `IWM`, `DIA`, `XLK`, `SOXX`, `SMH`, `NVDA`, `AMD`,
  `TSLA`, `COIN`, `HOOD`, `PLTR`, `META`, `AAPL`, `MSFT`, `AMZN`, `AVGO`,
  `UUP`, `FXE`, `FXY`, `FXB`, `FXA`, `GLD`, `TLT`.
- Cost model: 5 bps per side, so every round trip pays 0.10%.
- Execution model: long-only, one entry per trader proxy per ticker per day,
  stop/take-profit/EOD exits, conservative stop-before-target assumption when
  both are touched in the same later bar.
- Limitation: this is a day-trading flatten test. It penalizes swing playbooks
  such as Minervini, Zanger, Kullamagi, and Livermore, which often require
  multi-day holds. That is intentional because the current workflow is
  flat-by-default unless a separate swing mandate exists.

## The Ten Public Playbooks

### 1. Ross Cameron - Gap Momentum / Small-Cap Momentum

Public style: Ross Cameron and Warrior Trading emphasize stocks already moving,
catalysts, high relative volume, small/low-float names, morning focus, tight
risk, and roughly 2:1 reward/risk planning. Source anchors:
[Ross Cameron](https://www.rosscameron.com/) and
[Warrior Trading momentum article](https://warriortradingnews.com/2015/06/18/a-proven-momentum-day-trading-strategy/).

Proxy tested: gap up at least 2%, volume pace above 1.2x, 15-minute opening
range breakout above VWAP, bracket exit or EOD.

Result: 50 trades, -7.630% total return, 0.776 profit factor.

Interpretation: do not run this on broad large-cap ETFs as a generic setup. If
we revisit it, the scanner needs low-float, high-RVOL, news/catalyst, halt-risk,
spread, and first-pullback logic.

### 2. Andrew Aziz - Stocks-in-Play ORB / VWAP

Public style: Bear Bull Traders teaches ORBs, VWAP trading, moving-average
trends, reversals, support/resistance, psychology, risk, and account
management. Their research page also points to ORB, VWAP, stocks-in-play, and
SPY intraday momentum studies. Source anchors:
[Bear Bull Traders research](https://bearbulltraders.com/research) and
[Bear Bull Traders support](https://support.bearbulltraders.com/support/solutions/articles/67000660573-do-you-teach-technical-analysis-).

Proxy tested: 15-minute ORB, above VWAP, relative volume confirmation, EOD
flatten.

Result: 710 trades, -41.210% total return, 0.831 profit factor.

Interpretation: ORB is not enough. The bot must narrow to true stocks-in-play:
fresh catalyst, high RVOL, clean spread, strong sector/index alignment, and
avoid forcing trades every time a liquid instrument crosses its opening range.

### 3. Toby Crabel - NR7 / Opening Range Breakout

Public style: Crabel is associated with opening-range breakout, stretch, NR4,
NR7, and volatility expansion after compression. Source anchors:
[StockCharts NR7](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7),
[Traders.com ORB Part 7](https://store.traders.com/-v07-c06-orb-pdf.html), and
[JournalPlus opening range](https://journalplus.co/learn/glossary/opening-range/).

Proxy tested: previous day is NR7, then current day breaks the 15-minute opening
range high above VWAP with volume confirmation.

Result: 92 trades, +5.621% total return, 1.226 profit factor.

Interpretation: this is one of the cleanest day-trading lessons. Add a
volatility-compression filter before ORB; it reduced trade count and improved
expectancy.

### 4. Linda Raschke - Turtle Soup / Failed Breakout Reclaim

Public style: Raschke is a Market Wizard and short-term trader known for
Street Smarts playbooks such as Turtle Soup, a failed-breakout reversal
framework. Source anchors:
[Linda Raschke official site](https://lindaraschke.net/),
[XS Turtle Soup explainer](https://www.xs.com/en/blog/turtle-soup-trading/),
and [Oxfordstrat Turtle Soup](https://oxfordstrat.com/trading-strategies/turtle-soup-plus-1/).

Proxy tested: price sweeps below the prior day low, then reclaims that level
above VWAP with basic volume confirmation.

Result: 325 trades, +1.133% total return, 1.023 profit factor, but 21.673% max
drawdown.

Interpretation: useful concept, poor deployment shape. Keep as research-only
until it has stricter regime filters, smaller trade count, and a drawdown cap.

### 5. Mark Minervini - SEPA / VCP

Public style: Minervini teaches SEPA and VCP, combining specific entry timing,
leadership, trend, price action, and strict risk management. Source anchors:
[Minervini Private Access about Mark](https://minerviniprivateaccess.com/about-mark),
[Minervini Markets 360](https://www.minervini.com/), and
[PRNewswire 2021 U.S. Investing Championship release](https://www.prnewswire.com/news-releases/stock-trader-wins-us-investing-championship-a-second-time--breaks-record-301466652.html).

Proxy tested: prior close above a 20-day moving average, intraday ORB/VWAP
trigger, basic volume confirmation.

Result: 361 trades, -25.237% total return, 0.812 profit factor.

Interpretation: this proxy was too loose and too intraday. SEPA/VCP belongs in
the swing/research backlog unless the day bot can identify true leadership,
tight contraction, volume dry-up, and market-health gates.

### 6. Dan Zanger - Volume-Confirmed Chart Breakout

Public style: Zanger focuses on explosive stocks, chart patterns, high growth,
float, and breakouts highlighted in the Zanger Report. Source anchors:
[Chartpattern about Dan Zanger](https://chartpattern.com/about.cfm) and
[Chartpattern homepage](https://www.chartpattern.com/).

Proxy tested: intraday breakout above prior/20-day high, above VWAP, relative
volume and volume-pace confirmation.

Result: 106 trades, +3.085% total return, 1.100 profit factor.

Interpretation: promising but incomplete. Add better daily-pattern recognition
for cup/handle, flag, flat base, ascending triangle, and volume dry-up before
breakout.

### 7. Kristjan Kullamagi - Episodic Pivot / Breakout

Public style: Kullamagi describes breakouts, Episodic Pivots, and parabolic
setups. His EP criteria emphasize major surprise catalysts, large gaps, and
exceptional early volume. Source anchors:
[Qullamaggie about](https://qullamaggie.com/about/),
[Qullamaggie timeless setups](https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/), and
[ChartMill EP guide](https://www.chartmill.com/documentation/stock-screener/technical-analysis-trading-strategies/494-Mastering-the-Qullamaggie-Episodic-Pivot-Setup-A-Flexible-Stock-Screening-Approach).

Proxy tested: gap at least 3%, volume pace above 1.5x, ORB/VWAP trigger.

Result: 23 trades, -2.696% total return, 0.836 profit factor.

Interpretation: the proxy missed the core of the method: genuine earnings/news
surprise. Keep research-only until the news/politics and earnings event feeds
can validate catalysts.

### 8. Al Brooks - Price Action Trend Pullback

Public style: Brooks teaches price action across Emini, forex, futures, stocks,
options, and commodities, with emphasis on learning chart behavior and trading
consistently. Source anchor:
[Brooks Trading Course](https://www.brookstradingcourse.com/).

Proxy tested: first-hour uptrend, above VWAP, EMA9 above EMA20, pullback to
EMA20, bullish continuation candle.

Result: 589 trades, -52.830% total return, 0.551 profit factor.

Interpretation: our mechanical translation was far too broad. Use price-action
language for chart context and post-trade review, not autonomous entries.

### 9. John Carter - TTM Squeeze

Public style: Carter's TTM Squeeze identifies volatility compression with
Bollinger Bands inside Keltner Channels, then uses momentum to guide breakout
direction. Source anchors:
[StockCharts TTM Squeeze](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/ttm-squeeze) and
[TrendSpider TTM Squeeze overview](https://trendspider.com/learning-center/introduction-to-ttm-squeeze/).

Proxy tested: intraday squeeze-on condition, then upside release above upper
Bollinger Band, above VWAP, positive momentum.

Result: 444 trades, -14.725% total return, 0.861 profit factor.

Interpretation: intraday squeeze alone overtrades. Require daily/hourly
multi-timeframe compression, catalyst or sector alignment, and post-release
volume.

### 10. Jesse Livermore - Pivotal Point Volume Breakout

Public style: Livermore's pivotal-point idea centers on precise breakout levels,
volume confirmation, market leadership, and strong prior trends. Source anchor:
[AskLivermore pivotal point guide](https://asklivermore.com/docs/livermore).

Proxy tested: breakout above prior 20-day high, prior close above 20-day moving
average, above VWAP, relative volume and volume-pace confirmation.

Result: 118 trades, +8.092% total return, 1.219 profit factor.

Interpretation: this was the strongest proxy. It maps well to the existing
long-only paper workflow if it remains gated by volume, liquidity, index/sector
alignment, and EOD flattening.

## Lessons For The TradingAgents Business

1. Public trader names are not strategies. Convert every influence into a named
   setup, trigger, confirmation, invalidation, sizing rule, and review tag.
2. The best recent proxy results came from volume-confirmed breakouts after
   compression or at pivotal daily levels, not from generic "price went up"
   logic.
3. ORB needs context. Add filters for NR7/compression, stocks-in-play, fresh
   catalyst, volume pace, VWAP, index/sector alignment, and spread.
4. News/politics research matters most for EP/gap strategies. Without event
   validation, the bot is just buying gaps.
5. Price-action and discretionary frameworks should teach chart context and
   review language first. They should not become autonomous entries until they
   pass stricter tests.
6. Day trading should stay flat-by-default. Several famous playbooks are
   naturally swing strategies, so the current bot must not hold them overnight
   unless a separate swing mandate is added.
7. Promotion rule: a strategy should not move beyond paper-watch unless it has
   positive expectancy, profit factor above 1.15, at least 50 trades, max
   drawdown below 8%, and survives a different time window/universe.

## Concrete System Updates To Carry Forward

- Add "famous trader playbooks are hypothesis sources, not authority" to agent
  doctrine.
- Prefer these research tags for future strategy registry work:
  `pivotal_point_volume_breakout`, `nr7_opening_range_breakout`,
  `volume_confirmed_chart_breakout`, `turtle_soup_reclaim`,
  `episodic_pivot_orb`, `gap_momentum_orb`, `ttm_squeeze_release`.
- Treat `pivotal_point_volume_breakout`, `nr7_opening_range_breakout`, and
  `volume_confirmed_chart_breakout` as paper-watch candidates.
- Treat `turtle_soup_reclaim`, `episodic_pivot_orb`, `gap_momentum_orb`,
  `ttm_squeeze_release`, broad `sepa_vcp_intraday_breakout`, and generic
  `price_action_trend_pullback` as research-only until improved.

## Source Index

- Ross Cameron: https://www.rosscameron.com/
- Warrior Trading momentum strategy: https://warriortradingnews.com/2015/06/18/a-proven-momentum-day-trading-strategy/
- Bear Bull Traders research: https://bearbulltraders.com/research
- Bear Bull Traders technical analysis support: https://support.bearbulltraders.com/support/solutions/articles/67000660573-do-you-teach-technical-analysis-
- StockCharts NR7: https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7
- Traders.com Crabel ORB article listing: https://store.traders.com/-v07-c06-orb-pdf.html
- JournalPlus opening range glossary: https://journalplus.co/learn/glossary/opening-range/
- Linda Raschke official site: https://lindaraschke.net/
- XS Turtle Soup explainer: https://www.xs.com/en/blog/turtle-soup-trading/
- Oxfordstrat Turtle Soup: https://oxfordstrat.com/trading-strategies/turtle-soup-plus-1/
- Minervini Private Access about Mark: https://minerviniprivateaccess.com/about-mark
- Minervini Markets 360: https://www.minervini.com/
- PRNewswire Minervini championship release: https://www.prnewswire.com/news-releases/stock-trader-wins-us-investing-championship-a-second-time--breaks-record-301466652.html
- Chartpattern about Dan Zanger: https://chartpattern.com/about.cfm
- Qullamaggie about: https://qullamaggie.com/about/
- Qullamaggie timeless setups: https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- ChartMill Episodic Pivot guide: https://www.chartmill.com/documentation/stock-screener/technical-analysis-trading-strategies/494-Mastering-the-Qullamaggie-Episodic-Pivot-Setup-A-Flexible-Stock-Screening-Approach
- Brooks Trading Course: https://www.brookstradingcourse.com/
- StockCharts TTM Squeeze: https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/ttm-squeeze
- TrendSpider TTM Squeeze overview: https://trendspider.com/learning-center/introduction-to-ttm-squeeze/
- AskLivermore pivotal point guide: https://asklivermore.com/docs/livermore
