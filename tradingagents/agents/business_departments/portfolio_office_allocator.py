from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_strategy_doctrine_context,
)


def create_portfolio_office_allocator(llm):
    def portfolio_office_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        prompt = f"""You are the Portfolio Office Allocator.

{instrument_context}

The Portfolio Manager has made the final trade decision. Translate that decision
into portfolio-aware allocation guidance, including exposure, rebalancing,
monitoring, and what to review next run.

{get_strategy_doctrine_context()}

Final Portfolio Manager decision:
{state.get("final_trade_decision", "")}

Risk debate:
{state.get("risk_debate_state", {}).get("history", "")}

Risk Office memo:
{state.get("risk_office_report", "")}

Prior lessons:
{state.get("past_context", "")}

Return a portfolio-office memo with:
- allocation stance
- sizing and exposure guidance
- rebalance implications
- monitoring checklist
- post-trade review notes
{get_language_instruction()}
"""
        response = llm.invoke(prompt)
        return {"portfolio_office_report": response.content}

    return portfolio_office_node
