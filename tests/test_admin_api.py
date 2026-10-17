import pytest
from flask import Flask
from quant_trading.admin_api import admin_blueprint, _mask_key
from core.state_store import StateStore


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(admin_blueprint)
    app.config["TESTING"] = True
    db_file = str(tmp_path / "test_trader_state.db")
    # Patch StateStore to use isolated db
    from unittest.mock import patch
    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("quant_trading.admin_api.StateStore", lambda: StateStore(db_path=db_file)):
        with app.test_client() as test_client:
            yield test_client


def test_mask_key_utility():
    assert _mask_key("") == ""
    assert _mask_key("short") == "••••••••"
    masked = _mask_key("sk-or-v1-abcdef1234567890")
    assert masked.startswith("sk-o")
    assert masked.endswith("7890")
    assert "••••••••" in masked
    assert "123456" not in masked


def test_get_strategies(client):
    res = client.get("/api/strategies")
    assert res.status_code == 200
    data = res.get_json()
    assert "active_strategy" in data
    assert "active_mode" in data
    assert "strategies" in data
    assert len(data["strategies"]) >= 8

    # Verify reactive price_action exists
    pa = next((s for s in data["strategies"] if s["id"] == "price_action"), None)
    assert pa is not None
    assert pa["execution_mode"] == "reactive"


def test_select_strategy(client):
    res = client.post("/api/strategies/select", json={"strategy_id": "atr_trailing_breakout"})
    assert res.status_code == 200
    assert res.get_json()["active_strategy"] == "atr_trailing_breakout"

    # Select unknown strategy should fail
    bad_res = client.post("/api/strategies/select", json={"strategy_id": "invalid_strat_xyz"})
    assert bad_res.status_code == 404


def test_automation_status_and_toggle(client):
    res = client.get("/api/automation/status")
    assert res.status_code == 200
    data = res.get_json()
    assert "mode" in data
    assert "guardrails" in data
    assert data["guardrails"]["stop_loss_pct"] == 2.0

    # Toggle running state
    tog_res = client.post("/api/automation/toggle", json={"running": True})
    assert tog_res.status_code == 200
    assert tog_res.get_json()["is_running"] is True

    # Configure automation mode
    cfg_res = client.post("/api/automation/configure", json={"mode": "predictive", "max_order_usd": 75.0})
    assert cfg_res.status_code == 200
    assert cfg_res.get_json()["status"] == "success"

    # Check updated status
    status2 = client.get("/api/automation/status").get_json()
    assert status2["mode"] == "predictive"
    assert status2["guardrails"]["max_order_usd"] == 75.0


def test_automation_evaluate(client):
    res = client.post("/api/automation/evaluate", json={"symbol": "ETH"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["symbol"] == "ETH"
    assert "action" in data
    assert "reason" in data


def test_environment_mode_switch(client):
    # Initial mode
    res = client.get("/api/environment/mode")
    assert res.status_code == 200
    assert res.get_json()["environment"] == "demo"
    assert res.get_json()["is_demo"] is True

    # Switch to real
    post_res = client.post("/api/environment/mode", json={"environment": "real"})
    assert post_res.status_code == 200
    assert post_res.get_json()["environment"] == "real"
    assert post_res.get_json()["is_demo"] is False

    # Invalid environment
    bad_res = client.post("/api/environment/mode", json={"environment": "staging"})
    assert bad_res.status_code == 400


def test_admin_keys_masking(client, monkeypatch):
    monkeypatch.setenv("T212_API_KEY", "real_secret_t212_key_value")
    monkeypatch.setenv("T212_API_SECRET", "super_secret_secret_12345")

    res = client.get("/api/admin/keys")
    assert res.status_code == 200
    data = res.get_json()

    assert data["t212"]["configured"] is True
    # Crucial security invariant: raw secret is NEVER in response
    assert "real_secret_t212_key_value" not in str(data)
    assert "super_secret_secret_12345" not in str(data)
    assert "••••••••" in data["t212"]["key_preview"]


def test_admin_agents_telemetry(client, monkeypatch):
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: mock_resp)

    res = client.get("/api/admin/agents")
    assert res.status_code == 200
    data = res.get_json()
    assert "agents" in data
    assert len(data["agents"]) == 5
    agent_ids = [a["id"] for a in data["agents"]]
    assert "agent_a" in agent_ids
    assert "agent_b" in agent_ids
    assert "agent_c" in agent_ids
    assert "engine_loop" in agent_ids
    assert "risk_sentinel" in agent_ids


def test_ai_config_crud(client):
    res = client.get("/api/admin/ai-config")
    assert res.status_code == 200
    data = res.get_json()
    assert "provider" in data
    assert "fallback_to_local" in data

    # Update AI config
    update_res = client.post("/api/admin/ai-config", json={
        "provider": "external",
        "external_base_url": "https://api.openai.com/v1",
        "external_model": "gpt-4o",
        "fallback_to_local": True
    })
    assert update_res.status_code == 200
    assert update_res.get_json()["status"] == "success"

    # Verify update
    data2 = client.get("/api/admin/ai-config").get_json()
    assert data2["provider"] == "external"
    assert data2["external_base_url"] == "https://api.openai.com/v1"
    assert data2["external_model"] == "gpt-4o"
