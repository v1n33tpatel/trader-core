import json
import io
import pytest
from unittest.mock import MagicMock, patch

from core.state_store import StateStore
from feeds.openwebui_client import OpenWebUIClient
from quant_trading.resource_manager import ResourceManager
from main import app


@pytest.fixture
def temp_store(tmp_path):
    db_file = str(tmp_path / "test_trader_state.db")
    return StateStore(db_path=db_file)


@pytest.fixture
def resource_mgr(temp_store, tmp_path):
    res_dir = tmp_path / "resources"
    owu_mock = MagicMock(spec=OpenWebUIClient)
    owu_mock.base_url = "http://192.168.2.15:8080"
    owu_mock.check_connection.return_value = {"status": "online", "latency_ms": 12.4}
    owu_mock.get_or_create_knowledge_base.return_value = "kb_test_123"
    owu_mock.upload_file.return_value = "file_test_abc"
    owu_mock.add_file_to_knowledge_base.return_value = True
    owu_mock.remove_file_from_knowledge_base.return_value = True
    owu_mock.delete_file.return_value = True

    rm = ResourceManager(
        state_store=temp_store,
        openwebui_client=owu_mock,
        resources_dir=res_dir
    )
    return rm


# =============================================================================
# 1. StateStore Custom Resources & Sync Logs CRUD Tests
# =============================================================================

def test_statestore_resource_crud(temp_store):
    # 1. Save Resource
    res_data = {
        "id": "eq_test_1",
        "category": "EQUATION",
        "title": "Test Kelly Formula",
        "source_url_or_path": "Formula Lib",
        "summary": "Fractional Kelly formula for sizing.",
        "content": "f* = (p*b - q)/b",
        "metadata_json": json.dumps({"tags": ["kelly", "sizing"]}),
        "auto_update": 1
    }
    saved = temp_store.save_resource(res_data)
    assert saved["id"] == "eq_test_1"
    assert saved["title"] == "Test Kelly Formula"

    # 2. Get Resource
    fetched = temp_store.get_resource("eq_test_1")
    assert fetched is not None
    assert fetched["category"] == "EQUATION"
    assert fetched["auto_update"] == 1

    # 3. List Resources
    all_res = temp_store.list_resources()
    assert len(all_res) == 1

    eq_res = temp_store.list_resources(category="EQUATION")
    assert len(eq_res) == 1

    web_res = temp_store.list_resources(category="WEBSITE")
    assert len(web_res) == 0

    # 4. Update Resource Sync
    temp_store.update_resource_sync("eq_test_1", "owu_file_999", "2026-10-17T12:00:00Z")
    updated = temp_store.get_resource("eq_test_1")
    assert updated["openwebui_file_id"] == "owu_file_999"
    assert updated["last_synced_at"] == "2026-10-17T12:00:00Z"

    # 5. Delete Resource
    assert temp_store.delete_resource("eq_test_1") is True
    assert temp_store.get_resource("eq_test_1") is None


def test_statestore_sync_logs(temp_store):
    log_entry = {
        "id": "sync_101",
        "synced_at": "2026-10-17T02:00:00Z",
        "trigger_type": "NIGHTLY_CRON",
        "items_synced": 10,
        "items_failed": 0,
        "status": "SUCCESS",
        "duration_ms": 1250.5,
        "details_json": json.dumps([{"id": "eq_1", "action": "synced"}])
    }
    temp_store.record_sync_log(log_entry)

    logs = temp_store.get_sync_logs(limit=10)
    assert len(logs) == 1
    assert logs[0]["id"] == "sync_101"
    assert logs[0]["items_synced"] == 10
    assert logs[0]["trigger_type"] == "NIGHTLY_CRON"


# =============================================================================
# 2. ResourceManager Seeding & Markdown Synthesis Tests
# =============================================================================

