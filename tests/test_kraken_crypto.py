import pytest
from brokers.kraken_adapter import KrakenBroker, normalize_kraken_asset
from main import app


def test_kraken_asset_normalization():
    assert normalize_kraken_asset("XXBT") == "BTC"
    assert normalize_kraken_asset("XBT") == "BTC"
    assert normalize_kraken_asset("XETH") == "ETH"
    assert normalize_kraken_asset("ZUSD") == "USD"
    assert normalize_kraken_asset("ZEUR") == "EUR"
    assert normalize_kraken_asset("ZGBP") == "GBP"
    assert normalize_kraken_asset("DOT.S") == "DOT"
    assert normalize_kraken_asset("ADA.M") == "ADA"
    assert normalize_kraken_asset("SOL") == "SOL"


def test_kraken_portfolio_parsing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KRAKEN_API_KEY", "dummy_key")
    monkeypatch.setenv("KRAKEN_API_SECRET", "ZHVtbXlfc2VjcmV0XzEyMzQ1Njc4OTAxMjM0NTY3ODkw")

    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "error": [],
                "result": {
                    "ZUSD": "2500.50",
                    "USDT": "100.00",
                    "XXBT": "0.15000000",
                    "XETH": "2.50000000",
                    "DOT.S": "50.00000000",
                }
            }

    monkeypatch.setattr("brokers.kraken_adapter.requests.post", lambda *args, **kwargs: MockResponse())

    broker = KrakenBroker()
    cash, positions = broker.get_portfolio()

    assert cash == 2600.50
    assert len(positions) == 3
    tickers = {p["ticker"]: p["units"] for p in positions}
    assert tickers["BTC"] == 0.15
    assert tickers["ETH"] == 2.5
    assert tickers["DOT"] == 50.0


def test_kraken_demo_order():
    broker = KrakenBroker(is_demo=True)
    res = broker.place_order(pair="BTC/USD", side="buy", ordertype="limit", volume=0.05, price=67000.0)
    assert res["status"] == "SIMULATED"
    assert res["mode"] == "DEMO"
    assert "DEMO-KRAKEN" in res["txid"][0]


def test_kraken_flask_api_endpoints(monkeypatch: pytest.MonkeyPatch):
    client = app.test_client()

    mock_pairs = {
        "error": [],
        "result": {
            "XXBTZUSD": {"wsname": "BTC/USD", "base": "XXBT", "quote": "ZUSD", "status": "online"},
            "XETHZUSD": {"wsname": "ETH/USD", "base": "XETH", "quote": "ZUSD", "status": "online"},
            "XXBTZEUR": {"wsname": "BTC/EUR", "base": "XXBT", "quote": "ZEUR", "status": "online"},
        }
    }

    mock_ticker = {
        "error": [],
        "result": {
            "XXBTZUSD": {
                "c": ["67450.00", "0.01"],
                "h": ["68200.00", "68200.00"],
                "l": ["66100.00", "66100.00"],
                "v": ["1250.0", "3400.0"],
                "p": ["67150.0", "67120.0"],
            }
        }
    }

    mock_ohlc = {
        "error": [],
        "result": {
            "XXBTZUSD": [
                [1729000000, "67000.0", "67500.0", "66800.0", "67400.0", "67200.0", "120.5", 450],
                [1729000900, "67400.0", "67600.0", "67200.0", "67550.0", "67450.0", "95.2", 380],
            ],
            "last": 1729000900
        }
    }

    def mock_get(url, *args, **kwargs):
        class Resp:
            status_code = 200
            def json(self):
                if "AssetPairs" in url:
                    return mock_pairs
                if "Ticker" in url:
                    return mock_ticker
                if "OHLC" in url:
                    return mock_ohlc
                return {"result": {}}
        return Resp()

    monkeypatch.setattr("brokers.kraken_adapter.requests.get", mock_get)

    # 1. GET /api/kraken/pairs?quote=USD
    r_pairs = client.get("/api/kraken/pairs?quote=USD&force_refresh=true")
    assert r_pairs.status_code == 200
    data_pairs = r_pairs.get_json()
    assert data_pairs["status"] == "success"
    assert len(data_pairs["pairs"]) >= 1

    # 2. GET /api/kraken/ticker?pair=XXBTZUSD
    r_tick = client.get("/api/kraken/ticker?pair=XXBTZUSD")
    assert r_tick.status_code == 200
    data_tick = r_tick.get_json()
    assert data_tick["status"] == "success"
    assert data_tick["ticker"]["last_price"] == 67450.00

    # 3. GET /api/kraken/ohlc?pair=XXBTZUSD&interval=15
    r_ohlc = client.get("/api/kraken/ohlc?pair=XXBTZUSD&interval=15")
    assert r_ohlc.status_code == 200
    data_ohlc = r_ohlc.get_json()
    assert data_ohlc["status"] == "success"
    assert len(data_ohlc["bars"]) == 2

    # 4. POST /api/kraken/order (Demo Paper)
    r_ord = client.post("/api/kraken/order", json={
        "pair": "XXBTZUSD",
        "side": "buy",
        "ordertype": "limit",
        "volume": 0.01,
        "price": 67000.0,
        "mode": "DEMO"
    })
    assert r_ord.status_code == 200
    data_ord = r_ord.get_json()
    assert data_ord["status"] == "success"
    assert data_ord["mode"] == "DEMO"
    assert data_ord["result"]["status"] == "SIMULATED"
