"""Notification adapters for autonomous paper trading."""

from .whatsapp import NotificationResult, send_whatsapp_message, send_trade_notification

__all__ = [
    "NotificationResult",
    "send_trade_notification",
    "send_whatsapp_message",
]

