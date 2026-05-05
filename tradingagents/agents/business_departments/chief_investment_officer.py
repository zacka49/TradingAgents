from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_strategy_doctrine_context,
)


def create_chief_investment_officer(llm):
    def cio_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        prompt = f"""You are the Chief Investment Officer chairing the Investment Committee.

{instrument_context}

Review all research before the Trader acts. Decide whether the research plan is
credible enough to become a trade proposal, and identify what the Trader must
not ignore.

{get_strategy_doctrine_context()}

Pre-market stock discovery:
{state.get("stock_discovery_report", "")}

Analyst reports:
Market: {state.get("market_report", "")}

Sentiment: {state.get("sentiment_report", "")}

News: {state.get("news_report", "")}

Fundamentals: {state.get("fundamentals_report", "")}

AI research department:
{state.get("research_department_report", "")}

Research Manager plan:
{state.get("investment_plan", "")}

Return a concise investment committee memo with:
- committee stance
- strongest evidence
- unresolved questions
- must-follow constraints for the Trader
- escalation triggers for risk or compliance
{get_language_instruction()}
"""
        response = llm.invoke(prompt)
        return {"investment_committee_report": response.content}

    return cio_node
