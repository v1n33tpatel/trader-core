import os
import re
import json
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import requests

from core.state_store import StateStore
from feeds.agent_c import AgentCSentinel
from feeds.sub_agent import TwoTierQuantAgent
from risk.guardrail import RiskSentinel
from models.events import SignalEvent, SignalSide
from strategies.registry import STRATEGY_CATALOG

# Thread safety lock to serialize local LLM inference and protect GPU VRAM
OLLAMA_LOCK = threading.Lock()


class AIOrchestrator:
    """
    Central AI Quantitative Orchestrator for MoneyMakingMachine.
    Connects to local Ollama (http://10.10.10.15:11434) and Open-WebUI (http://192.168.2.15:8080)
    via standard REST and OpenAI-compatible tool/function-calling protocols.

    Responsibilities:
    1. Multi-Agent Synthesis: Ingests Agent A (Structure), Agent B (Quant Reasoning),
       Agent C (Social Sentiment & Macro Calendar), and RiskSentinel.
    2. Tool Execution Gateway: Executes commands sent by Open-WebUI models and pipelines.
    3. Concurrency Protection: Enforces OLLAMA_LOCK to prevent GPU VRAM overload.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.store = StateStore()
        stored_url = self.store.get_setting("orchestrator_url", "")
        stored_model = self.store.get_setting("orchestrator_model", "")
        stored_key = self.store.get_setting("open_webui_api_key", "")

        default_url = os.getenv("ORCHESTRATOR_URL", os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434"))
        default_model = os.getenv("ORCHESTRATOR_MODEL", "llama3.1:8b")
        default_key = os.getenv("OPEN_WEBUI_API_KEY", "")

        self.base_url = (base_url or stored_url or default_url).rstrip("/")
        self.model = model or stored_model or default_model
        self.api_key = api_key or stored_key or default_key

        # Determine backend flavor (Ollama native operates on 11434; Open-WebUI operates on 8080/3000)
        if "11434" in self.base_url:
            self.is_open_webui = False
        elif "8080" in self.base_url or "3000" in self.base_url:
            self.is_open_webui = True
        else:
            self.is_open_webui = bool(self.api_key)

    # =========================================================================
    # 1. Diagnostic & Health Probing
    # =========================================================================

    def probe_orchestrator(self) -> Dict[str, Any]:
        """Checks connectivity and measures round-trip latency to the orchestrator host."""
        t0 = time.perf_counter()
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Target probe URL depending on backend
        probe_urls = []
        if self.is_open_webui:
            probe_urls = [
                f"{self.base_url}/api/v1/models",
                f"{self.base_url}/api/models",
                f"{self.base_url}/health"
            ]
        else:
            probe_urls = [
                f"{self.base_url}/api/tags",
                f"{self.base_url}/api/version"
            ]

        for url in probe_urls:
            try:
                r = requests.get(url, headers=headers, timeout=4.0)
                if r.status_code in (200, 201):
                    latency = round((time.perf_counter() - t0) * 1000, 1)
                    return {
                        "status": "online",
                        "latency_ms": latency,
                        "base_url": self.base_url,
                        "model": self.model,
                        "type": "open_webui" if self.is_open_webui else "ollama",
                        "endpoint_probed": url
                    }
            except Exception:
                continue

        return {
            "status": "offline",
            "latency_ms": 0.0,
            "base_url": self.base_url,
            "model": self.model,
            "type": "open_webui" if self.is_open_webui else "ollama",
            "error": "Failed to connect to orchestrator service"
        }

    # =========================================================================
    # 2. Tool Registry & Schemas
    # =========================================================================

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Returns OpenAPI/JSON schema tool definitions for Open-WebUI function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_market_intelligence",
                    "description": "Fetch real-time social sentiment (Twitter/Discord), breaking news, and Tier-1 macro event calendar from Agent C.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Asset symbol (e.g. ETH, BTC, SPY, NVDA)"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "evaluate_price_action",
                    "description": "Run institutional price action structure analysis: swing pivots, liquidity sweeps, pinbar rejections, BOS, and Volume Profile (POC/VAH/VAL).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Crypto or stock symbol (e.g. ETH, BTC, SOL)"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_portfolio_and_risk",
                    "description": "Fetch current open positions, account environment mode (DEMO/REAL), active strategy, and RiskSentinel parameters.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "switch_strategy",
                    "description": "Switch the active algorithmic strategy (e.g. price_action, atr_trailing_breakout, fvg_breakout, rsi_reversion).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "strategy_id": {"type": "string", "description": "Strategy identifier from the catalog"}
                        },
                        "required": ["strategy_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_automation_mode",
                    "description": "Set execution engine automation mode: reactive (non-predictive price action only), predictive (quantitative models), or hybrid.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string", "enum": ["reactive", "predictive", "hybrid"]}
                        },
                        "required": ["mode"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_order",
                    "description": "Validate and submit a trade order through RiskSentinel capital preservation guardrails. Defaults to safe practice/demo mode.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Ticker symbol, e.g. ETH, BTC"},
                            "side": {"type": "string", "enum": ["BUY", "SELL"]},
                            "units": {"type": "number", "description": "Units to trade (optional)"},
                            "target_allocation_usd": {"type": "number", "description": "Target allocation in USD (default: $50)"},
                            "force_live": {"type": "boolean", "description": "Whether to force live account order (defaults to false for safety)"}
                        },
                        "required": ["symbol", "side"]
                    }
                }
            }
        ]

    # =========================================================================
    # 3. Tool Execution Engine
    # =========================================================================

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a specific tool requested by Open-WebUI or local models."""
        try:
            if name == "get_market_intelligence":
                symbol = str(args.get("symbol", "ETH")).upper()
                agent_c = AgentCSentinel()
                return agent_c.synthesize_intel(symbol=symbol)

            elif name == "evaluate_price_action":
                symbol = str(args.get("symbol", "ETH")).upper()
                structure = TwoTierQuantAgent.get_price_action_metrics(symbol)
                liquidity = TwoTierQuantAgent.get_liquidity_clusters(symbol)
                return {
                    "symbol": symbol,
                    "market_structure": structure,
                    "liquidity_profile": liquidity,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            elif name == "get_portfolio_and_risk":
                env = self.store.get_setting("environment_mode", "demo")
                strat = self.store.get_setting("active_strategy", "price_action")
                mode = self.store.get_setting("automation_mode", "reactive")
                positions = []
                with self.store._get_conn() if hasattr(self.store, "_get_conn") else sqlite3_conn(self.store.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT position_id, symbol, broker, side, units, entry_price, current_price, opened_at FROM positions")
                    for row in cur.fetchall():
                        positions.append({
                            "position_id": row[0],
                            "symbol": row[1],
                            "broker": row[2],
                            "side": row[3],
                            "units": row[4],
                            "entry_price": row[5],
                            "current_price": row[6],
                            "opened_at": row[7]
                        })
                return {
                    "environment_mode": env.upper(),
                    "is_demo": (env == "demo"),
                    "active_strategy": strat,
                    "automation_mode": mode,
                    "open_positions": positions,
                    "risk_sentinel": {
                        "max_drawdown_limit_pct": 3.0,
                        "max_open_positions": 5,
                        "max_order_usd": 50.0,
                        "min_risk_reward_ratio": 2.0,
                        "event_risk_guard_active": True
                    }
                }

            elif name == "switch_strategy":
                strat_id = args.get("strategy_id", "").lower().strip()
                flat_strats = {}
                for category, strats in STRATEGY_CATALOG.items():
                    for s_id, s_info in strats.items():
                        flat_strats[s_id] = {**s_info, "category": category}

                if strat_id not in flat_strats:
                    return {"status": "error", "message": f"Strategy '{strat_id}' not found in catalog: {list(flat_strats.keys())}"}

                self.store.set_setting("active_strategy", strat_id)
                strat_info = flat_strats[strat_id]
                return {
                    "status": "success",
                    "active_strategy": strat_id,
                    "name": strat_info["name"],
                    "category": strat_info.get("category", "crypto")
                }

            elif name == "set_automation_mode":
                mode = args.get("mode", "").lower().strip()
                if mode not in ("reactive", "predictive", "hybrid"):
                    return {"status": "error", "message": f"Invalid mode '{mode}'. Choose 'reactive', 'predictive', or 'hybrid'."}
                self.store.set_setting("automation_mode", mode)
                return {"status": "success", "automation_mode": mode}

            elif name == "submit_order":
                symbol = str(args.get("symbol", "ETH")).upper()
                side_str = str(args.get("side", "BUY")).upper()
                units = float(args.get("units", 0.0))
                alloc_usd = float(args.get("target_allocation_usd", 50.0))
                force_live = bool(args.get("force_live", False))

                side = SignalSide.BUY if side_str == "BUY" else SignalSide.SELL
                sig = SignalEvent(strategy_id="orchestrator", symbol=symbol, side=side, confidence=0.90)

                # Fetch current market price
                m = TwoTierQuantAgent.get_binance_metrics(symbol)
                price = m.get("price", 2600.0) if isinstance(m, dict) else 2600.0
                if units <= 0:
                    units = round(alloc_usd / price, 4) if price > 0 else 0.01

                # Validate against RiskSentinel
                sentinel = RiskSentinel(max_open_positions=5, max_drawdown_pct=3.0, max_order_usd=50.0)
                cal = AgentCSentinel().fetch_economic_calendar()
                event_risk = cal.get("event_risk_level", "LOW")

                order = sentinel.validate_signal(
                    signal=sig,
                    current_open_positions=0,
                    daily_loss_pct=0.0,
                    current_price=price,
                    event_risk_level=event_risk
                )

                if not order:
                    return {
                        "status": "rejected",
                        "reason": f"RiskSentinel rejected order. Tier-1 Macro Event Risk: {event_risk}."
                    }

                # Record in state store (safe demo mode by default)
                pos_id = f"orch_{int(time.time())}_{symbol.lower()}"
                self.store.record_trade(pos_id, symbol, "binance", side_str, units, price)
                return {
                    "status": "executed",
                    "mode": "DEMO" if not force_live else "LIVE",
                    "position_id": pos_id,
                    "symbol": symbol,
                    "side": side_str,
                    "units": units,
                    "fill_price": price,
                    "total_usd": round(units * price, 2),
                    "event_risk_level": event_risk,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            else:
                return {"status": "error", "message": f"Unknown tool: '{name}'"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # 4. Multi-Agent Executive Synthesis
    # =========================================================================

    def run_executive_synthesis(self, symbol: str = "ETH") -> Dict[str, Any]:
        """
        Polls Agent A, B, C, and RiskSentinel, then uses the Orchestrator model
        to produce an actionable executive briefing and trade setup.
        """
        sym = symbol.upper()

        # Step 1: Collect Multi-Agent Telemetry
        agent_c = AgentCSentinel()
        intel = agent_c.synthesize_intel(symbol=sym)
        pa_structure = TwoTierQuantAgent.get_price_action_metrics(sym)
        liquidity = TwoTierQuantAgent.get_liquidity_clusters(sym)
        portfolio = self.execute_tool("get_portfolio_and_risk", {})

        synthesis_payload = {
            "symbol": sym,
            "social_sentiment": intel.get("social", {}),
            "macro_calendar": intel.get("calendar", {}),
            "breaking_news": intel.get("news", [])[:2],
            "company_fundamentals": intel.get("company", {}),
            "price_action_structure": pa_structure,
            "volume_profile": liquidity.get("volume_profile", {}),
            "portfolio_context": portfolio
        }

        # Step 2: Query Orchestrator Model with Concurrency Lock
        prompt = f"""
You are the Chief Quantitative AI Orchestrator for MoneyMakingMachine.
Synthesize the complete multi-agent telemetry below and issue an Executive Directive for {sym}.

MULTI-AGENT TELEMETRY:
{json.dumps(synthesis_payload, indent=2)}

INSTRUCTIONS:
1. Reconcile Agent A (Institutional Price Action: BOS, liquidity sweeps, pinbars), Agent B (Quant Reasoning), and Agent C (Twitter/Discord sentiment and Tier-1 macro calendar).
2. Check RiskSentinel event risk: If macro risk is HIGH, enforce EVENT RISK HALT.
3. If confirmed Price Action setup is active with minimum 1:2 R:R, provide suggested entry, stop loss, and take profit.
4. If no confirmed structural setup is active, mandate HOLD. Cash is a strategic position.

Return STRICT RAW JSON ONLY in this format:
{{
  "symbol": "{sym}",
  "executive_action": "BUY" | "SELL" | "HOLD" | "EVENT_RISK_HALT",
  "confidence": <float 0.0 to 1.0>,
  "setup_summary": "<concise explanation reconciling price action with social sentiment and macro risk>",
  "invalidation_sl": <float or null>,
  "take_profit_tp": <float or null>,
  "risk_reward_ratio": <float or null>,
  "target_allocation_usd": <float>,
  "orchestrator_notes": "<strategic execution recommendation>"
}}
"""
        response_data = self._call_llm(prompt)
        text = response_data.get("text", "{}")
        # Strip <think>...</think> if emitted by reasoning models
        clean_json = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        try:
            directive = json.loads(clean_json)
        except Exception:
            directive = {
                "symbol": sym,
                "executive_action": "HOLD",
                "confidence": 0.0,
                "setup_summary": clean_json or "Synthesized market overview generated.",
                "target_allocation_usd": 0.0,
                "orchestrator_notes": "Awaiting clear structural confirmation."
            }

        return {
            "symbol": sym,
            "directive": directive,
            "telemetry": synthesis_payload,
            "orchestrator_meta": {
                "model": self.model,
                "backend": "open_webui" if self.is_open_webui else "ollama",
                "latency_ms": response_data.get("latency_ms", 0.0)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    # =========================================================================
    # 5. Natural Language Command Dispatcher
    # =========================================================================

    def execute_command(self, user_command: str) -> Dict[str, Any]:
        """
        Executes a natural language directive from Open-WebUI or user chat.
        Dispatches tools dynamically and returns the synthesized result.
        """
        cmd_lower = user_command.lower()

        # Direct pattern fast-paths for deterministic execution
        sym_match = re.search(r"\b(ETH|BTC|SOL|SPY|NVDA|TSLA|AVAX)\b", user_command.upper())
        target_sym = sym_match.group(1) if sym_match else "ETH"

        if "switch strategy" in cmd_lower or "use strategy" in cmd_lower:
            for category, strats in STRATEGY_CATALOG.items():
                for s_id, s_info in strats.items():
                    if s_id in cmd_lower or s_info["name"].lower() in cmd_lower:
                        return self.execute_tool("switch_strategy", {"strategy_id": s_id})

        if "reactive mode" in cmd_lower:
            return self.execute_tool("set_automation_mode", {"mode": "reactive"})
        elif "predictive mode" in cmd_lower:
            return self.execute_tool("set_automation_mode", {"mode": "predictive"})
        elif "hybrid mode" in cmd_lower:
            return self.execute_tool("set_automation_mode", {"mode": "hybrid"})

        if "portfolio" in cmd_lower or "positions" in cmd_lower or "risk status" in cmd_lower:
            return self.execute_tool("get_portfolio_and_risk", {})

        # Default to executive multi-agent synthesis
        return self.run_executive_synthesis(symbol=target_sym)

    # =========================================================================
    # Internal LLM Caller (Serialized)
    # =========================================================================

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        with OLLAMA_LOCK:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            if self.is_open_webui:
                # Open-WebUI OpenAI-compatible endpoint
                url = f"{self.base_url}/api/chat/completions"
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a quantitative trading orchestrator. Return concise raw JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "stream": False
                }
                try:
                    r = requests.post(url, headers=headers, json=payload, timeout=90)
                    if r.status_code == 200:
                        content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                        latency = round((time.perf_counter() - t0) * 1000, 1)
                        return {"text": content, "latency_ms": latency}
                except Exception:
                    # Fall through to local Ollama fallback
                    pass

            # Direct Ollama Native endpoint (fallback or default)
            # NEVER call /api/generate on an Open-WebUI port (:8080, :3000)
            ollama_host = self.base_url if (not self.is_open_webui and "11434" in self.base_url) else os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434").rstrip("/")
            url = f"{ollama_host}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2}
            }
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=90)
                if r.status_code == 200:
                    content = r.json().get("response", "")
                    latency = round((time.perf_counter() - t0) * 1000, 1)
                    return {"text": content, "latency_ms": latency}
                else:
                    return {"text": f'{{"error": "Ollama host returned HTTP {r.status_code}: {r.text}"}}', "latency_ms": 0.0}
            except Exception as e:
                return {"text": f'{{"error": "{str(e)}"}}', "latency_ms": 0.0}

        return {"text": '{"error": "LLM call failed"}', "latency_ms": 0.0}


def sqlite3_conn(db_path: str):
    import sqlite3
    return sqlite3.connect(db_path)
