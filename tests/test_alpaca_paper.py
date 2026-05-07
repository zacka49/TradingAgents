from tradingagents.execution.alpaca_paper import AlpacaPaperBroker


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_alpaca_paper_close_all_positions_cancels_orders_first(monkeypatch):
    calls = []

    def fake_delete(url, headers, params=None, timeout=20):
        calls.append((url, params))
        return _FakeResponse([{"symbol": "SPY", "status": 200}])

    monkeypatch.setattr("tradingagents.execution.alpaca_paper.requests.delete", fake_delete)

    broker = AlpacaPaperBroker(api_key="key", api_secret="secret", base_url="https://paper-api.alpaca.markets")
    response = broker.close_all_positions(cancel_orders=True)

    assert response == {"positions": [{"symbol": "SPY", "status": 200}]}
    assert calls == [
        ("https://paper-api.alpaca.markets/v2/positions", {"cancel_orders": "true"})
    ]


def test_alpaca_paper_cancel_all_orders(monkeypatch):
    calls = []

    def fake_delete(url, headers, params=None, timeout=20):
        calls.append((url, params))
        return _FakeResponse([{"id": "order-1", "status": 200}])

    monkeypatch.setattr("tradingagents.execution.alpaca_paper.requests.delete", fake_delete)

    broker = AlpacaPaperBroker(api_key="key", api_secret="secret", base_url="https://paper-api.alpaca.markets")
    response = broker.cancel_all_orders()

    assert response == {"orders": [{"id": "order-1", "status": 200}]}
    assert calls == [("https://paper-api.alpaca.markets/v2/orders", None)]


def test_alpaca_paper_cancel_order(monkeypatch):
    calls = []

    def fake_delete(url, headers, params=None, timeout=20):
        calls.append((url, params))
        return _FakeResponse({"id": "order-1", "status": "canceled"})

    monkeypatch.setattr("tradingagents.execution.alpaca_paper.requests.delete", fake_delete)

    broker = AlpacaPaperBroker(api_key="key", api_secret="secret", base_url="https://paper-api.alpaca.markets")
    response = broker.cancel_order("order-1")

    assert response == {"id": "order-1", "status": "canceled"}
    assert calls == [("https://paper-api.alpaca.markets/v2/orders/order-1", None)]
