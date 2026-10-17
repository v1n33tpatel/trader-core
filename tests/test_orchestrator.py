import pytest
from unittest.mock import MagicMock, patch
from flask import Flask

from feeds.orchestrator import AIOrchestrator, OLLAMA_LOCK
from src.quant_trading.orchestrator_api import orchestrator_blueprint
from core.state_store import StateStore


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(orchestrator_blueprint)
    app.config["TESTING"] = True
    db_file = str(tmp_path / "test_trader_state.db")

    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("quant_trading.orchestrator_api.StateStore", lambda: StateStore(db_path=db_file)), \
         patch("feeds.orchestrator.StateStore", lambda: StateStore(db_path=db_file)):
        with app.test_client() as test_client:
            yield test_client


# =============================================================================
# 1. AIOrchestrator Unit Tests
# =============================================================================

def test_tool_schemas():
    orch = AIOrchestrator()
    schemas = orch.get_tool_schemas()
    assert isinstance(schemas, list)
    assert len(schemas) >= 6

    tool_names = [s["function"]["name"] for s in schemas]
    assert "get_market_intelligence" in tool_names
    assert "evaluate_price_action" in tool_names
    assert "get_portfolio_and_risk" in tool_names
    assert "switch_strategy" in tool_names
    assert "set_automation_mode" in tool_names
    assert "submit_order" in tool_names


def test_probe_orchestrator_online():
    orch = AIOrchestrator(base_url="http://10.10.10.15:11434")
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("requests.get", return_value=mock_resp):
        res = orch.probe_orchestrator()
        assert res["status"] == "online"
        assert res["latency_ms"] >= 0.0
        assert res["type"] == "ollama"


def test_probe_orchestrator_offline():
    orch = AIOrchestrator(base_url="http://10.10.10.15:11434")
    with patch("requests.get", side_effect=Exception("Connection refused")):
        res = orch.probe_orchestrator()
        assert res["status"] == "offline"
        assert "error" in res


def test_execute_tool_portfolio_and_risk(tmp_path):
    db_file = str(tmp_path / "test_trader_state.db")
    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("feeds.orchestrator.StateStore", lambda: StateStore(db_path=db_file)):
        orch = AIOrchestrator()
        res = orch.execute_tool("get_portfolio_and_risk", {})
        assert "environment_mode" in res
        assert "is_demo" in res
        assert "risk_sentinel" in res
        assert res["risk_sentinel"]["max_order_usd"] == 50.0


def test_execute_tool_switch_strategy(tmp_path):
    db_file = str(tmp_path / "test_trader_state.db")
    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("feeds.orchestrator.StateStore", lambda: StateStore(db_path=db_file)):
        orch = AIOrchestrator()
        # Valid strategy
        res = orch.execute_tool("switch_strategy", {"strategy_id": "atr_trailing_breakout"})
        assert res["status"] == "success"
        assert res["active_strategy"] == "atr_trailing_breakout"

        # Invalid strategy
        bad_res = orch.execute_tool("switch_strategy", {"strategy_id": "nonexistent_strat_99"})
        assert bad_res["status"] == "error"


def test_execute_tool_set_automation_mode(tmp_path):
    db_file = str(tmp_path / "test_trader_state.db")
    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("feeds.orchestrator.StateStore", lambda: StateStore(db_path=db_file)):
        orch = AIOrchestrator()
        res = orch.execute_tool("set_automation_mode", {"mode": "reactive"})
        assert res["status"] == "success"
        assert res["automation_mode"] == "reactive"

        bad_res = orch.execute_tool("set_automation_mode", {"mode": "invalid_mode"})
        assert bad_res["status"] == "error"


def test_execute_tool_submit_order_demo(tmp_path):
    db_file = str(tmp_path / "test_trader_state.db")
    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("feeds.orchestrator.StateStore", lambda: StateStore(db_path=db_file)):
        orch = AIOrchestrator()
        res = orch.execute_tool("submit_order", {
            "symbol": "ETH",
            "side": "BUY",
            "target_allocation_usd": 50.0
        })
        assert res["status"] == "executed"
        assert res["mode"] == "DEMO"
        assert res["symbol"] == "ETH"
        assert res["side"] == "BUY"
        assert res["units"] > 0


