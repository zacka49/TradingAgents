from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .paper_broker import OrderIntent


@dataclass
class PolicyDecision:
    allow: bool
    reason: str
    order_notional_usd: float | None = None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_order_policy(
    *,
    intent: OrderIntent,
    account: Dict[str, Any],
    market_open: bool,
    latest_price: float | None,
    config: Dict[str, Any],
) -> PolicyDecision:
    allowed_symbols = {s.upper() for s in config.get("allowed_symbols", []) if str(s).strip()}
    if allowed_symbols and intent.ticker.upper() not in allowed_symbols:
        return PolicyDecision(False, "symbol_not_allowed")

    if config.get("enforce_market_open", True) and not market_open:
        return PolicyDecision(False, "market_closed")

    if latest_price is None or latest_price <= 0:
        return PolicyDecision(False, "missing_live_price")

    order_notional = float(intent.quantity) * float(latest_price)
    max_order_notional = float(config.get("max_order_notional_usd", 250.0))
    if order_notional > max_order_notional:
        return PolicyDecision(False, "order_notional_exceeds_limit", order_notional)

    buying_power = _safe_float(account.get("buying_power"))
    if intent.side.lower() == "buy" and buying_power is not None and order_notional > buying_power:
        return PolicyDecision(False, "insufficient_buying_power", order_notional)

    max_position_notional = float(config.get("max_position_notional_usd", 1000.0))
    if intent.side.lower() == "buy" and order_notional > max_position_notional:
        return PolicyDecision(False, "position_notional_exceeds_limit", order_notional)

    return PolicyDecision(True, "approved", order_notional)
