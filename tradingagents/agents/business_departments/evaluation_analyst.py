from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)


def create_evaluation_analyst(llm):
    def evaluation_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        prompt = f"""You are the Evaluation Department Analyst.

{instrument_context}

Close the business loop. Decide how this run should be measured after the fact,
what should be compared against a baseline, and what the next paper-trading or
backtest review should inspect.

Final decision:
{state.get("final_trade_decision", "")}

Portfolio Office memo:
{state.get("portfolio_office_report", "")}

Operations and Compliance memo:
{state.get("operations_compliance_report", "")}

Research department brief:
{state.get("research_department_report", "")}

Return an evaluation memo with:
- benchmark and holding-period suggestion
- metrics to track
- A/B test idea for agent/model comparison
- what would prove this decision right or wrong
- learning note for the next run
{get_language_instruction()}
"""
        response = llm.invoke(prompt)
        return {"evaluation_report": response.content}

    return evaluation_node
