import pytest
from brokers.ctrader_adapter import CTraderBroker, CTRADER_INSTRUMENTS
from main import app


def test_ctrader_pip_calculation():
    # 4-decimal currency pair EURUSD: 1 pip = 0.0001
    pips_eur = CTraderBroker.calculate_pips("EURUSD", entry_price=1.0850, current_price=1.0875, is_buy=True)
    assert pips_eur == 25.0

    # Sell trade: entry 1.0875, current 1.0850 = +25 pips
    pips_eur_sell = CTraderBroker.calculate_pips("EURUSD", entry_price=1.0875, current_price=1.0850, is_buy=False)
    assert pips_eur_sell == 25.0

    # JPY pair USDJPY: 1 pip = 0.01
    pips_jpy = CTraderBroker.calculate_pips("USDJPY", entry_price=152.00, current_price=152.50, is_buy=True)
    assert pips_jpy == 50.0


def test_ctrader_demo_portfolio():
    broker = CTraderBroker(is_demo=True)
    cash, positions = broker.get_portfolio()
    assert cash >= 10000.0
    assert isinstance(positions, list)


def test_ctrader_place_and_close_demo_order():
    broker = CTraderBroker(is_demo=True)
    res = broker.place_order(symbol="EURUSD", is_buy=True, amount=1000.0, stop_loss=1.0800, take_profit=1.0950)
    assert res["status"] == "FILLED"
    assert res["demo"] is True
    assert "CT-DEMO-" in res["order_id"]

    cash, positions = broker.get_portfolio()
    assert len(positions) >= 1
    pos_id = positions[0]["position_id"]

    # Close position
    closed = broker.close_position(pos_id)
    assert closed is True


def test_ctrader_token_exchange_mocked(monkeypatch):
    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "accessToken": "mock_ctrader_access_token_123",
                "refreshToken": "mock_ctrader_refresh_token_456",
                "expiresIn": 2592000,
            }
        def raise_for_status(self): pass

    monkeypatch.setattr("requests.post", lambda url, **kwargs: MockResponse())

    broker = CTraderBroker(is_demo=True)
    token_data = broker.exchange_authorization_code(code="sample_code", redirect_uri="http://localhost/callback")
    assert token_data["accessToken"] == "mock_ctrader_access_token_123"


def test_ctrader_api_routes():
    client = app.test_client()

    # 1. Status route
    r_status = client.get("/api/ctrader/status")
    assert r_status.status_code == 200
    status_data = r_status.get_json()
    assert "status" in status_data

    # 2. Search route
    r_search = client.get("/api/search/ctrader?q=EUR")
    assert r_search.status_code == 200
    search_data = r_search.get_json()
    assert any(item["symbol"] == "EURUSD" for item in search_data)

    # 3. Portfolio route
    r_port = client.get("/api/ctrader/portfolio")
    assert r_port.status_code == 200
    port_data = r_port.get_json()
    assert "cash" in port_data
    assert "total_equity" in port_data

    # 4. Order route
    r_order = client.post("/api/ctrader/order", json={
        "symbol": "EURUSD",
        "side": "BUY",
        "units": 1000.0,
        "stop_loss": 1.0800,
        "take_profit": 1.0950
    })
    assert r_order.status_code == 200
    order_data = r_order.get_json()
    assert order_data.get("status") in ("FILLED", "SUBMITTED")
