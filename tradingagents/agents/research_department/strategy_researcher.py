from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_indicators,
    get_language_instruction,
    get_news,
    get_stock_data,
)


def create_strategy_researcher(llm):
    def strategy_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])
        tools = [get_stock_data, get_indicators, get_news]

        system_message = (
            "You are the Strategy Researcher in an AI trading research department. "
            "Your job is to propose fresh, testable trading strategies for this "
            "instrument, not just repeat the analyst reports. Use the tools when "
            "you need price, indicator, or recent-event context. Translate the "
            "setup into concrete strategy candidates: time horizon, trigger, "
            "confirmation, invalidation, position-sizing thought, and failure mode. "
            "Flag strategies that are only hypotheses and should be paper-tested "
            "before live execution."
            + get_language_instruction()
        )

        context = (
            f"Existing analyst context:\n\n"
            f"Pre-market stock discovery report:\n{state.get('stock_discovery_report', '')}\n\n"
            f"Market report:\n{state.get('market_report', '')}\n\n"
            f"Sentiment report:\n{state.get('sentiment_report', '')}\n\n"
            f"News report:\n{state.get('news_report', '')}\n\n"
            f"Current news scout report:\n{state.get('current_news_report', '')}\n\n"
            f"Fundamentals report:\n{state.get('fundamentals_report', '')}"
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
            "strategy_report": report,
        }

    return strategy_node
