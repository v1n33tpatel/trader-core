import pytest
from brokers.binance_adapter import BinanceBroker
from brokers.kraken_adapter import KrakenBroker


def test_binance_broker_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_API_SECRET", raising=False)
    broker = BinanceBroker()
    cash, positions = broker.get_portfolio()
    assert cash == 0.0
    assert positions == []


def test_kraken_broker_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    broker = KrakenBroker()
    cash, positions = broker.get_portfolio()
    assert cash == 0.0
    assert positions == []


def test_binance_broker_parses_balances(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BINANCE_API_KEY", "dummy_key")
    monkeypatch.setenv("BINANCE_API_SECRET", "dummy_secret")

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "balances": [
                    {"asset": "USDT", "free": "150.50", "locked": "0.0"},
                    {"asset": "BTC", "free": "0.05", "locked": "0.01"},
                    {"asset": "ETH", "free": "0.00", "locked": "0.0"},
                ]
            }

    monkeypatch.setattr("brokers.binance_adapter.requests.get", lambda *args, **kwargs: FakeResponse())
    broker = BinanceBroker()
    cash, positions = broker.get_portfolio()

    assert cash == 150.50
    assert len(positions) == 1
    assert positions[0]["ticker"] == "BTCUSDT"
    assert positions[0]["units"] == 0.06
