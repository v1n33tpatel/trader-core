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


def test_t212_ticker_normalization():
    from brokers.t212_adapter import normalize_t212_ticker, to_t212_order_ticker

    assert normalize_t212_ticker("EQQQ_l_EQ") == "EQQQ.L"
    assert normalize_t212_ticker("VUKE_l_EQ") == "VUKE.L"
    assert normalize_t212_ticker("VUSA_l_EQ") == "VUSA.L"
    assert normalize_t212_ticker("AAPL_US_EQ") == "AAPL"
    assert normalize_t212_ticker("MSFT_US_EQ") == "MSFT"
    assert normalize_t212_ticker("EQQQ.L") == "EQQQ.L"

    # Bidirectional order ticker
    assert to_t212_order_ticker("EQQQ.L") == "EQQQ_l_EQ"
    assert to_t212_order_ticker("VUKE.L") == "VUKE_l_EQ"
    assert to_t212_order_ticker("AAPL") == "AAPL_US_EQ"
    assert to_t212_order_ticker("AAPL_US_EQ") == "AAPL_US_EQ"


def test_t212_broker_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    from brokers.t212_adapter import Trading212Broker
    monkeypatch.delenv("T212_API_KEY", raising=False)
    monkeypatch.delenv("T212_API_SECRET", raising=False)
    broker = Trading212Broker()
    cash, positions = broker.get_portfolio()
    assert cash == 0.0
    assert positions == []


def test_t212_ucits_mapping_and_target_price():
    from brokers.t212_adapter import map_us_to_ucits, calculate_ucits_target_price

    # UCITS ETF mapping
    qqq_map = map_us_to_ucits("QQQ")
    assert qqq_map["primary"] == "QQQA.L"
    assert qqq_map["sister_fund"] == "EQQQ.L"
    assert qqq_map["currency"] == "GBX"

    spy_map = map_us_to_ucits("SPY")
    assert spy_map["primary"] == "VUSA.L"
    assert spy_map["currency"] == "GBX"

    # US-to-GBX proportional limit calculation
    # QQQ drops from $709.80 to $482.65 (down ~32%)
    # If EQQQ.L spot is 54102.0p, limit should be ~36794.75p
    us_spot = 709.80
    us_val = 482.65
    ucits_spot = 54102.0
    limit = calculate_ucits_target_price(us_spot, us_val, ucits_spot)
    expected = round(54102.0 * (1.0 + (482.65 - 709.80) / 709.80), 2)
    assert limit == expected
    assert limit < ucits_spot


def test_t212_order_placement(monkeypatch: pytest.MonkeyPatch):
    from brokers.t212_adapter import Trading212Broker

    monkeypatch.setenv("T212_API_KEY", "dummy_key")
    monkeypatch.setenv("T212_API_SECRET", "dummy_secret")

    posted_payloads = []

    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"orderId": "12345", "status": "CONFIRMED"}

    def mock_post(url, headers=None, json=None, timeout=None):
        posted_payloads.append((url, json))
        return MockResponse()

    monkeypatch.setattr("brokers.t212_adapter.requests.post", mock_post)

    broker = Trading212Broker()

    # Market buy
    res_mkt = broker.place_market_order("EQQQ.L", is_buy=True, quantity=5.0)
    assert res_mkt["status"] == "CONFIRMED"
    assert posted_payloads[0][0].endswith("/equity/orders/market")
    assert posted_payloads[0][1]["ticker"] == "EQQQ_l_EQ"
    assert posted_payloads[0][1]["quantity"] == 5.0

    # Limit buy at calculated pullback price
    res_lmt = broker.place_limit_order("EQQQ.L", is_buy=True, quantity=5.0, limit_price=36794.75, time_validity="DAY")
    assert res_lmt["status"] == "CONFIRMED"
    assert posted_payloads[1][0].endswith("/equity/orders/limit")
    assert posted_payloads[1][1]["ticker"] == "EQQQ_l_EQ"
    assert posted_payloads[1][1]["quantity"] == 5.0
    assert posted_payloads[1][1]["limitPrice"] == 36794.75
    assert posted_payloads[1][1]["timeValidity"] == "DAY"
