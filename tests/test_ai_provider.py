import pytest
from unittest.mock import MagicMock
from feeds.ai_provider import AIProviderClient


def test_ai_provider_local_ollama_mocked(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "<think>Analyzing market</think>BUY ETH structural sweep confirmed."}
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: mock_resp)

    client = AIProviderClient(provider="ollama")
    result = client.generate("Evaluate ETH")

    assert result["provider_used"] == "ollama"
    assert "<think>" not in result["text"]
    assert "BUY ETH structural sweep confirmed." in result["text"]
    assert result["fallback"] is False


def test_ai_provider_external_mocked(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "<think>Checking R:R</think>HOLD. No confirmed market structure setup."
                }
            }
        ]
    }
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: mock_resp)

    client = AIProviderClient(
        provider="external",
        external_base_url="https://openrouter.ai/api/v1",
        external_api_key="sk-or-v1-testkey123",
        external_model="deepseek/deepseek-r1",
        fallback_to_local=False
    )
    result = client.generate("Evaluate SOL")

    assert result["provider_used"] == "external"
    assert "<think>" not in result["text"]
    assert "HOLD. No confirmed market structure setup." in result["text"]
    assert result["fallback"] is False


def test_ai_provider_failover_to_local(monkeypatch):
    # External fails, Ollama succeeds
    call_count = {"val": 0}

    def mock_post(url, *args, **kwargs):
        call_count["val"] += 1
        if "openrouter" in url:
            raise ConnectionError("External API 502 Bad Gateway")
        mock_ollama = MagicMock()
        mock_ollama.status_code = 200
        mock_ollama.json.return_value = {"response": "Local fallback answer: Cash is strategic."}
        return mock_ollama

    monkeypatch.setattr("requests.post", mock_post)

    client = AIProviderClient(
        provider="external",
        external_base_url="https://openrouter.ai/api/v1",
        external_api_key="sk-test",
        fallback_to_local=True
    )
    result = client.generate("Evaluate BTC")

    assert result["fallback"] is True
    assert result["provider_used"] == "ollama"
    assert "Local fallback answer" in result["text"]


def test_ai_connection_tester(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "deepseek-r1:7b"}, {"name": "llama3.1:8b"}]}
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: mock_resp)

    # Test local Ollama connection
    res = AIProviderClient.test_connection(provider="ollama", base_url="http://10.10.10.15:11434")
    assert res["status"] == "online"
    assert res["latency_ms"] >= 0
    assert "deepseek-r1:7b" in res["models"]


def test_ai_provider_timeout_diagnostics(monkeypatch):
    import requests
    def mock_timeout(*args, **kwargs):
        raise requests.exceptions.ReadTimeout("Read timed out")

    monkeypatch.setattr("requests.post", mock_timeout)
    client = AIProviderClient(provider="ollama", timeout=120)
    assert client.timeout == 120

    res = client.generate("Evaluate ETH timeout")
    assert "[AI-TIMEOUT]" in res["text"]
    assert "vmbr1" in res["text"]
    assert "120s" in res["text"]
    assert res["error"] is not None
