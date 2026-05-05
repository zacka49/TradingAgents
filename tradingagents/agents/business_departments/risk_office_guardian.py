from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_strategy_doctrine_context,
)


def create_risk_office_guardian(llm):
    def risk_office_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        prompt = f"""You are the independent Risk Office Guardian.

{instrument_context}

Before the risk debate begins, issue a risk-office memo that frames the trade's
main drawdown, concentration, liquidity, volatility, macro, and event risks.
Your job is not to approve the trade; it is to define what risk must be debated
and what guardrails should bind any final decision.

{get_strategy_doctrine_context()}

Investment Committee memo:
{state.get("investment_committee_report", "")}

Trader proposal:
{state.get("trader_investment_plan", "")}

Trading Desk plan:
{state.get("trading_desk_report", "")}

Research department brief:
{state.get("research_department_report", "")}

Return a risk-office memo with:
- key risk exposures
- stress scenarios
- max loss / invalidation thinking
- sizing guardrails
- debate questions for aggressive, conservative, and neutral analysts
{get_language_instruction()}
"""
        response = llm.invoke(prompt)
        return {"risk_office_report": response.content}

    return risk_office_node
