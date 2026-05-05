from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
    get_global_news,
    get_news,
)


def create_current_news_scout(llm):
    def current_news_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])
        stock_discovery_report = state.get("stock_discovery_report", "")
        tools = [get_news, get_global_news]

        system_message = (
            "You are the Current News Scout in an AI trading research department. "
            "Use the news tools before writing. Find the most recent company, sector, "
            "macro, central-bank, regulatory, geopolitical, and earnings-adjacent "
            "developments that could change the trading decision. Be date-specific, "
            "separate confirmed facts from interpretation, and finish with a compact "
            "catalyst table: catalyst, direction, urgency, confidence, and what the "
            "rest of the desk should verify next."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants. "
                    "Use the provided tools to progress toward the research deliverable. "
                    "You have access to the following tools: {tool_names}.\n"
                    "{system_message}\nFor your reference, the current date is "
                    "{current_date}. {instrument_context}\n\nPre-market stock "
                    "discovery brief:\n{stock_discovery_report}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)
        prompt = prompt.partial(stock_discovery_report=stock_discovery_report)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        report = result.content if len(result.tool_calls) == 0 else ""

        return {
            "messages": [result],
            "current_news_report": report,
        }

    return current_news_node
