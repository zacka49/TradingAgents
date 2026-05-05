from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict

import requests


@dataclass(frozen=True)
class NotificationResult:
    sent: bool
    reason: str
    provider_id: str | None = None


def _missing_env() -> list[str]:
    required = [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_FROM",
        "WHATSAPP_TO",
    ]
    return [name for name in required if not os.getenv(name)]


def send_whatsapp_message(
    body: str,
    *,
    to: str | None = None,
    from_: str | None = None,
    timeout: int = 20,
) -> NotificationResult:
    """Send a WhatsApp message through Twilio's Messages API."""
    missing = _missing_env()
    if missing:
        return NotificationResult(False, f"missing_env:{','.join(missing)}")

    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    to_value = to or os.environ["WHATSAPP_TO"]
    from_value = from_ or os.environ["TWILIO_WHATSAPP_FROM"]

    if not to_value.startswith("whatsapp:"):
        to_value = f"whatsapp:{to_value}"
    if not from_value.startswith("whatsapp:"):
        from_value = f"whatsapp:{from_value}"

    resp = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data={
            "From": from_value,
            "To": to_value,
            "Body": body[:1500],
        },
        auth=(account_sid, auth_token),
        timeout=timeout,
    )
    if resp.status_code >= 400:
        return NotificationResult(
            False,
            f"twilio_http_{resp.status_code}:{resp.text[:180]}",
        )
    payload = resp.json()
    return NotificationResult(True, "sent", provider_id=payload.get("sid"))


def send_trade_notification(
    *,
    strategy_profile: str,
    order: Any,
    account: Dict[str, Any] | None = None,
) -> NotificationResult:
    """Send a compact notification for one submitted paper order."""
    response = order.order_response or {}
    account = account or {}
    lines = [
        "TradingAgents paper trade submitted",
        f"Strategy: {strategy_profile}",
        f"Order: {order.side.upper()} {order.quantity} {order.ticker}",
        f"Est notional: ${order.estimated_notional_usd:.2f}",
        f"Entry ref: ${order.latest_price:.2f}",
        f"Stop: {order.stop_loss_price or 'n/a'}",
        f"Take profit: {order.take_profit_price or 'n/a'}",
        f"Alpaca status: {response.get('status', 'submitted')}",
        f"Order id: {response.get('id', 'n/a')}",
    ]
    if account.get("portfolio_value"):
        lines.append(f"Paper portfolio value: ${account.get('portfolio_value')}")
    return send_whatsapp_message("\n".join(lines))

