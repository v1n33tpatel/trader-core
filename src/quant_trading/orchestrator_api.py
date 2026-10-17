import os
from pathlib import Path
from flask import Blueprint, jsonify, request
from core.state_store import StateStore
from feeds.orchestrator import AIOrchestrator

orchestrator_blueprint = Blueprint("orchestrator_api", __name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@orchestrator_blueprint.get("/api/orchestrator/status")
def get_orchestrator_status():
    orch = AIOrchestrator()
    status = orch.probe_orchestrator()
    return jsonify(status)


@orchestrator_blueprint.get("/api/orchestrator/tools")
def get_orchestrator_tools():
    orch = AIOrchestrator()
    return jsonify({
        "tools": orch.get_tool_schemas(),
        "total_tools": len(orch.get_tool_schemas())
    })


@orchestrator_blueprint.post("/api/orchestrator/tools/call")
def call_orchestrator_tool():
    payload = request.get_json(silent=True) or {}
    tool_name = payload.get("name", "")
    args = payload.get("arguments") or payload.get("parameters") or {}
    if not tool_name:
        return jsonify({"status": "error", "message": "Missing 'name' in tool call payload"}), 400

    orch = AIOrchestrator()
    result = orch.execute_tool(tool_name, args)
    return jsonify({
        "status": "success" if result.get("status") != "error" else "error",
        "tool": tool_name,
        "result": result
    })


@orchestrator_blueprint.post("/api/orchestrator/command")
def execute_orchestrator_command():
    payload = request.get_json(silent=True) or {}
    command = payload.get("command", "")
    if not command:
        return jsonify({"status": "error", "message": "Missing 'command' parameter"}), 400

    orch = AIOrchestrator()
    result = orch.execute_command(command)
    return jsonify({
        "status": "success",
        "command": command,
        "result": result
    })


@orchestrator_blueprint.post("/api/orchestrator/synthesize")
def run_synthesis():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "ETH").upper()
    orch = AIOrchestrator()
    directive = orch.run_executive_synthesis(symbol=symbol)
    return jsonify(directive)


@orchestrator_blueprint.post("/api/orchestrator/config")
def save_orchestrator_config():
    payload = request.get_json(silent=True) or {}
    url = payload.get("orchestrator_url")
    model = payload.get("orchestrator_model")
    api_key = payload.get("open_webui_api_key")

    store = StateStore()
    updates = {}
    if url is not None:
        cleaned_url = str(url).strip()
        store.set_setting("orchestrator_url", cleaned_url)
        os.environ["ORCHESTRATOR_URL"] = cleaned_url
        updates["ORCHESTRATOR_URL"] = cleaned_url

    if model is not None:
        cleaned_model = str(model).strip()
        store.set_setting("orchestrator_model", cleaned_model)
        os.environ["ORCHESTRATOR_MODEL"] = cleaned_model
        updates["ORCHESTRATOR_MODEL"] = cleaned_model

    if api_key is not None:
        cleaned_key = str(api_key).strip()
        if "••••" not in cleaned_key:
            store.set_setting("open_webui_api_key", cleaned_key)
            os.environ["OPEN_WEBUI_API_KEY"] = cleaned_key
            updates["OPEN_WEBUI_API_KEY"] = cleaned_key

    # Save to .env if updates exist
    env_file = PROJECT_ROOT / ".env"
    if updates and env_file.exists():
        try:
            lines = env_file.read_text(encoding="utf-8").splitlines()
            new_lines = []
            seen = set()
            for line in lines:
                matched = False
                for k, v in updates.items():
                    if line.startswith(f"{k}="):
                        new_lines.append(f"{k}={v}")
                        seen.add(k)
                        matched = True
                        break
                if not matched:
                    new_lines.append(line)
            for k, v in updates.items():
                if k not in seen:
                    new_lines.append(f"{k}={v}")
            env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    orch = AIOrchestrator()
    probe = orch.probe_orchestrator()
    return jsonify({
        "status": "success",
        "message": "Orchestrator configuration updated successfully.",
        "probe": probe
    })


@orchestrator_blueprint.get("/api/orchestrator/tool-script")
def get_open_webui_tool_script():
    script_path = PROJECT_ROOT / "deploy" / "open_webui_trader_tool.py"
    if not script_path.exists():
        return jsonify({"status": "error", "message": "Tool script file not found"}), 404
    code = script_path.read_text(encoding="utf-8")
    return jsonify({
        "status": "success",
        "filename": "open_webui_trader_tool.py",
        "code": code
    })


@orchestrator_blueprint.post("/api/orchestrator/openwebui/sync")
def sync_openwebui():
    from feeds.openwebui_client import OpenWebUIClient
    payload = request.get_json(silent=True) or {}
    url = payload.get("open_webui_url")
    api_key = payload.get("api_key")
    fast_model = payload.get("fast_base_model", "llama3.1:8b")
    deep_model = payload.get("deep_base_model", "deepseek-r1:7b")

    client = OpenWebUIClient(base_url=url, api_key=api_key)
    res = client.sync_workspace(fast_base_model=fast_model, deep_base_model=deep_model)
    status_code = 200 if res.get("status") == "success" else 400
    return jsonify(res), status_code


@orchestrator_blueprint.get("/api/orchestrator/openwebui/inspect")
def inspect_openwebui():
    from feeds.openwebui_client import OpenWebUIClient
    url = request.args.get("url")
    api_key = request.args.get("api_key")
    client = OpenWebUIClient(base_url=url, api_key=api_key)
    res = client.inspect_workspace()
    return jsonify(res)


@orchestrator_blueprint.get("/api/orchestrator/openwebui/rag-preview")
def preview_rag_docs():
    from feeds.rag_docs import get_all_rag_documents
    docs = get_all_rag_documents()
    return jsonify({
        "status": "success",
        "total_documents": len(docs),
        "documents": docs
    })

