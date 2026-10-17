import pytest
from unittest.mock import MagicMock, patch
from flask import Flask

from feeds.agent_c import AgentCSentinel
from feeds.ai_provider import AIProviderClient
from src.quant_trading.agent_c_api import agent_c_blueprint
from src.quant_trading.admin_api import admin_blueprint
from risk.guardrail import RiskSentinel
from models.events import SignalEvent, BarEvent, SignalSide
from models.signal import SignalType
from core.state_store import StateStore
from datetime import datetime, timezone


@pytest.fixture
def mock_ai_client():
    client = MagicMock(spec=AIProviderClient)
    client.generate.return_value = {
        "text": "1. Crowd Sentiment: Bulls lead on ETH.\n2. Macro Risk: Watch CPI.\n3. Fundamentals: Strong staking yield.\n4. Executive: CLEAR TO TRADE.",
        "provider_used": "grok",
        "model": "grok-2-latest",
        "latency_ms": 120.5,
    }
    return client


@pytest.fixture
def agent(mock_ai_client):
    return AgentCSentinel(provider_client=mock_ai_client)


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(agent_c_blueprint)
    app.register_blueprint(admin_blueprint)
    app.config["TESTING"] = True
    db_file = str(tmp_path / "test_trader_state.db")

    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("quant_trading.admin_api.StateStore", lambda: StateStore(db_path=db_file)), \
         patch("feeds.agent_c.StateStore", lambda: StateStore(db_path=db_file)):
        with app.test_client() as test_client:
            yield test_client


# =============================================================================
# 1. AgentCSentinel Unit Tests
# =============================================================================

def test_fetch_social_sentiment(agent):
    data = agent.fetch_social_sentiment(symbol="ETH")
    assert data["symbol"] == "ETH"
    assert -1.0 <= data["sentiment_score"] <= 1.0
    assert data["sentiment_label"] in ("BULLISH", "BEARISH", "NEUTRAL")
    assert isinstance(data["chatter_stream"], list)
    assert len(data["chatter_stream"]) >= 2

    # Percentage sum invariant
    total_pct = round(data["bull_percentage"] + data["bear_percentage"] + data["neutral_percentage"], 1)
    assert 99.0 <= total_pct <= 101.0
    assert data["mention_velocity_hr"] > 0


def test_fetch_social_sentiment_symbols(agent):
    for sym in ("BTC", "SPY", "UNKNOWN"):
        data = agent.fetch_social_sentiment(symbol=sym)
        assert data["symbol"] == sym.upper()
        assert len(data["chatter_stream"]) >= 2


def test_fetch_company_fundamentals(agent):
    spy = agent.fetch_company_fundamentals(symbol="SPY")
    assert "SPDR S&P 500" in spy["name"]
    assert spy["pe_ratio"] > 0
    assert spy["market_cap"].startswith("$")

    nvda = agent.fetch_company_fundamentals(symbol="NVDA")
    assert "NVIDIA" in nvda["name"]
    assert nvda["analyst_consensus"] == "STRONG BUY"

    eth = agent.fetch_company_fundamentals(symbol="ETH")
    assert "Ethereum" in eth["name"]
    assert "Staking" in eth["dividend_yield"]

    unknown = agent.fetch_company_fundamentals(symbol="XYZ")
    assert "XYZ" in unknown["name"]
    assert unknown["pe_ratio"] > 0


def test_fetch_market_news(agent):
    all_news = agent.fetch_market_news()
    assert isinstance(all_news, list)
    assert len(all_news) >= 3

    for item in all_news:
        assert "id" in item
        assert "title" in item
        assert "source" in item
        assert item["sentiment"] in ("BULLISH", "BEARISH", "NEUTRAL")
        assert item["impact"] in ("HIGH", "MEDIUM", "LOW")

    eth_news = agent.fetch_market_news(symbol="ETH")
    assert len(eth_news) >= 1
    assert any("ETH" in item.get("symbols", []) for item in eth_news)