def test_execute_unknown_tool():
    orch = AIOrchestrator()
    res = orch.execute_tool("invalid_tool_action", {})
    assert res["status"] == "error"
    assert "Unknown tool" in res["message"]


def test_run_executive_synthesis(tmp_path):
    db_file = str(tmp_path / "test_trader_state.db")
    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("feeds.orchestrator.StateStore", lambda: StateStore(db_path=db_file)):
        orch = AIOrchestrator()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": '{"symbol": "ETH", "executive_action": "HOLD", "confidence": 0.8, "setup_summary": "Waiting for confirmed BOS"}'
        }

        with patch("requests.post", return_value=mock_resp):
            res = orch.run_executive_synthesis(symbol="ETH")
            assert res["symbol"] == "ETH"
            assert "directive" in res
            assert res["directive"]["executive_action"] == "HOLD"
            assert "telemetry" in res


def test_execute_command_fastpaths(tmp_path):
    db_file = str(tmp_path / "test_trader_state.db")
    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("feeds.orchestrator.StateStore", lambda: StateStore(db_path=db_file)):
        orch = AIOrchestrator()

        res_mode = orch.execute_command("switch to reactive mode")
        assert res_mode["status"] == "success"
        assert res_mode["automation_mode"] == "reactive"

        res_port = orch.execute_command("check portfolio and open positions")
        assert "environment_mode" in res_port


# =============================================================================
# 2. REST API Endpoints Tests
# =============================================================================

def test_api_orchestrator_status(client):
    with patch("feeds.orchestrator.AIOrchestrator.probe_orchestrator", return_value={"status": "online", "latency_ms": 15.2, "type": "ollama"}):
        res = client.get("/api/orchestrator/status")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "online"
        assert data["latency_ms"] == 15.2


def test_api_orchestrator_tools(client):
    res = client.get("/api/orchestrator/tools")
    assert res.status_code == 200
    data = res.get_json()
    assert "tools" in data
    assert data["total_tools"] >= 6


def test_api_orchestrator_tools_call(client):
    res = client.post("/api/orchestrator/tools/call", json={
        "name": "get_portfolio_and_risk",
        "arguments": {}
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["tool"] == "get_portfolio_and_risk"
    assert "result" in data

    # Error case: missing name
    bad_res = client.post("/api/orchestrator/tools/call", json={})
    assert bad_res.status_code == 400


def test_api_orchestrator_command(client):
    res = client.post("/api/orchestrator/command", json={"command": "switch to predictive mode"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["result"]["automation_mode"] == "predictive"

    bad_res = client.post("/api/orchestrator/command", json={})
    assert bad_res.status_code == 400


def test_api_orchestrator_synthesize(client):
    with patch("feeds.orchestrator.AIOrchestrator.run_executive_synthesis") as mock_synth:
        mock_synth.return_value = {
            "symbol": "BTC",
            "directive": {"executive_action": "HOLD", "confidence": 0.9}
        }
        res = client.post("/api/orchestrator/synthesize", json={"symbol": "BTC"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["symbol"] == "BTC"
        assert data["directive"]["executive_action"] == "HOLD"


def test_api_orchestrator_config(client):
    payload = {
        "orchestrator_url": "http://192.168.2.15:8080",
        "orchestrator_model": "deepseek-r1:7b",
        "open_webui_api_key": "sk-owui-secret-key-123"
    }
    with patch("feeds.orchestrator.AIOrchestrator.probe_orchestrator", return_value={"status": "online", "latency_ms": 12.0}):
        res = client.post("/api/orchestrator/config", json=payload)
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"
        assert "probe" in data


def test_api_orchestrator_tool_script(client):
    res = client.get("/api/orchestrator/tool-script")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["filename"] == "open_webui_trader_tool.py"
    assert "class Tools:" in data["code"]
    assert "get_market_intelligence" in data["code"]
