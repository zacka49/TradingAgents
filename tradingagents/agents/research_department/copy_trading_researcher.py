from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_insider_transactions,
    get_language_instruction,
)
from tradingagents.agents.utils.copy_trading_tools import (
    get_congressional_trades,
    get_institutional_holders,
    get_sec_disclosure_filings,
)


def create_copy_trading_researcher(llm):
    def copy_trading_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])
        tools = [
            get_congressional_trades,
            get_institutional_holders,
            get_sec_disclosure_filings,
            get_insider_transactions,
        ]

        system_message = (
            "You are the Copy Trading Researcher in an AI trading research "
            "department. Look for public signals from politicians, famous or "
            "institutional investors, company insiders, and large holders. Use the "
            "tools before writing. Treat these disclosures as lagging, noisy public "
            "records, not automatic buy/sell instructions. Your memo must explain "
            "who moved, what they did, disclosure lag, whether the action aligns "
            "with price/news/fundamentals, and whether copying the flow would add "
            "or reduce risk."
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
                    "{current_date}. {instrument_context}\n\n"
                    "Pre-market stock discovery context:\n{stock_discovery_report}\n\n"
                    "Current news context:\n{current_news_report}\n\n"
                    "Strategy context:\n{strategy_report}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)
        prompt = prompt.partial(stock_discovery_report=state.get("stock_discovery_report", ""))
        prompt = prompt.partial(current_news_report=state.get("current_news_report", ""))
        prompt = prompt.partial(strategy_report=state.get("strategy_report", ""))

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        report = result.content if len(result.tool_calls) == 0 else ""

        return {
            "messages": [result],
            "copy_trading_report": report,
        }

    return copy_trading_node
