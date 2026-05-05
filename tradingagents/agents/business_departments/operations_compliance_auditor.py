from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_strategy_doctrine_context,
)


def create_operations_compliance_auditor(llm):
    def operations_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        prompt = f"""You are the Operations and Compliance Auditor.

{instrument_context}

Audit the run before anything is treated as business-ready. Focus on data
freshness, disclosure lag, ticker correctness, tool limitations, broker/order
readiness, and whether the reasoning is auditable.

{get_strategy_doctrine_context()}

Stock discovery:
{state.get("stock_discovery_report", "")}

Copy-trading memo:
{state.get("copy_trading_report", "")}

Trading Desk plan:
{state.get("trading_desk_report", "")}

Portfolio Office memo:
{state.get("portfolio_office_report", "")}

Final decision:
{state.get("final_trade_decision", "")}

Return an operations/compliance memo with:
- pass / caution / block status
- data-quality concerns
- compliance and disclosure-lag notes
- operational checklist
- required human review before live capital
{get_language_instruction()}
"""
        response = llm.invoke(prompt)
        return {"operations_compliance_report": response.content}

    return operations_node
