# AI Research Department

This project now runs a full AI research department between the core analyst team and the bull/bear debate.
The rest of the business is also expanded into downstream AI departments: Investment Committee, Trading Desk, Risk Office, Portfolio Office, Operations/Compliance, and Evaluation.

## Department Roles

| Agent | Job | Main outputs |
| --- | --- | --- |
| Stock Discovery Researcher | Runs before the market analyst and screens a liquid starter universe plus global news. | Exactly 10 stocks/ETFs for the rest of the business to consider, with catalyst, risk, owner team, and primary ticker line. |
| Current News Scout | Finds recent company, sector, macro, regulatory, and earnings-adjacent developments. | Catalyst table with direction, urgency, confidence, and verification needs. |
| Strategy Researcher | Converts market data and analyst reports into testable strategies. | Setup, trigger, confirmation, invalidation, sizing thought, and paper-test notes. |
| Copy Trading Researcher | Reviews public politician trades, SEC disclosure filings, insider transactions, and holder snapshots. | Who moved, what changed, disclosure lag, and whether copying the flow improves or worsens risk. |
| GitHub Researcher | Monitors popular financial AI, trading, data, agent, and backtesting repositories. | Repo lessons, adoption status, license caution, and next implementation step. |
| Research Director | Synthesizes the specialist memos into a CEO-ready brief. | Highest-value signals, conflicts, limitations, and debate questions for bull/bear researchers. |

## Recommended Free/Low-Cost AI Stack

Checked online on 2026-05-04.

| Department member | Recommended AI/API | Why this fit |
| --- | --- | --- |
| Current News Scout | Google Gemini 2.5 Flash-Lite or Gemini 2.5 Flash | Google lists free input/output tokens for both 2.5 Flash-Lite and 2.5 Flash, with free-tier Google Search grounding limits on those models. Good first choice for news synthesis and dated catalyst work. |
| Strategy Researcher | Gemini 2.5 Flash, with Groq `qwen/qwen3-32b` as a speed option | Flash gives long-context reasoning at low/free-tier cost. Groq publishes free-plan limits and very high throughput models, useful for repeated strategy ideation. |
| Copy Trading Researcher | Gemini 2.5 Flash-Lite for extraction/summarization | This job is mostly structured extraction and cautionary interpretation, so the cheaper Gemini tier is enough. Use public data tools rather than paying for a copy-trading data vendor at first. |
| GitHub Researcher | Local Ollama quick model or Gemini 2.5 Flash-Lite | This job uses a GitHub scout tool with a curated fallback list, so it only needs cheap summarization and architecture judgment. |
| Research Director | Gemini 2.5 Flash, or OpenRouter `openrouter/free` as a fallback | The director needs synthesis across multiple reports. Gemini Flash is the default; OpenRouter's free router can pick free models that match requested capabilities such as structured output/tool calling. |

## Data Sources

- Privacy note: Google's Gemini free tier lists content as used to improve products. Use paid tier or another provider if you do not want research prompts used that way.
- SEC EDGAR: official JSON APIs do not require auth keys, but SEC fair-access rules require a declared `User-Agent` and currently cap automated access at 10 requests/second. Set `SEC_USER_AGENT` before using the SEC disclosure tool.
- Congressional trades: the copy-trading agent checks public House/Senate community datasets when available and records source failures instead of failing the whole run.
- CapitolTrades and Quiver: useful free public dashboards for manual checking and future integrations. Quiver's free visitor tier includes live alternative datasets, while premium unlocks copy-trading/backtesting features.
- News/search: Tavily gives 1,000 free monthly credits and NewsAPI's free developer plan provides 100 requests/day for development/testing, but NewsAPI's free plan has a 24-hour article delay and is not for production.

## Suggested Default Config

```python
config["llm_provider"] = "google"
config["quick_think_llm"] = "gemini-2.5-flash-lite"
config["deep_think_llm"] = "gemini-2.5-flash"
config["stock_discovery_enabled"] = True
config["research_department_enabled"] = True
config["github_research_enabled"] = True
```

For a no-cost fallback experiment:

```python
config["llm_provider"] = "openrouter"
config["quick_think_llm"] = "openrouter/free"
config["deep_think_llm"] = "openrouter/free"
```

For very fast cheap/free-tier testing:

```python
config["llm_provider"] = "groq"
config["quick_think_llm"] = "openai/gpt-oss-20b"
config["deep_think_llm"] = "openai/gpt-oss-120b"
```

## Sources

- [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)
- [Groq supported models](https://console.groq.com/docs/models)
- [OpenRouter free router](https://openrouter.ai/openrouter/free)
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC fair access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- [Tavily credits and pricing](https://docs.tavily.com/documentation/api-credits)
- [NewsAPI pricing](https://newsapi.org/pricing)
- [CapitolTrades](https://www.capitoltrades.com/)
- [Quiver Quantitative](https://www.quiverquant.com/)
- [GitHub repository search API](https://docs.github.com/en/rest/search/search)
- [GitHub search syntax](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories)
