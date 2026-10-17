import pytest
from unittest.mock import MagicMock, patch
from flask import Flask

from feeds.rag_docs import (
    get_price_action_playbook_doc,
    get_risksentinel_envelope_doc,
    get_broker_execution_doc,
    get_live_state_journal_doc,
    get_all_rag_documents,
)
from feeds.openwebui_client import OpenWebUIClient
from src.quant_trading.orchestrator_api import orchestrator_blueprint
from core.state_store import StateStore


@pytest.fixture
def test_client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(orchestrator_blueprint)
    app.config["TESTING"] = True
    db_file = str(tmp_path / "test_trader_state.db")

    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("quant_trading.orchestrator_api.StateStore", lambda: StateStore(db_path=db_file)), \
         patch("feeds.openwebui_client.StateStore", lambda: StateStore(db_path=db_file)):
        with app.test_client() as client:
            yield client


# =============================================================================
# 1. RAG Documents Generation Tests
# =============================================================================

def test_institutional_price_action_playbook():
    doc_dict = get_price_action_playbook_doc()
    assert doc_dict["filename"] == "institutional_price_action_playbook.md"
    doc = doc_dict["content"]
    assert "Institutional Price Action & Market Structure Playbook" in doc
    assert "Fair Value Gaps (FVG)" in doc
    assert "Liquidity Sweeps" in doc
    assert "1:2 R:R" in doc


def test_risksentinel_execution_envelope():
    doc_dict = get_risksentinel_envelope_doc()
    assert doc_dict["filename"] == "risksentinel_execution_envelope.md"
    doc = doc_dict["content"]
    assert "RiskSentinel Capital Preservation" in doc
    assert "2.0%" in doc or "Stop-Loss" in doc
    assert "3.0%" in doc or "Circuit Breaker" in doc
    assert "$50.00" in doc or "Max Order Sizing" in doc


def test_multi_broker_execution_guide():
    doc_dict = get_broker_execution_doc()
    assert doc_dict["filename"] == "multi_broker_execution_guide.md"
    doc = doc_dict["content"]
    assert "Multi-Broker" in doc
    assert "Trading 212" in doc
    assert "negative quantity" in doc.lower()
    assert "Binance" in doc
    assert "Kraken" in doc


def test_live_state_journal(tmp_path):
    db_file = str(tmp_path / "test_trader_state.db")
    store = StateStore(db_path=db_file)
    store.record_trade("pos-1", "ETHUSDT", "binance", "BUY", 1.5, 3000.0)

    with patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("feeds.rag_docs.StateStore", lambda: StateStore(db_path=db_file)):
        doc_dict = get_live_state_journal_doc()
        assert doc_dict["filename"] == "live_state_journal.md"
        doc = doc_dict["content"]
        assert "TraderCore Active State & Execution Journal" in doc
        assert "ETHUSDT" in doc
        assert "3000.0" in doc


def test_get_all_rag_documents():
    docs = get_all_rag_documents()
    assert isinstance(docs, list)
    assert len(docs) == 4
    filenames = [d["filename"] for d in docs]
    assert "institutional_price_action_playbook.md" in filenames
    assert "risksentinel_execution_envelope.md" in filenames
    assert "multi_broker_execution_guide.md" in filenames
    assert "live_state_journal.md" in filenames

    for d in docs:
        assert len(d["content"]) > 100
        assert "title" in d
        assert "description" in d


# =============================================================================
# 2. OpenWebUIClient Unit Tests
# =============================================================================

def test_openwebui_client_init():
    with patch("feeds.openwebui_client.StateStore") as mock_store:
        mock_store.return_value.get_setting.return_value = ""
        with patch.dict("os.environ", {}, clear=True):
            client = OpenWebUIClient()
            assert client.base_url == "http://192.168.2.15:8080"
            assert not client.api_key

    custom_client = OpenWebUIClient(base_url="http://custom:8080/", api_key="secret-token")
    assert custom_client.base_url == "http://custom:8080"
    assert custom_client.api_key == "secret-token"
    headers = custom_client._headers()
    assert headers["Authorization"] == "Bearer secret-token"
    assert headers["Content-Type"] == "application/json"


