from .paper_broker import OrderIntent
from tradingagents.agents.utils.rating import parse_rating


def decision_to_order_intent(
    ticker: str,
    final_trade_decision: str,
    *,
    base_quantity: float = 1.0,
) -> OrderIntent | None:
    """Convert final decision text into a basic order intent.

    Current mapping:
    - Buy / Overweight: buy
    - Sell / Underweight: sell
    - Hold: no order (None)
    """
    rating = parse_rating(final_trade_decision)
    r = rating.lower()

    if r in ("buy", "overweight"):
        return OrderIntent(ticker=ticker, side="buy", quantity=base_quantity)
    if r in ("sell", "underweight"):
        return OrderIntent(ticker=ticker, side="sell", quantity=base_quantity)
    return None
