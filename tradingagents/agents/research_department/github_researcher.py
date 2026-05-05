from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.agents.utils.github_research_tools import (
    get_popular_financial_ai_repos,
)


def create_github_researcher(llm):
    def github_research_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])
        tools = [get_popular_financial_ai_repos]

        system_message = (
            "You are the GitHub Researcher in an AI trading research department. "
            "Your job is to monitor popular open-source financial AI, trading, "
            "agent, data, and backtesting repositories and extract lessons the "
            "business can safely learn from. Use the GitHub repository scout "
            "tool before writing. Focus on reusable architecture, validation, "
            "dry-run, observability, risk controls, and data adapters. Do not "
            "recommend copying code without license review, tests, and a clear "
            "business reason. Finish with: repo, lesson, adoption status "
            "(`adopt_now`, `prototype_next`, `watch`, or `reject_for_now`), and "
            "next implementation step."
            + get_language_instruction()
        )

        context = (
            f"Current research department context:\n\n"
            f"Pre-market stock discovery report:\n{state.get('stock_discovery_report', '')}\n\n"
            f"Current news scout report:\n{state.get('current_news_report', '')}\n\n"
            f"Strategy report:\n{state.get('strategy_report', '')}\n\n"
            f"Copy-trading report:\n{state.get('copy_trading_report', '')}\n\n"
            f"Technology scout report:\n{state.get('technology_scout_report', '')}"
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants. "
                    "Use the provided tools to progress toward the research deliverable. "
                    "You have access to the following tools: {tool_names}.\n"
                    "{system_message}\nFor your reference, the current date is "
                    "{current_date}. {instrument_context}\n\n{context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)
        prompt = prompt.partial(context=context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        report = result.content if len(result.tool_calls) == 0 else ""

        return {
            "messages": [result],
            "github_research_report": report,
        }

    return github_research_node
