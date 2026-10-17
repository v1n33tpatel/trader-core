import os
import json
import time
from typing import Dict, Any, List
from flask import Blueprint, jsonify, request
from core.state_store import StateStore
from feeds.openwebui_client import OpenWebUIClient
from quant_trading.resource_manager import ResourceManager

resource_blueprint = Blueprint("resource_api", __name__)

ALLOWED_CATEGORIES = [
    "ALL",
    "WEBSITE",
    "HISTORICAL_DATA",
    "SEC_DATA",
    "COMPANY",
    "EQUATION",
    "CALENDAR"
]


@resource_blueprint.get("/api/resources")
def list_resources():
    """Returns a list of all resources, optionally filtered by category."""
    category = request.args.get("category", "ALL").strip().upper()
    limit = int(request.args.get("limit", 200))

    rm = ResourceManager()
    resources = rm.list_resources(category=category, limit=limit)

    return jsonify({
        "status": "success",
        "resources": resources,
        "total": len(resources),
        "category": category,
        "categories": ALLOWED_CATEGORIES
    })


@resource_blueprint.post("/api/resources")
def create_resource():
    """Creates a new custom resource or ingests from a URL."""
    payload = request.get_json(silent=True) or {}
    category = str(payload.get("category", "WEBSITE")).strip().upper()
    title = str(payload.get("title", "")).strip()
    source = str(payload.get("source_url_or_path", "")).strip()
    summary = str(payload.get("summary", "")).strip()
    content = str(payload.get("content", "")).strip()
    metadata = payload.get("metadata_json") or {}
    auto_update = 1 if payload.get("auto_update", 1) in (1, True, "1") else 0

    if category not in ALLOWED_CATEGORIES or category == "ALL":
        category = "WEBSITE"

    rm = ResourceManager()

    # If category is WEBSITE, source looks like a URL, and content is empty -> fetch it
    if category == "WEBSITE" and source.startswith(("http://", "https://")) and not content:
        try:
            url_res = rm.ingest_url(url=source, title=title if title else None)
            url_res["auto_update"] = auto_update
            saved = rm.save_resource(url_res)
            return jsonify({"status": "success", "resource": saved}), 201
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to ingest URL: {str(e)}"}), 400

    if not title:
        return jsonify({"status": "error", "message": "Missing 'title' parameter"}), 400

    if not content:
        return jsonify({"status": "error", "message": "Missing 'content' parameter"}), 400

    meta_str = json.dumps(metadata) if isinstance(metadata, dict) else str(metadata)
    new_res = {
        "category": category,
        "title": title,
        "source_url_or_path": source,
        "summary": summary,
        "content": content,
        "metadata_json": meta_str,
        "auto_update": auto_update
    }
    saved = rm.save_resource(new_res)
    return jsonify({"status": "success", "resource": saved}), 201


@resource_blueprint.get("/api/resources/<resource_id>")
def get_resource_detail(resource_id: str):
    """Retrieves a single resource by ID."""
    rm = ResourceManager()
    res = rm.get_resource(resource_id)
    if not res:
        return jsonify({"status": "error", "message": "Resource not found"}), 404
    return jsonify({"status": "success", "resource": res})


@resource_blueprint.put("/api/resources/<resource_id>")
def update_resource(resource_id: str):
    """Updates an existing resource."""
    payload = request.get_json(silent=True) or {}
    rm = ResourceManager()
    existing = rm.get_resource(resource_id)
    if not existing:
        return jsonify({"status": "error", "message": "Resource not found"}), 404

    for field in ["title", "category", "source_url_or_path", "summary", "content"]:
        if field in payload and payload[field] is not None:
            existing[field] = str(payload[field]).strip()

    if "auto_update" in payload:
        existing["auto_update"] = 1 if payload["auto_update"] in (1, True, "1") else 0

    if "metadata_json" in payload:
        meta = payload["metadata_json"]
        existing["metadata_json"] = json.dumps(meta) if isinstance(meta, dict) else str(meta)

    saved = rm.save_resource(existing)
    return jsonify({"status": "success", "resource": saved})


@resource_blueprint.delete("/api/resources/<resource_id>")
def delete_resource_item(resource_id: str):
    """Deletes a resource and removes its indexed file from Open-WebUI."""
    rm = ResourceManager()
    success = rm.delete_resource(resource_id)
    if not success:
        return jsonify({"status": "error", "message": "Resource not found or deletion failed"}), 404
    return jsonify({"status": "success", "deleted_id": resource_id})


@resource_blueprint.post("/api/resources/upload")
def upload_historical_dataset():
    """Handles multipart upload of historical CSV/JSON dataset and computes statistical profile."""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded in multipart form data"}), 400

    uploaded_file = request.files["file"]
    if uploaded_file.filename == "":
        return jsonify({"status": "error", "message": "Empty filename"}), 400

    symbol = request.form.get("symbol", "ASSET").strip().upper()
    timeframe = request.form.get("timeframe", "1d").strip().lower()
    title = request.form.get("title")

    rm = ResourceManager()
    try:
        content_bytes = uploaded_file.read()
        dataset_res = rm.parse_historical_csv(
            file_content=content_bytes,
            filename=uploaded_file.filename,
            symbol=symbol,
            timeframe=timeframe,
            title=title
        )
        saved = rm.save_resource(dataset_res)
        return jsonify({"status": "success", "resource": saved}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": f"Historical data parsing failed: {str(e)}"}), 400


@resource_blueprint.post("/api/resources/sync")
def trigger_openwebui_sync():
    """Triggers immediate synchronization of all resources to Open-WebUI."""
    payload = request.get_json(silent=True) or {}
    force = bool(payload.get("force", False))

    rm = ResourceManager()
    result = rm.sync_to_openwebui(force=force, trigger_type="MANUAL_UI")
    return jsonify(result)


@resource_blueprint.get("/api/resources/sync/status")
def get_sync_status():
    """Returns current sync status, Open-WebUI connectivity, and recent audit logs."""
    rm = ResourceManager()
    store = rm.store
    owu = rm.owu

    conn = owu.check_connection()
    kb_id = store.get_setting("openwebui_resource_hub_id", "")
    all_res = store.list_resources(limit=500)
    synced_count = sum(1 for r in all_res if r.get("openwebui_file_id"))
    last_synced = max([r.get("last_synced_at") for r in all_res if r.get("last_synced_at")] or ["Never"])

    logs = store.get_sync_logs(limit=10)

    category_counts = {}
    for c in ALLOWED_CATEGORIES:
        if c != "ALL":
            category_counts[c] = sum(1 for r in all_res if r.get("category") == c)

    return jsonify({
        "status": "success",
        "openwebui": {
            "status": conn.get("status", "offline"),
            "base_url": owu.base_url,
            "latency_ms": conn.get("latency_ms", 0.0),
            "knowledge_base_id": kb_id
        },
        "total_resources": len(all_res),
        "synced_resources": synced_count,
        "last_synced_at": last_synced,
        "category_counts": category_counts,
        "recent_sync_logs": logs
    })


@resource_blueprint.post("/api/resources/nightly-run")
def trigger_nightly_run():
    """Manually invokes the automated nightly refresh routine (02:00 UTC)."""
    rm = ResourceManager()
    result = rm.run_nightly_refresh()
    return jsonify(result)