def test_resource_manager_seeding(resource_mgr):
    resource_mgr.seed_default_resources()
    items = resource_mgr.list_resources()
    assert len(items) == 10

    # Verify categories present
    cats = {item["category"] for item in items}
    assert "EQUATION" in cats
    assert "SEC_DATA" in cats
    assert "COMPANY" in cats
    assert "CALENDAR" in cats
    assert "WEBSITE" in cats

    # Check that Half-Kelly is present
    kelly = resource_mgr.get_resource("eq_half_kelly")
    assert kelly is not None
    assert "Half-Kelly" in kelly["title"]
    assert "0.50" in kelly["content"]

    # Verify local markdown cache file was created
    local_file = resource_mgr.resources_dir / "eq_half_kelly.md"
    assert local_file.exists()
    content = local_file.read_text(encoding="utf-8")
    assert "# [RESOURCE: EQUATION]" in content
    assert "Executive Summary" in content


def test_synthesize_markdown_dossier():
    res = {
        "id": "eq_test",
        "category": "EQUATION",
        "title": "Sharpe Ratio Definition",
        "source_url_or_path": "Formula Lib",
        "summary": "Annualized Sharpe ratio calculation.",
        "content": "Sharpe = (mu - rf) / sigma * sqrt(N)",
        "metadata_json": json.dumps({"tags": ["sharpe", "risk"], "symbol": "ETH"}),
        "updated_at": "2026-10-17T15:00:00Z"
    }
    dossier = ResourceManager.synthesize_markdown_dossier(res)
    assert "# [RESOURCE: EQUATION] Sharpe Ratio Definition" in dossier
    assert "**Resource ID**: `eq_test`" in dossier
    assert "**Asset/Ticker**: `ETH`" in dossier
    assert "#equation #sharpe #risk" in dossier
    assert "## Executive Summary" in dossier
    assert "Sharpe = (mu - rf) / sigma * sqrt(N)" in dossier


# =============================================================================
# 3. Historical Data CSV Parsing Tests
# =============================================================================

def test_parse_historical_csv_success(resource_mgr):
    sample_csv = """timestamp,open,high,low,close,volume
2026-01-01,100,105,95,102,1000
2026-01-02,102,108,101,107,1500
2026-01-03,107,112,105,110,2000
2026-01-04,110,111,103,105,1200
2026-01-05,105,115,104,114,2500
"""
    parsed = resource_mgr.parse_historical_csv(
        file_content=sample_csv,
        filename="eth_sample.csv",
        symbol="ETHUSDT",
        timeframe="1d"
    )

    assert parsed["category"] == "HISTORICAL_DATA"
    assert "ETHUSDT" in parsed["title"]
    assert parsed["auto_update"] == 0

    meta = json.loads(parsed["metadata_json"])
    assert meta["total_bars"] == 5
    assert meta["symbol"] == "ETHUSDT"
    assert "annualized_volatility_pct" in meta
    assert "sharpe_ratio" in meta
    assert "max_drawdown_pct" in meta
    assert "poc_price" in meta
    assert meta["poc_price"] > 0


def test_parse_historical_csv_missing_close(resource_mgr):
    bad_csv = """timestamp,open,high,low,volume
2026-01-01,100,105,95,1000
"""
    with pytest.raises(ValueError, match="missing mandatory 'close'"):
        resource_mgr.parse_historical_csv(bad_csv, symbol="BTC")


# =============================================================================
# 4. Web Ingestion & Open-WebUI Synchronization Tests
# =============================================================================

def test_ingest_url_mocked(resource_mgr, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.text = """
    <html>
      <head><title>Algorithmic Market Making Guide</title></head>
      <body>
        <script>console.log('strip me');</script>
        <h1>Market Imbalance Retest</h1>
        <p>Institutions accumulate at Value Area Low.</p>
      </body>
    </html>
    """
    mock_resp.raise_for_status = MagicMock()
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: mock_resp)

    res = resource_mgr.ingest_url("https://example.com/guide")
    assert res["category"] == "WEBSITE"
    assert res["title"] == "Algorithmic Market Making Guide"
    assert "Institutions accumulate at Value Area Low" in res["content"]
    assert "console.log" not in res["content"]


