from tradingagents.dataflows import alpaca_realtime


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_get_snapshots_returns_symbol_keyed_payload(monkeypatch):
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append((url, params))
        return _FakeResponse(
            {
                "snapshots": {
                    "NVDA": {
                        "latestTrade": {"p": 101.5},
                        "latestQuote": {"bp": 101.4, "ap": 101.6},
                        "minuteBar": {"v": 12_000},
                    }
                }
            }
        )

    monkeypatch.setenv("APCA_API_KEY_ID", "key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "secret")
    monkeypatch.setattr(alpaca_realtime.requests, "get", fake_get)

    snapshots = alpaca_realtime.get_snapshots(["nvda"], feed="iex")

    assert snapshots["NVDA"]["latestTrade"]["p"] == 101.5
    assert calls[0][0].endswith("/v2/stocks/snapshots")
    assert calls[0][1]["symbols"] == "NVDA"
    assert calls[0][1]["feed"] == "iex"


def test_get_latest_bars_returns_symbol_keyed_payload(monkeypatch):
    def fake_get(url, headers, params, timeout):
        return _FakeResponse({"bars": {"SPY": {"c": 500.25, "v": 99}}})

    monkeypatch.setenv("APCA_API_KEY_ID", "key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "secret")
    monkeypatch.setattr(alpaca_realtime.requests, "get", fake_get)

    bars = alpaca_realtime.get_latest_bars(["spy"], feed="iex")

    assert bars == {"SPY": {"c": 500.25, "v": 99}}
