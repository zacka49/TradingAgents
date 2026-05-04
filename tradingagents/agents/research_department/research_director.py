from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)


def create_research_director(llm):
    def research_director_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        prompt = f"""You are the Research Director for an AI trading research department.

{instrument_context}

Synthesize the specialist memos below into a CEO-ready research department brief.
Your brief should:
- identify the highest-value signals and what changed today
- reconcile conflicts between news, strategy, copy-trading, and analyst work
- call out data freshness or disclosure-lag limitations
- hand the bull and bear researchers a short list of questions they must debate
- end with a Markdown table of signal, impact, confidence, and owner

Current News Scout:
{state.get("current_news_report", "")}

Strategy Researcher:
{state.get("strategy_report", "")}

Copy Trading Researcher:
{state.get("copy_trading_report", "")}

Core analyst reports:
Market: {state.get("market_report", "")}

Sentiment: {state.get("sentiment_report", "")}

News: {state.get("news_report", "")}

Fundamentals: {state.get("fundamentals_report", "")}
{get_language_instruction()}
"""

        response = llm.invoke(prompt)
        return {"research_department_report": response.content}

    return research_director_node