def test_fetch_economic_calendar(agent):
    cal = agent.fetch_economic_calendar()
    assert "events" in cal
    assert len(cal["events"]) >= 3
    assert cal["event_risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert "next_tier1_event" in cal
    assert "risk_advisory" in cal
    assert "event" in cal["next_tier1_event"]
    assert cal["next_tier1_event"]["minutes_away"] > 0


def test_synthesize_intel(agent, mock_ai_client):
    intel = agent.synthesize_intel(symbol="ETH", question="What is the current whale sentiment?")
    assert intel["symbol"] == "ETH"
    assert "CLEAR TO TRADE" in intel["briefing"]
    assert intel["provider_used"] == "grok"
    assert intel["model"] == "grok-2-latest"
    assert "social" in intel
    assert "calendar" in intel
    assert "news" in intel
    assert "company" in intel
    mock_ai_client.generate.assert_called_once()


# =============================================================================
# 2. RiskSentinel Integration with Event Risk
# =============================================================================

def test_risk_sentinel_event_risk_halt():
    sentinel = RiskSentinel(max_open_positions=5, max_drawdown_pct=3.0, event_risk_guard=True)
    sig = SignalEvent(
        strategy_id="price_action",
        symbol="ETHUSDT",
        side=SignalSide.BUY,
        confidence=0.85,
    )

    # When event_risk_level is HIGH and guard is enabled, should block signal (return None)
    order_blocked = sentinel.validate_signal(
        signal=sig,
        current_open_positions=1,
        daily_loss_pct=0.5,
        current_price=2655.0,
        event_risk_level="HIGH",
    )
    assert order_blocked is None

    # When event_risk_level is LOW, should pass and return an OrderEvent
    order_allowed = sentinel.validate_signal(
        signal=sig,
        current_open_positions=1,
        daily_loss_pct=0.5,
        current_price=2655.0,
        event_risk_level="LOW",
    )
    assert order_allowed is not None
    assert order_allowed.symbol == "ETHUSDT"

    # When event_risk_guard is disabled, HIGH event risk does not block
    sentinel_no_guard = RiskSentinel(max_open_positions=5, max_drawdown_pct=3.0, event_risk_guard=False)
    order_passed = sentinel_no_guard.validate_signal(
        signal=sig,
        current_open_positions=1,
        daily_loss_pct=0.5,
        current_price=2655.0,
        event_risk_level="HIGH",
    )
    assert order_passed is not None


# =============================================================================
# 3. Agent C API Endpoint Tests
# =============================================================================

def test_api_agent_c_intel(client):
    with patch("src.quant_trading.agent_c_api.AgentCSentinel") as MockAgent:
        instance = MockAgent.return_value
        instance.synthesize_intel.return_value = {
            "symbol": "BTC",
            "briefing": "Mock briefing",
            "provider_used": "grok",
            "social": {"sentiment_score": 0.5},
            "calendar": {"event_risk_level": "LOW"},
            "news": [],
            "company": {}
        }
        res = client.get("/api/agent-c/intel?symbol=BTC")
        assert res.status_code == 200
        data = res.get_json()
        assert data["symbol"] == "BTC"
        assert data["briefing"] == "Mock briefing"


def test_api_agent_c_social(client):
    res = client.get("/api/agent-c/social?symbol=ETH")
    assert res.status_code == 200
    data = res.get_json()
    assert data["symbol"] == "ETH"
    assert "chatter_stream" in data


def test_api_agent_c_news(client):
    res = client.get("/api/agent-c/news?symbol=ETH")
    assert res.status_code == 200
    data = res.get_json()
    assert "news" in data
    assert len(data["news"]) >= 1


def test_api_agent_c_calendar(client):
    res = client.get("/api/agent-c/calendar")
    assert res.status_code == 200
    data = res.get_json()
    assert "events" in data
    assert "event_risk_level" in data


def test_api_agent_c_company(client):
    res = client.get("/api/agent-c/company?symbol=NVDA")
    assert res.status_code == 200
    data = res.get_json()
    assert "NVIDIA" in data["name"]


def test_api_agent_c_query(client):
    with patch("src.quant_trading.agent_c_api.AgentCSentinel") as MockAgent:
        instance = MockAgent.return_value
        instance.synthesize_intel.return_value = {
            "symbol": "ETH",
            "briefing": "Synthesized response from Grok",
            "provider_used": "grok"
        }
        res = client.post("/api/agent-c/query", json={"symbol": "ETH", "question": "Whale sweeps?"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["briefing"] == "Synthesized response from Grok"


# =============================================================================
# 4. Admin Agent Mesh & Key Vault Tests for Agent C
# =============================================================================

def test_admin_mesh_includes_agent_c(client):
    res = client.get("/api/admin/agents")
    assert res.status_code == 200
    agents = res.get_json()["agents"]
    agent_c = next((a for a in agents if a["id"] == "agent_c"), None)
    assert agent_c is not None
    assert "Grok" in agent_c["name"] or "Agent C" in agent_c["name"]
    assert "Twitter" in agent_c["role"] or "chats" in agent_c["role"]


def test_admin_key_vault_agent_c_keys(client):
    # Save xAI, Discord, and X tokens
    payload = {
        "XAI_API_KEY": "xai-test-key-1234567890abcdef",
        "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/abc",
        "X_BEARER_TOKEN": "AAAAAAAAAAAAAAAAAAAAAMockToken123456"
    }
    save_res = client.post("/api/admin/keys", json=payload)
    assert save_res.status_code == 200
    assert save_res.get_json()["status"] == "success"

    # Verify keys are masked in GET
    keys_res = client.get("/api/admin/keys")
    assert keys_res.status_code == 200
    data = keys_res.get_json()
    assert "xai" in data
    assert "discord" in data
    assert data["xai"]["configured"] is True
    assert "••••" in data["xai"]["key_preview"]
    assert "1234567890" not in data["xai"]["key_preview"]
    assert data["discord"]["configured"] is True