def test_sync_to_openwebui(resource_mgr):
    # Save a test resource
    resource_mgr.save_resource({
        "id": "res_sync_test",
        "category": "EQUATION",
        "title": "Half-Kelly Test",
        "content": "f* = 0.50 * ((p*b - q)/b)",
        "summary": "Sizing rule",
        "auto_update": 1
    })

    sync_result = resource_mgr.sync_to_openwebui(force=True, trigger_type="MANUAL_TEST")
    assert sync_result["status"] == "success"
    assert sync_result["items_synced"] == 1
    assert sync_result["items_failed"] == 0
    assert sync_result["knowledge_base_id"] == "kb_test_123"

    # Verify StateStore was updated
    saved = resource_mgr.get_resource("res_sync_test")
    assert saved["openwebui_file_id"] == "file_test_abc"
    assert saved["last_synced_at"] is not None

    # Check sync audit log
    logs = resource_mgr.store.get_sync_logs()
    assert len(logs) == 1
    assert logs[0]["status"] == "SUCCESS"


def test_sync_to_openwebui_offline(resource_mgr):
    resource_mgr.owu.check_connection.return_value = {"status": "offline", "error": "Connection refused"}
    res = resource_mgr.sync_to_openwebui(force=True)
    assert res["status"] == "offline"
    assert res["items_synced"] == 0


def test_run_nightly_refresh(resource_mgr):
    resource_mgr.seed_default_resources()
    result = resource_mgr.run_nightly_refresh()

    assert result["status"] == "success"
    assert "macro_economic_calendar" in result["refreshed_resources"]
    assert result["sync_result"]["status"] == "success"


# =============================================================================
# 5. Flask API Integration Tests (/api/resources/*)
# =============================================================================

@pytest.fixture
def client(temp_store, monkeypatch):
    monkeypatch.setattr("quant_trading.resource_manager.StateStore", lambda *args, **kwargs: temp_store)
    monkeypatch.setattr("quant_trading.resource_api.StateStore", lambda *args, **kwargs: temp_store)
    with app.test_client() as c:
        yield c


def test_api_list_and_create_resource(client):
    # 1. Create Resource via API
    payload = {
        "category": "EQUATION",
        "title": "Ornstein-Uhlenbeck Test",
        "summary": "O-U process formula",
        "content": "dX = theta*(mu - X)*dt + sigma*dW",
        "auto_update": 1
    }
    post_res = client.post("/api/resources", json=payload)
    assert post_res.status_code == 201
    created = post_res.get_json()["resource"]
    assert created["title"] == "Ornstein-Uhlenbeck Test"
    res_id = created["id"]

    # 2. List Resources
    get_res = client.get("/api/resources")
    assert get_res.status_code == 200
    data = get_res.get_json()
    assert data["total"] == 1
    assert data["resources"][0]["id"] == res_id

    # 3. Filter by Category
    filter_eq = client.get("/api/resources?category=EQUATION")
    assert filter_eq.get_json()["total"] == 1

    filter_web = client.get("/api/resources?category=WEBSITE")
    assert filter_web.get_json()["total"] == 0

    # 4. Get Detail
    detail_res = client.get(f"/api/resources/{res_id}")
    assert detail_res.status_code == 200
    assert detail_res.get_json()["resource"]["id"] == res_id

    # 5. Update Resource
    put_res = client.put(f"/api/resources/{res_id}", json={"title": "Updated O-U Title"})
    assert put_res.status_code == 200
    assert put_res.get_json()["resource"]["title"] == "Updated O-U Title"

    # 6. Delete Resource
    del_res = client.delete(f"/api/resources/{res_id}")
    assert del_res.status_code == 200
    assert del_res.get_json()["deleted_id"] == res_id

    # 7. Confirm 404 after deletion
    assert client.get(f"/api/resources/{res_id}").status_code == 404


def test_api_upload_csv(client):
    csv_bytes = b"timestamp,open,high,low,close,volume\n2026-01-01,10,12,9,11,500\n2026-01-02,11,14,10,13,800\n"
    data = {
        "file": (io.BytesIO(csv_bytes), "sample_upload.csv"),
        "symbol": "SOLUSDT",
        "timeframe": "1h",
        "title": "SOLUSDT 1H Custom Upload"
    }
    res = client.post("/api/resources/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    json_data = res.get_json()
    assert json_data["status"] == "success"
    assert "SOLUSDT" in json_data["resource"]["title"]


def test_api_sync_status(client):
    res = client.get("/api/resources/sync/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "openwebui" in data
    assert "total_resources" in data
    assert "category_counts" in data