def test_openwebui_check_connection_online():
    client = OpenWebUIClient(base_url="http://192.168.2.15:8080")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"version": "0.5.0"}

    with patch("requests.get", return_value=mock_resp):
        res = client.check_connection()
        assert res["status"] == "online"
        assert res["latency_ms"] >= 0.0


def test_openwebui_check_connection_offline():
    client = OpenWebUIClient(base_url="http://192.168.2.15:8080")
    with patch("requests.get", side_effect=Exception("Connection refused")):
        res = client.check_connection()
        assert res["status"] == "offline"
        assert "error" in res


def test_openwebui_inspect_workspace():
    client = OpenWebUIClient(base_url="http://192.168.2.15:8080")

    def mock_get(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "/api/v1/tools/" in url:
            resp.json.return_value = [{"id": "trader_core_tools", "name": "TraderCore Tools"}]
        elif "/api/v1/knowledge/" in url:
            resp.json.return_value = [{"id": "kb-123", "name": "TraderCore RAG", "files": [1, 2]}]
        elif "/api/v1/models" in url:
            resp.json.return_value = {"data": [{"id": "trader-core-fast", "name": "TraderCore Fast"}]}
        elif "/api/v1/prompts/" in url:
            resp.json.return_value = [{"command": "/scan", "title": "Market Scan"}]
        elif "/api/version" in url or "/health" in url:
            resp.json.return_value = {"version": "0.5.0"}
        else:
            resp.status_code = 200
            resp.json.return_value = {}
        return resp

    with patch("requests.get", side_effect=mock_get):
        res = client.inspect_workspace()
        assert res["status"] == "online"
        assert res["tools_installed"] is True
        assert "trader-core-fast" in res["orchestrator_models"]
        assert len(res["knowledge_bases"]) == 1


def test_openwebui_deploy_tool():
    client = OpenWebUIClient(base_url="http://192.168.2.15:8080")

    mock_post = MagicMock()
    mock_post.status_code = 200

    mock_get = MagicMock()
    mock_get.status_code = 404  # not exist initially

    with patch("requests.get", return_value=mock_get), \
         patch("requests.post", return_value=mock_post):
        res = client.deploy_tool()
        assert res["status"] == "success"
        assert res["id"] == "trader_core_tools"


def test_openwebui_deploy_rag_playbooks():
    client = OpenWebUIClient(base_url="http://192.168.2.15:8080")

    mock_kb_list = MagicMock()
    mock_kb_list.status_code = 200
    mock_kb_list.json.return_value = []  # No existing KB

    mock_kb_create = MagicMock()
    mock_kb_create.status_code = 200
    mock_kb_create.json.return_value = {"id": "kb-quant-123"}

    mock_file_upload = MagicMock()
    mock_file_upload.status_code = 200
    mock_file_upload.json.return_value = {"id": "file-abc"}

    def mock_post(url, *args, **kwargs):
        if "/api/v1/knowledge/create" in url:
            return mock_kb_create
        elif "/api/v1/files/" in url:
            return mock_file_upload
        else:
            r = MagicMock()
            r.status_code = 200
            return r

    with patch("requests.get", return_value=mock_kb_list), \
         patch("requests.post", side_effect=mock_post):
        res = client.deploy_rag_playbooks()
        assert res["status"] == "success"
        assert res["knowledge_id"] == "kb-quant-123"
        assert len(res["uploaded_files"]) == 4


def test_openwebui_deploy_dual_models():
    client = OpenWebUIClient(base_url="http://192.168.2.15:8080")

    mock_post = MagicMock()
    mock_post.status_code = 200

    with patch("requests.post", return_value=mock_post):
        res = client.deploy_dual_models(
            fast_base_model="llama3.1:8b",
            deep_base_model="deepseek-r1:14b",
            tool_id="trader_core_tools",
            knowledge_id="kb-quant-123"
        )
        assert res["status"] == "success"
        assert len(res["models"]) == 2
        model_ids = [m["id"] for m in res["models"]]
        assert "trader-core-orchestrator-fast" in model_ids
        assert "trader-core-quant-reasoner" in model_ids


def test_openwebui_deploy_prompts():
    client = OpenWebUIClient(base_url="http://192.168.2.15:8080")

    mock_post = MagicMock()
    mock_post.status_code = 200

    with patch("requests.post", return_value=mock_post):
        res = client.deploy_prompts()
        assert res["status"] == "success"
        assert len(res["prompts"]) == 4
        commands = [p["command"] for p in res["prompts"]]
        assert "/scan" in commands
        assert "/macro" in commands
        assert "/portfolio" in commands
        assert "/evaluate" in commands


def test_openwebui_sync_workspace_success(tmp_path):
    db_file = str(tmp_path / "test_trader_state.db")
    client = OpenWebUIClient(base_url="http://192.168.2.15:8080")

    with patch.object(client, "check_connection", return_value={"status": "online"}), \
         patch.object(client, "deploy_tool", return_value={"status": "success", "tool_id": "trader_core_tools"}), \
         patch.object(client, "deploy_rag_playbooks", return_value={"status": "success", "knowledge_id": "kb-1"}), \
         patch.object(client, "deploy_dual_models", return_value={"status": "success", "models": []}), \
         patch.object(client, "deploy_prompts", return_value={"status": "success", "prompts": []}), \
         patch("core.state_store.DEFAULT_DB_PATH", db_file), \
         patch("feeds.openwebui_client.StateStore", lambda: StateStore(db_path=db_file)):
        res = client.sync_workspace(fast_base_model="llama3.1:8b", deep_base_model="deepseek-r1:14b")
        assert res["status"] == "success"
        assert res["base_url"] == "http://192.168.2.15:8080"


# =============================================================================
# 3. Blueprint API Routes Tests
# =============================================================================

def test_api_rag_preview(test_client):
    res = test_client.get("/api/orchestrator/openwebui/rag-preview")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["total_documents"] == 4
    assert len(data["documents"]) == 4


def test_api_inspect_openwebui(test_client):
    with patch("feeds.openwebui_client.OpenWebUIClient.inspect_workspace") as mock_inspect:
        mock_inspect.return_value = {
            "status": "online",
            "version": "0.5.0",
            "tools": [],
            "knowledge_bases": [],
            "models": [],
            "prompts": []
        }
        res = test_client.get("/api/orchestrator/openwebui/inspect?url=http://192.168.2.15:8080")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "online"
        assert data["version"] == "0.5.0"


def test_api_sync_openwebui_success(test_client):
    with patch("feeds.openwebui_client.OpenWebUIClient.sync_workspace") as mock_sync:
        mock_sync.return_value = {
            "status": "success",
            "base_url": "http://192.168.2.15:8080",
            "tool": {"status": "deployed"},
            "rag": {"status": "success"},
            "models": {"status": "success"},
            "prompts": {"status": "success"}
        }
        payload = {
            "open_webui_url": "http://192.168.2.15:8080",
            "api_key": "test-key",
            "fast_base_model": "llama3.1:8b",
            "deep_base_model": "deepseek-r1:14b"
        }
        res = test_client.post("/api/orchestrator/openwebui/sync", json=payload)
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"


def test_api_sync_openwebui_error(test_client):
    with patch("feeds.openwebui_client.OpenWebUIClient.sync_workspace") as mock_sync:
        mock_sync.return_value = {
            "status": "error",
            "message": "Open-WebUI host is offline"
        }
        payload = {
            "open_webui_url": "http://192.168.2.15:8080"
        }
        res = test_client.post("/api/orchestrator/openwebui/sync", json=payload)
        assert res.status_code == 400
        data = res.get_json()
        assert data["status"] == "error"
        assert "offline" in data["message"]
