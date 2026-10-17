from datetime import UTC, datetime

import numpy as np
import pandas as pd

from quant_trading import flask_api
from quant_trading.market_data import MarketSnapshot


def make_snapshot(count: int = 210) -> MarketSnapshot:
    dates = pd.date_range("2024-01-01", periods=count, freq="B", tz="UTC")
    close = 100.0 * np.exp(np.linspace(0.0, 0.18, count) + 0.025 * np.sin(np.arange(count) / 8))
    bars = [
        {
            "time": date.isoformat(),
            "open": float(value * 0.999),
            "high": float(value * 1.01),
            "low": float(value * 0.99),
            "close": float(value),
            "volume": 1000.0 + index,
        }
        for index, (date, value) in enumerate(zip(dates, close, strict=True))
    ]
    return MarketSnapshot(
        provider="yahoo",
        symbol="SPY",
        interval="1d",
        quote={"price": float(close[-1]), "currency": "USD", "as_of": datetime.now(UTC).isoformat()},
        bars=bars,
    )


def test_market_data_route_returns_quote_bars_and_summary(monkeypatch) -> None:
    snapshot = make_snapshot(45)
    monkeypatch.setattr(flask_api, "get_market_snapshot", lambda *args: snapshot)
    from main import app

    response = app.test_client().get("/api/market/data?provider=yahoo&symbol=SPY&interval=1d&period=3mo")

    assert response.status_code == 200
    assert response.json["quote"]["price"] == snapshot.quote["price"]
    assert len(response.json["bars"]) == 45
    assert response.json["summary"]["bars"] == 45
    assert response.json["summary"]["sma_20"] > 0
    assert response.json["summary"]["periods_per_year"] == 252


def test_analysis_route_includes_price_history_and_active_settings(monkeypatch) -> None:
    snapshot = make_snapshot(55)
    captured = {}
    monkeypatch.setattr(flask_api, "get_market_snapshot", lambda *args: snapshot)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "Trend is positive; volatility remains a risk."}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["body"] = json
        return FakeResponse()

    monkeypatch.setattr(flask_api.requests, "post", fake_post)
    from main import app

    response = app.test_client().post("/api/research/analyze", json={
        "provider": "yahoo",
        "symbol": "SPY",
        "interval": "1d",
        "period": "3mo",
        "question": "Analyze the trend",
        "settings": {"lookback": 30, "volatility_window": 15, "max_leverage": 0.8},
    })

    assert response.status_code == 200
    assert response.json["analysis"].startswith("Trend is positive")
    prompt = captured["body"]["prompt"]
    assert "Analyze the trend" in prompt
    assert '"lookback":30' in prompt
    assert '"recent_ohlcv"' in prompt


def test_optimizer_ranks_training_and_reports_holdout_separately(monkeypatch) -> None:
    snapshot = make_snapshot()
    monkeypatch.setattr(flask_api, "get_market_snapshot", lambda *args: snapshot)
    from main import app

    response = app.test_client().post("/api/research/optimize", json={
        "provider": "yahoo",
        "symbol": "SPY",
        "interval": "1d",
        "period": "1y",
        "settings": {"lookback": 20, "volatility_window": 20, "max_leverage": 1.0},
    })

    assert response.status_code == 200
    result = response.json
    assert result["observations"] == 210
    assert "not used for ranking" in result["objective"]
    assert len(result["candidates"]) == 3
    assert result["train_end"] < result["validation_start"]
    assert "validation" in result["baseline"]


def test_analyze_avoids_openwebui_generate_endpoint_and_falls_back_to_ollama(monkeypatch) -> None:
    snapshot = make_snapshot()
    monkeypatch.setattr(flask_api, "get_market_snapshot", lambda *args: snapshot)

    from core.state_store import StateStore
    store = StateStore()
    store.set_setting("orchestrator_url", "http://192.168.2.15:8080")
    store.set_setting("open_webui_api_key", "sk-test-key")

    calls = []

    def mock_post(url, **kwargs):
        calls.append(url)
        # If open-webui chat completions is hit, simulate 401 or failure
        if "192.168.2.15:8080" in url:
            if url.endswith("/api/generate"):
                raise AssertionError("CRITICAL: /api/generate must NEVER be called on Open-WebUI port 8080!")
            # Simulate Open-WebUI error to trigger Ollama fallback
            resp = flask_api.requests.Response()
            resp.status_code = 401
            return resp

        # Direct Ollama fallback on port 11434
        if ":11434" in url and url.endswith("/api/generate"):
            resp = flask_api.requests.Response()
            resp.status_code = 200
            resp._content = b'{"response": "<think>Evaluating FVG</think>Confirmed bullish trend on SPY."}'
            return resp

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(flask_api.requests, "post", mock_post)
    from main import app

    response = app.test_client().post("/api/research/analyze", json={
        "provider": "yahoo",
        "symbol": "SPY",
        "interval": "1d",
        "period": "3mo",
        "question": "What is the structure?",
    })

    assert response.status_code == 200
    data = response.json
    assert data["analysis"] == "Confirmed bullish trend on SPY."
    assert "<think>" not in data["analysis"]
    # Verify 192.168.2.15:8080/api/generate was NEVER called
    assert not any(c.endswith("8080/api/generate") for c in calls)

