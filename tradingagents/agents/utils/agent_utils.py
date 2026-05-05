from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)
from tradingagents.agents.utils.autonomous_discovery_tools import (
    get_autonomous_stock_selection,
)
from tradingagents.agents.utils.order_flow_tools import (
    get_live_order_flow_snapshot,
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Only applied to user-facing agents (analysts, portfolio manager).
    Internal debate agents stay in English for reasoning quality.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )


def build_training_context(state) -> str:
    """Return recent role-training lessons for prompt injection."""
    context = state.get("training_context", "") if isinstance(state, dict) else ""
    if not context:
        return ""
    return (
        "\n\nAI Training and Development guidance from prior runs:\n"
        f"{context}\n"
        "Apply the lessons relevant to your specific role, but do not let them "
        "override current evidence."
    )


def get_strategy_doctrine_context() -> str:
    """Return the current trading-strategy doctrine for decision agents.

    Keep this concise: the full research file lives in
    ``knowledge/trading_strategy_deep_dive_2026.md``.
    """
    return """

Trading Strategy Doctrine:
- Regime before signal: classify trend, range, volatility, liquidity, catalyst,
  and market-index alignment before choosing any setup.
- Deploy only tested long-side paper strategies for autonomous execution:
  momentum breakout, opening-range breakout, and selective relative-strength
  continuation. VWAP reclaim, range reversion, fading, news shock, and scalping
  are watch/research modes unless backtests and live-data gates promote them.
- A trade needs a named setup, trigger, confirmation, invalidation, position-size
  logic, expected holding period, and post-trade review label.
- Liquidity/data gates are mandatory: fresh price, clean spread, sufficient
  volume, market open, no known halt/stale feed, and no duplicate working order.
- Risk is part of the strategy: bracket exits, no averaging down, stop before
  entry, reward/risk target, order-notional cap, portfolio exposure cap, and
  stand-down after failed data quality or excessive drawdown.
- Order flow and VWAP are confirmations, not standalone reasons to trade. Use
    delta, large prints, absorption, and price vs VWAP only when the feed quality
  is explicit and current.
"""


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
