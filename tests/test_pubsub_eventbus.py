import pytest
from unittest.mock import MagicMock, patch
from flask import Flask

from core.event_bus import EventBus, CH_SIGNALS, CH_ORDERS, CH_MARKET, CH_TELEMETRY
from core.state_store import StateStore
from src.quant_trading.pubsub_api import pubsub_blueprint
from services.strategy_scanner import StrategyScannerService
from services.order_execution_engine import OrderExecutionEngineService


@pytest.fixture
def isolated_bus():
    # Force in-memory fallback by using an invalid redis URL
    bus = EventBus(redis_url="redis://localhost:99999/0")
    yield bus
    bus.close()


@pytest.fixture
def pubsub_client(isolated_bus):
    app = Flask(__name__)
    app.register_blueprint(pubsub_blueprint)
    app.config["TESTING"] = True
    with patch("src.quant_trading.pubsub_api.get_event_bus", return_value=isolated_bus):
        with app.test_client() as client:
            yield client


def test_event_bus_in_memory_pubsub(isolated_bus):
    assert isolated_bus.backend == "in_memory"
    assert not isolated_bus.is_redis()

    received = []

    def on_signal(msg):
        received.append(msg)

    isolated_bus.subscribe(CH_SIGNALS, on_signal)
    payload = {"symbol": "BTCUSDT", "action": "BUY", "price": 67000.0}
    isolated_bus.publish(CH_SIGNALS, payload)

    assert len(received) == 1
    assert received[0]["symbol"] == "BTCUSDT"

    # Verify event history caching
    history = isolated_bus.get_recent_events(channel=CH_SIGNALS)
    assert len(history) == 1
    assert history[0]["channel"] == CH_SIGNALS
    assert history[0]["payload"]["symbol"] == "BTCUSDT"

    status = isolated_bus.get_status()
    assert status["backend"] == "in_memory"
    assert status["total_cached_events"] >= 1
    assert CH_SIGNALS in status["subscribed_channels"]


def test_pubsub_api_endpoints(pubsub_client, isolated_bus):
    # Test GET /api/pubsub/status
    res = pubsub_client.get("/api/pubsub/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["backend"] == "in_memory"

    # Test POST /api/pubsub/publish
    res = pubsub_client.post(
        "/api/pubsub/publish",
        json={"channel": CH_SIGNALS, "message": {"test": "signal", "value": 42}}
    )
    assert res.status_code == 200
    assert res.get_json()["status"] == "success"

    # Test GET /api/pubsub/events
    res = pubsub_client.get(f"/api/pubsub/events?channel={CH_SIGNALS}")
    assert res.status_code == 200
    events_data = res.get_json()
    assert events_data["count"] >= 1
    assert any(e["payload"].get("value") == 42 for e in events_data["events"])


def test_strategy_scanner_emits_signal(isolated_bus):
    scanner = StrategyScannerService(symbols=["ETHUSDT"], event_bus=isolated_bus)

    # Mock feed & strategy evaluation to return actionable BUY
    scanner.feed.fetch_klines = MagicMock(return_value=[{"close": 2650.0}])
    scanner.strategy.evaluate_market = MagicMock(return_value=("BUY", "RSI oversold + FVG fill"))

    signals_caught = []
    isolated_bus.subscribe(CH_SIGNALS, lambda s: signals_caught.append(s))

    sig = scanner.evaluate_symbol("ETHUSDT")
    assert sig is not None
    assert sig["symbol"] == "ETHUSDT"
    assert sig["action"] == "BUY"
    assert sig["entry_price"] == 2650.0
    assert sig["risk_reward_ratio"] >= 2.0
    assert sig["stop_loss"] < 2650.0
    assert sig["take_profit"] > 2650.0

    # Ensure event was published to the bus
    assert len(signals_caught) == 1
    assert signals_caught[0]["signal_id"] == sig["signal_id"]


def test_order_execution_engine_processes_signal(tmp_path, isolated_bus):
    db_file = str(tmp_path / "test_engine_state.db")
    test_store = StateStore(db_path=db_file)

    with patch("services.order_execution_engine.StateStore", lambda: test_store):
        engine = OrderExecutionEngineService(event_bus=isolated_bus, is_demo=True)
        engine.state_store = test_store
        engine.start()

        orders_caught = []
        isolated_bus.subscribe(CH_ORDERS, lambda o: orders_caught.append(o))

        signal_payload = {
            "signal_id": "SIG-TEST1234",
            "symbol": "BTCUSDT",
            "action": "BUY",
            "entry_price": 67000.0,
            "stop_loss": 65995.0,
            "take_profit": 69211.0,
        }

        # Publish signal on bus -> engine listener intercepts and executes
        isolated_bus.publish(CH_SIGNALS, signal_payload)

        # Check order event was published
        assert len(orders_caught) == 1
        ord_event = orders_caught[0]
        assert ord_event["signal_id"] == "SIG-TEST1234"
        assert ord_event["symbol"] == "BTCUSDT"
        assert ord_event["side"] == "BUY"
        assert ord_event["status"] == "FILLED_DEMO"
        assert ord_event["broker"] == "binance"

        # Verify notional sizing cap <= $50
        notional = ord_event["units"] * ord_event["price"]
        assert notional <= 50.05

        # Verify recorded in StateStore positions
        positions = test_store.get_positions()
        assert len(positions) >= 1
        assert any(p["position_id"] == ord_event["order_id"] for p in positions)
