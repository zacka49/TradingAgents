from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class OrderIntent:
    """Normalized order request produced by portfolio decisions."""

    ticker: str
    side: str
    quantity: float
    order_type: str = "market"


class PaperBroker:
    """Minimal broker adapter interface for paper trading integrations.

    Concrete adapters (e.g. Alpaca paper, IBKR paper, etc.) should implement
    this interface and return provider-native response payloads.
    """

    def submit_order(self, order: OrderIntent) -> Dict[str, Any]:
        raise NotImplementedError

    def get_positions(self) -> Dict[str, Any]:
        raise NotImplementedError

    def get_account(self) -> Dict[str, Any]:
        raise NotImplementedError
