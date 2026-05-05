from tradingagents.agents.utils.agent_utils import (
    build_training_context,
    build_instrument_context,
    get_language_instruction,
)


def create_training_development_coach(llm):
    def training_development_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        training_context = build_training_context(state)
        prompt = f"""You are the AI Training and Development Department.

{instrument_context}

Your responsibility is to upskill the current AI agents in the trading company.
Read the run outputs below and produce role-specific training guidance. This is
not a trading recommendation and must not override the final portfolio decision.
It is an internal curriculum for improving future agent performance.
{training_context}

Opportunity Scout:
{state.get("opportunity_scout_report", "")}

Stock Discovery Researcher:
{state.get("stock_discovery_report", "")}

Market Analyst:
{state.get("market_report", "")}

Social/Sentiment Analyst:
{state.get("sentiment_report", "")}

News Analyst:
{state.get("news_report", "")}

Fundamentals Analyst:
{state.get("fundamentals_report", "")}

Research Department:
{state.get("research_department_report", "")}

Investment debate and manager plan:
{state.get("investment_plan", "")}

Trader:
{state.get("trader_investment_plan", "")}

Trading Desk:
{state.get("trading_desk_report", "")}

Risk Office and risk debate:
{state.get("risk_office_report", "")}

Portfolio Office:
{state.get("portfolio_office_report", "")}

Operations and Compliance:
{state.get("operations_compliance_report", "")}

Evaluation Department:
{state.get("evaluation_report", "")}

Return a training memo with:
- company-wide skill gaps noticed in this run
- one role-specific lesson for each active agent/department
- concrete practice drills or checklists for the next run
- data/tooling skills each role should learn, including order flow and opportunity selection where relevant
- evaluation rubric for measuring whether each agent improved
- short "next run coaching instructions" that can be copied into future prompts

End with a Markdown table with columns: Agent, Skill to Train, Drill, Success Metric.
{get_language_instruction()}
"""
        response = llm.invoke(prompt)
        return {"training_development_report": response.content}

    return training_development_node
