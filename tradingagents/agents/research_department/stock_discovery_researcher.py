from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    build_training_context,
    get_global_news,
    get_language_instruction,
)
from tradingagents.agents.utils.market_scanner_tools import (
    get_discovery_market_snapshot,
)


def create_stock_discovery_researcher(llm):
    def stock_discovery_node(state):
        current_date = state["trade_date"]
        focus_ticker = state["company_of_interest"]
        opportunity_scout_report = state.get("opportunity_scout_report", "")
        tools = [get_discovery_market_snapshot, get_global_news]

        system_message = (
            "You are the Stock Discovery Researcher for the AI research department. "
            "You run before the market analyst and decide what the rest of the "
            "business should consider today. Use the tools before writing. Produce "
            "exactly 10 ranked stocks or ETFs to investigate, with a short reason, "
            "catalyst, risk flag, and which downstream team should pay closest "
            "attention. If the user supplied a focus ticker, include whether it "
            "deserves priority against the wider opportunity set. Finish with a "
            "single line: Primary ticker to analyze next: TICKER."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants. "
                    "Use the provided tools to progress toward the stock-discovery "
                    "deliverable. You have access to the following tools: {tool_names}.\n"
                    "{system_message}\nFor your reference, the current date is "
                    "{current_date}. User supplied focus ticker: {focus_ticker}.\n\n"
                    "Automated opportunity scout brief:\n{opportunity_scout_report}"
                    "{training_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(focus_ticker=focus_ticker)
        prompt = prompt.partial(opportunity_scout_report=opportunity_scout_report)
        prompt = prompt.partial(training_context=build_training_context(state))

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        report = result.content if len(result.tool_calls) == 0 else ""

        return {
            "messages": [result],
            "stock_discovery_report": report,
        }

    return stock_discovery_node
