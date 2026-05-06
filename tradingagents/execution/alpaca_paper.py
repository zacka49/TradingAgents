import os
from typing import Dict, Any

import requests

from .paper_broker import PaperBroker, OrderIntent


class AlpacaPaperBroker(PaperBroker):
    """Alpaca paper-trading adapter.

    Environment variables:
    - APCA_API_KEY_ID
    - APCA_API_SECRET_KEY
    - APCA_API_BASE_URL (default: https://paper-api.alpaca.markets)
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
        timeout: int = 20,
    ) -> None:
        self.api_key = api_key or os.getenv("APCA_API_KEY_ID")
        self.api_secret = api_secret or os.getenv("APCA_API_SECRET_KEY")
        self.base_url = (base_url or os.getenv("APCA_API_BASE_URL") or "https://paper-api.alpaca.markets").rstrip("/")
        self.timeout = timeout

        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Missing Alpaca credentials. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY."
            )

    def _headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
        }

    def submit_order(self, order: OrderIntent) -> Dict[str, Any]:
        payload = {
            "symbol": order.ticker,
            "qty": order.quantity,
            "side": order.side.lower(),
            "type": order.order_type.lower(),
            "time_in_force": order.time_in_force.lower(),
        }
        if order.order_class:
            payload["order_class"] = order.order_class
        if order.take_profit_limit_price is not None:
            payload["take_profit"] = {
                "limit_price": round(float(order.take_profit_limit_price), 2)
            }
        if order.stop_loss_stop_price is not None:
            payload["stop_loss"] = {
                "stop_price": round(float(order.stop_loss_stop_price), 2)
            }
        resp = requests.post(
            f"{self.base_url}/v2/orders",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_positions(self) -> Dict[str, Any]:
        resp = requests.get(
            f"{self.base_url}/v2/positions",
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return {"positions": resp.json()}

    def get_account(self) -> Dict[str, Any]:
        resp = requests.get(
            f"{self.base_url}/v2/account",
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_orders(self, status: str = "open") -> Dict[str, Any]:
        resp = requests.get(
            f"{self.base_url}/v2/orders",
            headers=self._headers(),
            params={
                "status": status,
                "limit": 500,
                "direction": "desc",
                "nested": "true",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return {"orders": resp.json()}

    def cancel_all_orders(self) -> Dict[str, Any]:
        resp = requests.delete(
            f"{self.base_url}/v2/orders",
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return {"orders": resp.json()}

    def close_all_positions(self, cancel_orders: bool = True) -> Dict[str, Any]:
        resp = requests.delete(
            f"{self.base_url}/v2/positions",
            headers=self._headers(),
            params={"cancel_orders": str(bool(cancel_orders)).lower()},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return {"positions": resp.json()}

    def get_clock(self) -> Dict[str, Any]:
        resp = requests.get(
            f"{self.base_url}/v2/clock",
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_latest_trade(self, symbol: str, feed: str | None = None) -> Dict[str, Any]:
        resp = requests.get(
            f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
            headers=self._headers(),
            params={"feed": feed or os.getenv("ALPACA_STOCK_FEED", "iex")},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("trade", {})
