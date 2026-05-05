import re

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    build_training_context,
    get_autonomous_stock_selection,
    get_global_news,
    get_language_instruction,
)
from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.utils import safe_ticker_component


def _extract_primary_ticker(report: str) -> str:
    match = re.search(
        r"Primary ticker to analyze next:\s*([A-Za-z0-9.\-_=^]+)",
        report,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return safe_ticker_component(match.group(1).upper())


def create_opportunity_scout(llm):
    def opportunity_scout_node(state):
        current_date = state["trade_date"]
        focus_ticker = state["company_of_interest"]
        tools = [get_autonomous_stock_selection, get_global_news]

        system_message = (
            "You are the Opportunity Scout. Your job is to automate what stocks "
            "or ETFs the rest of the trading company should look into today. "
            "Use the autonomous stock selection tool before writing. Use global "
            "news if it helps interpret broad market themes. Produce a ranked "
            "opportunity brief with: primary ticker, backup tickers, why each "
            "made the list, what data the downstream agents should inspect, "
            "and any data gaps. Do not recommend live capital deployment; this "
            "is research routing only. Finish with a single line: "
            "Primary ticker to analyze next: TICKER."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants. "
                    "Use the provided tools to progress toward the opportunity-routing "
                    "deliverable. You have access to the following tools: {tool_names}.\n"
                    "{system_message}\nFor your reference, the current date is "
                    "{current_date}. User supplied focus ticker: {focus_ticker}."
                    "{training_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(focus_ticker=focus_ticker)
        prompt = prompt.partial(training_context=build_training_context(state))

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        report = result.content if len(result.tool_calls) == 0 else ""
        update = {
            "messages": [result],
            "opportunity_scout_report": report,
        }

        selected_ticker = _extract_primary_ticker(report)
        if selected_ticker and get_config().get("opportunity_scout_updates_focus_ticker", True):
            update["company_of_interest"] = selected_ticker

        return update

    return opportunity_scout_node
