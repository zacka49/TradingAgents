from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_strategy_doctrine_context,
)


def create_trading_desk_strategist(llm):
    def trading_desk_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        prompt = f"""You are the Trading Desk Strategist.

{instrument_context}

Turn the Trader's transaction proposal into an execution plan that a real desk
could act on. Focus on timing, liquidity, entry method, stop handling, order
type, and what would make the desk stand down.

{get_strategy_doctrine_context()}

Investment Committee memo:
{state.get("investment_committee_report", "")}

Trader proposal:
{state.get("trader_investment_plan", "")}

Market report:
{state.get("market_report", "")}

Strategy Researcher memo:
{state.get("strategy_report", "")}

Return a desk plan with:
- execution stance
- entry/exit plan
- liquidity and slippage concerns
- order handling notes
- conditions that cancel or delay execution
{get_language_instruction()}
"""
        response = llm.invoke(prompt)
        return {"trading_desk_report": response.content}

    return trading_desk_node
