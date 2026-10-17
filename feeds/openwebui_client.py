import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

from core.state_store import StateStore
from feeds.rag_docs import get_all_rag_documents

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class OpenWebUIClient:
    """
    Client for Open-WebUI REST API (FastAPI backend).
    Programmatically provisions tools, RAG knowledge collections, custom models,
    and quick prompts on the Open-WebUI instance (http://192.168.2.15:8080).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        store = StateStore()
        stored_url = store.get_setting("open_webui_url", "")
        stored_key = store.get_setting("open_webui_api_key", "")

        default_url = os.getenv("OPEN_WEBUI_URL", "http://192.168.2.15:8080")
        default_key = os.getenv("OPEN_WEBUI_API_KEY", "")

        self.base_url = (base_url or stored_url or default_url).rstrip("/")
        self.api_key = api_key or stored_key or default_key

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # =========================================================================
    # 1. Connectivity & Inspection
    # =========================================================================

    def check_connection(self) -> Dict[str, Any]:
        """Probes Open-WebUI API and returns version / status."""
        t0 = time.perf_counter()
        probe_paths = ["/api/v1/models", "/api/models", "/health"]
        for p in probe_paths:
            try:
                r = requests.get(f"{self.base_url}{p}", headers=self._headers(), timeout=5.0)
                if r.status_code in (200, 201):
                    latency = round((time.perf_counter() - t0) * 1000, 1)
                    return {
                        "status": "online",
                        "latency_ms": latency,
                        "base_url": self.base_url,
                        "authenticated": bool(self.api_key and r.status_code != 401)
                    }
                elif r.status_code == 401:
                    return {
                        "status": "unauthorized",
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                        "base_url": self.base_url,
                        "error": "Open-WebUI API Key is invalid or missing"
                    }
            except Exception:
                continue

        return {
            "status": "offline",
            "latency_ms": 0.0,
            "base_url": self.base_url,
            "error": "Cannot reach Open-WebUI service"
        }

    def inspect_workspace(self) -> Dict[str, Any]:
        """Inspects currently installed tools, models, and knowledge bases."""
        conn = self.check_connection()
        if conn.get("status") != "online":
            return {"status": conn.get("status"), "details": conn}

        tools_installed = False
        models_installed = []
        knowledge_bases = []

        # Check Tools
        try:
            r = requests.get(f"{self.base_url}/api/v1/tools/", headers=self._headers(), timeout=5)
            if r.status_code == 200:
                tools_list = r.json()
                tools_installed = any(t.get("id") == "trader_core_tools" for t in tools_list)
        except Exception:
            pass

        # Check Models
        try:
            r = requests.get(f"{self.base_url}/api/v1/models", headers=self._headers(), timeout=5)
            if r.status_code == 200:
                models_data = r.json()
                m_list = models_data.get("data", models_data) if isinstance(models_data, dict) else models_data
                for m in m_list:
                    m_id = m.get("id", "")
                    if "trader-core" in m_id:
                        models_installed.append(m_id)
        except Exception:
            pass

        # Check Knowledge Bases
        try:
            r = requests.get(f"{self.base_url}/api/v1/knowledge/", headers=self._headers(), timeout=5)
            if r.status_code == 200:
                kb_list = r.json()
                for kb in kb_list:
                    if "TraderCore" in kb.get("name", ""):
                        knowledge_bases.append(kb.get("name"))
        except Exception:
            pass

        return {
            "status": "online",
            "connection": conn,
            "tools_installed": tools_installed,
            "orchestrator_models": models_installed,
            "knowledge_bases": knowledge_bases,
            "synced": bool(tools_installed and len(models_installed) >= 1 and len(knowledge_bases) >= 1)
        }

    # =========================================================================
    # 2. Deploy Tool Plugin
    # =========================================================================

    def deploy_tool(self) -> Dict[str, Any]:
        """Uploads deploy/open_webui_trader_tool.py as a native tool in Open-WebUI."""
        script_path = PROJECT_ROOT / "deploy" / "open_webui_trader_tool.py"
        if not script_path.exists():
            return {"status": "error", "message": "Tool file deploy/open_webui_trader_tool.py not found"}

        code = script_path.read_text(encoding="utf-8")
        payload = {
            "id": "trader_core_tools",
            "name": "TraderCore Quant Hub",
            "meta": {
                "description": "Multi-agent quantitative trading workstation tools: institutional price action, social sentiment, macro calendar, and RiskSentinel orders."
            },
            "content": code
        }

        # Check if tool already exists
        check_url = f"{self.base_url}/api/v1/tools/id/trader_core_tools"
        try:
            r_check = requests.get(check_url, headers=self._headers(), timeout=5)
            if r_check.status_code == 200:
                # Update existing tool
                update_url = f"{self.base_url}/api/v1/tools/id/trader_core_tools/update"
                r = requests.post(update_url, headers=self._headers(), json=payload, timeout=10)
                if r.status_code in (200, 201):
                    return {"status": "success", "action": "updated", "id": "trader_core_tools"}
                return {"status": "error", "message": f"Update tool failed: HTTP {r.status_code} {r.text}"}
        except Exception:
            pass

        # Create new tool
        create_url = f"{self.base_url}/api/v1/tools/create"
        try:
            r = requests.post(create_url, headers=self._headers(), json=payload, timeout=10)
            if r.status_code in (200, 201):
                return {"status": "success", "action": "created", "id": "trader_core_tools"}
            return {"status": "error", "message": f"Create tool failed: HTTP {r.status_code} {r.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # 3. Knowledge Base & File Primitives
    # =========================================================================

    def get_or_create_knowledge_base(self, name: str, description: str = "") -> Optional[str]:
        """Finds or creates a Knowledge Base collection and returns its ID."""
        try:
            r = requests.get(f"{self.base_url}/api/v1/knowledge/", headers=self._headers(), timeout=5)
            if r.status_code == 200:
                for kb in r.json():
                    if kb.get("name") == name:
                        return kb.get("id")
        except Exception:
            pass

        try:
            r_create = requests.post(
                f"{self.base_url}/api/v1/knowledge/create",
                headers=self._headers(),
                json={"name": name, "description": description},
                timeout=10
            )
            if r_create.status_code in (200, 201):
                return r_create.json().get("id")
        except Exception:
            pass
        return None

    def upload_file(self, filename: str, content: bytes, content_type: str = "text/markdown") -> Optional[str]:
        """Uploads a file multipart to Open-WebUI and returns the resulting file ID."""
        try:
            files = {"file": (filename, content, content_type)}
            upload_headers = {}
            if self.api_key:
                upload_headers["Authorization"] = f"Bearer {self.api_key}"

            r = requests.post(
                f"{self.base_url}/api/v1/files/",
                headers=upload_headers,
                files=files,
                timeout=15
            )
            if r.status_code in (200, 201):
                return r.json().get("id")
        except Exception:
            pass
        return None

    def add_file_to_knowledge_base(self, knowledge_id: str, file_id: str) -> bool:
        """Binds an uploaded file to a Knowledge Base collection."""
        try:
            r = requests.post(
                f"{self.base_url}/api/v1/knowledge/{knowledge_id}/file/add",
                headers=self._headers(),
                json={"file_id": file_id},
                timeout=10
            )
            return r.status_code in (200, 201)
        except Exception:
            return False

    def remove_file_from_knowledge_base(self, knowledge_id: str, file_id: str) -> bool:
        """Unbinds a file from a Knowledge Base collection."""
        try:
            r = requests.post(
                f"{self.base_url}/api/v1/knowledge/{knowledge_id}/file/remove",
                headers=self._headers(),
                json={"file_id": file_id},
                timeout=10
            )
            return r.status_code in (200, 201)
        except Exception:
            return False

    def delete_file(self, file_id: str) -> bool:
        """Permanently deletes a file from Open-WebUI storage."""
        try:
            r = requests.delete(
                f"{self.base_url}/api/v1/files/{file_id}",
                headers=self._headers(),
                timeout=10
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    def deploy_rag_playbooks(self) -> Dict[str, Any]:
        """Creates the RAG Knowledge Base and uploads the 4 quant playbooks."""
        kb_name = "TraderCore Quantitative Playbook & Market Intel"
        kb_desc = "Institutional Price Action rules, RiskSentinel guardrails, multi-broker standards, and live trade journal."

        knowledge_id = self.get_or_create_knowledge_base(kb_name, kb_desc)
        if not knowledge_id:
            return {"status": "error", "message": "Failed to resolve or create Knowledge Base"}

        docs = get_all_rag_documents()
        uploaded_files = []
        for doc in docs:
            fname = doc["filename"]
            fcontent = doc["content"].encode("utf-8")
            file_id = self.upload_file(fname, fcontent, "text/markdown")
            if file_id:
                self.add_file_to_knowledge_base(knowledge_id, file_id)
                uploaded_files.append({"filename": fname, "file_id": file_id})
            else:
                uploaded_files.append({"filename": fname, "status": "skipped"})

        return {
            "status": "success",
            "knowledge_id": knowledge_id,
            "knowledge_name": kb_name,
            "uploaded_files": uploaded_files
        }

    # =========================================================================
    # 4. Deploy Dual Custom Models
    # =========================================================================

    def deploy_dual_models(
        self,
        fast_base_model: str = "llama3.1:8b",
        deep_base_model: str = "deepseek-r1:7b",
        tool_id: str = "trader_core_tools",
        knowledge_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates two tailored model presets in Open-WebUI:
        1. TraderCore Orchestrator (Fast) for instant tool execution.
        2. TraderCore Quant Reasoner (Deep R1) for deep chain-of-thought analysis.
        """
        models_created = []
        kb_meta = [{"id": knowledge_id, "type": "collection"}] if knowledge_id else []

        # Model 1: Fast Orchestrator
        fast_sys = """You are the Fast Quantitative AI Orchestrator for MoneyMakingMachine.
You operate directly connected to trader-core multi-broker algorithms.
Use your tools to query real-time market structure, price action, sentiment, and portfolio state.
Provide rapid, concise, executive answers. Enforce strict risk guardrails."""

        payload_fast = {
            "id": "trader-core-orchestrator-fast",
            "name": "TraderCore Orchestrator (Fast)",
            "base_model_id": fast_base_model,
            "meta": {
                "description": f"Fast Quantitative Trading Orchestrator powered by {fast_base_model}. Quick market scans and tool execution.",
                "capabilities": {"tools": True},
                "tool_ids": [tool_id],
                "knowledge": kb_meta
            },
            "params": {
                "system": fast_sys,
                "temperature": 0.2
            }
        }

        # Model 2: Deep Quant Reasoner
        deep_sys = """You are the Chief Quantitative Strategist & Reasoner for MoneyMakingMachine.
You operate an institutional, strictly non-predictive Price Action framework.
REASONING MANDATE:
- Think deeply before issuing directives. Question whether a liquidity sweep was genuine or retail trap.
- Never enter without confirmed Break of Structure (BOS) or Pinbar Rejection candle.
- Anchor stop-loss strictly to the structural rejection wick.
- Require a minimum 1:2 Risk-to-Reward (R:R) ratio for any trade setup.
- If high-impact macro reports (CPI, FOMC, NFP) are imminent, mandate EVENT RISK HALT."""

        payload_deep = {
            "id": "trader-core-quant-reasoner",
            "name": "TraderCore Quant Reasoner (Deep R1)",
            "base_model_id": deep_base_model,
            "meta": {
                "description": f"Deep Institutional Quant Reasoner powered by {deep_base_model}. Step-by-step chain-of-thought analysis.",
                "capabilities": {"tools": True},
                "tool_ids": [tool_id],
                "knowledge": kb_meta
            },
            "params": {
                "system": deep_sys,
                "temperature": 0.3
            }
        }

        for p in [payload_fast, payload_deep]:
            m_id = p["id"]
            # Attempt create or update
            try:
                r = requests.post(f"{self.base_url}/api/v1/models/create", headers=self._headers(), json=p, timeout=10)
                if r.status_code in (200, 201):
                    models_created.append({"id": m_id, "name": p["name"], "status": "created"})
                elif r.status_code == 400 or "already exists" in r.text.lower():
                    # Update model
                    r_up = requests.post(f"{self.base_url}/api/v1/models/update", headers=self._headers(), json=p, timeout=10)
                    models_created.append({"id": m_id, "name": p["name"], "status": "updated"})
                else:
                    models_created.append({"id": m_id, "name": p["name"], "status": f"HTTP {r.status_code}"})
            except Exception as e:
                models_created.append({"id": m_id, "name": p["name"], "error": str(e)})

        return {"status": "success", "models": models_created}

    # =========================================================================
    # 5. Deploy Quick Prompts & Slash Commands
    # =========================================================================

    def deploy_prompts(self) -> Dict[str, Any]:
        """Registers quick prompts (/scan, /macro, /portfolio, /evaluate) in Open-WebUI."""
        prompts = [
            {
                "command": "/scan",
                "title": "Scan Market Structure & Sentiment",
                "content": "Execute institutional price action and social sentiment scan for symbol {{prompt:default=ETH}}. Check for liquidity sweeps and pinbars."
            },
            {
                "command": "/macro",
                "title": "Check Tier-1 Macro Calendar Risk",
                "content": "Check upcoming Tier-1 economic reports (CPI, FOMC, NFP) and report any macro event-risk halts in RiskSentinel."
            },
            {
                "command": "/portfolio",
                "title": "Inspect Portfolio & Risk Envelope",
                "content": "Inspect current open positions, account environment mode (DEMO/REAL), and RiskSentinel limits."
            },
            {
                "command": "/evaluate",
                "title": "Evaluate Trade Setup (1:2 R:R)",
                "content": "Run a full institutional price action evaluation for {{prompt:default=ETH}} and compute entry, stop-loss wick, and 1:2 R:R take profit target."
            }
        ]

        installed = []
        for p in prompts:
            cmd = p["command"]
            try:
                r = requests.post(f"{self.base_url}/api/v1/prompts/create", headers=self._headers(), json=p, timeout=5)
                if r.status_code in (200, 201):
                    installed.append({"command": cmd, "status": "created"})
                else:
                    # Try update
                    requests.post(f"{self.base_url}/api/v1/prompts/command{cmd}/update", headers=self._headers(), json=p, timeout=5)
                    installed.append({"command": cmd, "status": "updated"})
            except Exception:
                installed.append({"command": cmd, "status": "registered"})

        return {"status": "success", "prompts": installed}

    # =========================================================================
    # 6. Complete End-to-End Synchronization
    # =========================================================================

    def sync_workspace(
        self,
        fast_base_model: str = "llama3.1:8b",
        deep_base_model: str = "deepseek-r1:7b"
    ) -> Dict[str, Any]:
        """Runs the entire provisioning journey and returns structured audit results."""
        conn = self.check_connection()
        if conn.get("status") != "online":
            return {"status": "error", "message": f"Open-WebUI host is {conn.get('status')}: {conn.get('error', '')}"}

        # Step 1: Deploy Tool Plugin
        tool_res = self.deploy_tool()

        # Step 2: Deploy RAG Playbooks
        rag_res = self.deploy_rag_playbooks()
        kb_id = rag_res.get("knowledge_id")

        # Step 3: Deploy Dual Models
        model_res = self.deploy_dual_models(
            fast_base_model=fast_base_model,
            deep_base_model=deep_base_model,
            tool_id="trader_core_tools",
            knowledge_id=kb_id
        )

        # Step 4: Deploy Quick Prompts
        prompts_res = self.deploy_prompts()

        # Persist configuration in StateStore
        store = StateStore()
        store.set_setting("open_webui_url", self.base_url)
        store.set_setting("open_webui_fast_model", fast_base_model)
        store.set_setting("open_webui_deep_model", deep_base_model)

        return {
            "status": "success",
            "base_url": self.base_url,
            "tool": tool_res,
            "rag": rag_res,
            "models": model_res,
            "prompts": prompts_res,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC")
        }
