import pytest
from unittest.mock import patch
from flask import Flask

from src.quant_trading.workflow_api import workflow_blueprint, _classify_asset, _estimate_price
from core.state_store import StateStore


@pytest.fixture
def workflow_client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(workflow_blueprint)
    app.config["TESTING"] = True

    db_file = str(tmp_path / "test_workflow_state.db")
    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("src.quant_trading.workflow_api.StateStore", lambda: StateStore(db_path=db_file)):
        with app.test_client() as client:
            client.db_file = db_file
            yield client


def test_asset_classification_and_estimation():
    assert _classify_asset("EURUSD", "ctrader") == "FOREX"
    assert _classify_asset("GBPUSD", "binance") == "FOREX"
    assert _classify_asset("XAUUSD", "ctrader") == "COMMODITY"
    assert _classify_asset("BTCUSDT", "binance") == "CRYPTO"
    assert _classify_asset("ETHUSDT", "kraken") == "CRYPTO"
    assert _classify_asset("SPY", "t212") == "ETF"
    assert _classify_asset("AAPL", "t212") == "STOCK"

    # Price estimation table sanity
    assert _estimate_price("BTCUSDT", "CRYPTO") == 67500.0
    assert _estimate_price("EURUSD", "FOREX") == 1.0850
    assert _estimate_price("UNKNOWN", "CRYPTO") == 100.0
    assert _estimate_price("UNKNOWN", "FOREX") == 1.1000


def test_workflow_recommend_crypto(workflow_client):
    res = workflow_client.post(
        "/api/workflow/recommend",
        json={"symbol": "ETHUSDT", "broker": "binance", "current_price": 2650.0}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["symbol"] == "ETHUSDT"
    assert data["broker"] == "binance"
    assert data["asset_class"] == "CRYPTO"

    # Verify all 8 workflow steps are present
    for i in range(1, 9):
        step_key = [k for k in data.keys() if k.startswith(f"step_{i}_")]
        assert len(step_key) == 1, f"Missing step {i} in response"

    params = data["step_6_parameters"]
    assert params["risk_reward_ratio"] >= 2.0, "Risk-to-Reward ratio must be >= 2.0"
    assert params["recommended_size_usd"] <= 50.0, "Order sizing must not exceed $50.0 RiskSentinel bound"
    assert params["entry_price"] == 2650.0

    action = data["step_3_suggest"]["action"]
    if action == "BUY":
        assert params["stop_loss"] < params["entry_price"]
        assert params["take_profit"] > params["entry_price"]
    else:
        assert params["stop_loss"] > params["entry_price"]
        assert params["take_profit"] < params["entry_price"]


def test_workflow_recommend_forex(workflow_client):
    res = workflow_client.post(
        "/api/workflow/recommend",
        json={"symbol": "EURUSD", "broker": "ctrader", "current_price": 1.0850}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["asset_class"] == "FOREX"
    assert data["step_5_strategy"]["strategy_id"] == "london_ny_overlap"

    params = data["step_6_parameters"]
    assert params["risk_reward_ratio"] >= 2.0
    assert params["recommended_size_usd"] <= 50.0
    assert params["recommended_units"] == 1000.0  # Standard micro-lot check


def test_workflow_recommend_equity(workflow_client):
    res = workflow_client.post(
        "/api/workflow/recommend",
        json={"symbol": "SPY", "broker": "t212", "current_price": 580.0}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["asset_class"] == "ETF"
    assert data["step_5_strategy"]["strategy_id"] == "sma_macro_regime"
    assert data["step_6_parameters"]["risk_reward_ratio"] >= 2.0
    assert data["step_6_parameters"]["recommended_size_usd"] <= 50.0


def test_workflow_recommend_lse_etf(workflow_client):
    res = workflow_client.post(
        "/api/workflow/recommend",
        json={"symbol": "EQQQ_l_EQ", "broker": "t212", "current_price": 435.0}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["symbol"] == "EQQQ.L"
    assert data["asset_class"] == "ETF"
    assert data["execution_pipeline"] == "MACRO_DCA"
    assert data["broker"] == "t212"
    assert data["step_5_strategy"]["strategy_id"] == "sma_macro_regime"
    assert "200-Day SMA" in data["step_3_suggest"]["setup_name"]
    assert "sma_200" in data["step_4_analyze"]
    assert data["step_6_parameters"]["risk_reward_ratio"] >= 2.0
    assert data["step_6_parameters"]["recommended_size_usd"] <= 50.0
    assert "max_loss_base_currency" in data["step_6_parameters"]


def test_workflow_recommend_crypto_50pct_ce(workflow_client):
    res = workflow_client.post(
        "/api/workflow/recommend",
        json={"symbol": "BTCUSDT", "broker": "binance", "current_price": 67000.0}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["asset_class"] == "CRYPTO"
    assert data["execution_pipeline"] == "INTRADAY_STRUCTURAL"
    assert data["step_5_strategy"]["strategy_id"] == "fvg_breakout"
    assert "50% FVG CE" in data["step_3_suggest"]["setup_name"]
    ce = data["step_4_analyze"]["consequent_encroachment"]
    fvg_bottom, fvg_top = data["step_4_analyze"]["fvg_zone"]
    assert fvg_bottom < ce < fvg_top
    assert round(ce, 2) == round(fvg_bottom + 0.5 * (fvg_top - fvg_bottom), 2)


def test_workflow_demo_execute(workflow_client, tmp_path):
    db_file = str(tmp_path / "test_workflow_state.db")
    res = workflow_client.post(
        "/api/workflow/demo-execute",
        json={
            "symbol": "BTCUSDT",
            "broker": "binance",
            "side": "BUY",
            "units": 0.005,
            "price": 67200.0,
        }
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "FILLED"
    assert data["mode"] == "DEMO"
    assert data["symbol"] == "BTCUSDT"
    assert data["units"] == 0.005
    assert "DEMO-BINANCE-" in data["order_id"]

    # Verify persistence in StateStore
    store = StateStore(db_path=workflow_client.db_file)
    positions = store.get_positions()
    assert len(positions) >= 1
    assert any(p["symbol"] == "BTCUSDT" for p in positions)
