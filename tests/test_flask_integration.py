import importlib
import base64

import pytest

from quant_trading import flask_api
from quant_trading.flask_api import demo_prices


@pytest.mark.parametrize("module_name", ["main", "web_app"])
def test_existing_app_serves_dashboard_assets_and_backtest(module_name: str) -> None:
    app = importlib.import_module(module_name).app
    client = app.test_client()

    dashboard = client.get("/")
    stylesheet = client.get("/dashboard.css")
    script = client.get("/dashboard.js")
    logo = client.get("/logo/MonetMakingMachine-logo.jpg")
    backtest = client.post(
        "/api/research/backtest",
        json={"prices": demo_prices(), "lookback": 20, "volatility_window": 15},
    )

    assert dashboard.status_code == 200
    assert b"Strategy Research" in dashboard.data
    assert stylesheet.status_code == 200
    assert script.status_code == 200
    assert logo.status_code == 200
    assert logo.mimetype == "image/jpeg"
    assert logo.data.startswith(b"\xff\xd8\xff")
    assert backtest.status_code == 200
    assert backtest.json["observations"] == 750


def test_api_status_reports_states_without_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    class SuccessfulResponse:
        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(flask_api.requests, "get", lambda *args, **kwargs: SuccessfulResponse())
    app = importlib.import_module("main").app

    response = app.test_client().get("/api/status")
    statuses = response.get_json()

    assert response.status_code == 200
    assert set(statuses) == {"dashboard", "t212", "etoro", "yahoo", "binance", "kraken", "ollama"}
    assert statuses["dashboard"]["status"] == "online"
    assert all(item["status"] in {"online", "offline", "unconfigured"} for item in statuses.values())
    assert "api_key" not in response.get_data(as_text=True).lower()


def test_t212_status_reads_exact_credentials_from_root_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    (tmp_path / ".env").write_text(
        "T212_API_KEY=demo-key\n"
        "T212_API_SECRET=demo-secret\n"
        "ETORO_API_KEY=other-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(flask_api, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("T212_API_KEY", raising=False)
    monkeypatch.delenv("T212_API_SECRET", raising=False)

    class SuccessfulResponse:
        def raise_for_status(self) -> None:
            return None

    requests_made = []

    def fake_get(url: str, **kwargs):
        requests_made.append((url, kwargs))
        return SuccessfulResponse()

    monkeypatch.setattr(flask_api.requests, "get", fake_get)
    status = flask_api._t212_status()

    expected_token = base64.b64encode(b"demo-key:demo-secret").decode()
    assert status["status"] == "online"
    assert requests_made[0][0] == "https://demo.trading212.com/api/v0/equity/account/cash"
    assert requests_made[0][1]["headers"]["Authorization"] == f"Basic {expected_token}"