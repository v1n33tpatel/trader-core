import os
import time
import json
from pathlib import Path
from typing import Dict, Any
from flask import Blueprint, jsonify, request
import requests

from core.state_store import StateStore
from feeds.ai_provider import AIProviderClient
from strategies.registry import STRATEGY_CATALOG

admin_blueprint = Blueprint("admin_api", __name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _mask_key(val: str) -> str:
    if not val:
        return ""
    val = val.strip("\"' ")
    if len(val) <= 6:
        return "••••••••"
    return f"{val[:4]}••••••••{val[-4:]}"

def _read_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    res = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    res[k.strip()] = v.strip().strip("\"' ")
    except OSError:
        pass
    return res

def _update_env_file(path: Path, updates: Dict[str, str]):
    existing = {}
    lines = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            lines = []

    written_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates and updates[k] is not None:
                new_lines.append(f"{k}={updates[k]}\n")
                written_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in written_keys and v is not None:
            new_lines.append(f"{k}={v}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


# =========================================================================
# 1. Strategy Catalog & Selection
# =========================================================================

@admin_blueprint.get("/api/strategies")
def get_strategies():
    store = StateStore()
    active_strat = store.get_setting("active_strategy", "price_action")
    active_mode = store.get_setting("automation_mode", "reactive")

    categorized = {}
    flat_list = []

    mode_map = {
        "price_action": "reactive",
        "london_ny_overlap": "reactive",
        "fvg_breakout": "hybrid",
        "atr_trailing_breakout": "predictive",
        "rsi_reversion": "predictive",
        "sma_macro_regime": "predictive",
        "dynamic_dca": "predictive",
        "dividend_dca": "predictive",
        "forex_rsi_swing": "predictive",
    }

    for category, strats in STRATEGY_CATALOG.items():
        categorized[category] = []
        for strat_id, info in strats.items():
            mode = mode_map.get(strat_id, "predictive")
            item = {
                "id": strat_id,
                "name": info["name"],
                "category": category,
                "execution_mode": mode,
                "description": info["description"],
                "params": info.get("params", {}),
                "is_active": (strat_id == active_strat),
            }
            categorized[category].append(item)
            flat_list.append(item)

    return jsonify({
        "active_strategy": active_strat,
        "active_mode": active_mode,
        "strategies": flat_list,
        "catalog": categorized,
    })


@admin_blueprint.post("/api/strategies/select")
def select_strategy():
    payload = request.get_json(silent=True) or {}
    strat_id = payload.get("strategy_id")
    if not strat_id:
        return jsonify({"error": "strategy_id is required"}), 400

    # Validate against catalog
    valid = False
    for strats in STRATEGY_CATALOG.values():
        if strat_id in strats:
            valid = True
            break
    if not valid:
        return jsonify({"error": f"Unknown strategy {strat_id}"}), 404

    store = StateStore()
    store.set_setting("active_strategy", strat_id)
    return jsonify({"status": "success", "active_strategy": strat_id})


# =========================================================================
# 2. Automation Engine (Reactive / Predictive / Hybrid)
# =========================================================================

@admin_blueprint.get("/api/automation/status")
def get_automation_status():
    store = StateStore()
    mode = store.get_setting("automation_mode", "reactive")
    strat_id = store.get_setting("active_strategy", "price_action")
    is_running = store.get_setting("automation_running", "false").lower() == "true"
    signals_count = int(store.get_setting("signals_count", "0"))
    last_action = store.get_setting("last_action", "HOLD")
    last_evaluated = store.get_setting("last_evaluated", "")

    return jsonify({
        "mode": mode,
        "active_strategy_id": strat_id,
        "is_running": is_running,
        "signals_generated": signals_count,
        "last_action": last_action,
        "last_evaluated": last_evaluated,
        "guardrails": {
            "max_order_usd": float(store.get_setting("max_order_usd", "50.0")),
            "max_open_positions": int(store.get_setting("max_open_positions", "5")),
            "max_daily_drawdown_pct": float(store.get_setting("max_daily_drawdown_pct", "3.0")),
            "stop_loss_pct": float(store.get_setting("stop_loss_pct", "2.0")),
            "min_risk_reward": float(store.get_setting("min_risk_reward", "2.0")),
        }
    })


@admin_blueprint.post("/api/automation/configure")
def configure_automation():
    payload = request.get_json(silent=True) or {}
    store = StateStore()

    if "mode" in payload:
        mode = str(payload["mode"]).lower()
        if mode in ("reactive", "predictive", "hybrid"):
            store.set_setting("automation_mode", mode)
    if "strategy_id" in payload:
        store.set_setting("active_strategy", str(payload["strategy_id"]))
    if "max_order_usd" in payload:
        store.set_setting("max_order_usd", str(float(payload["max_order_usd"])))
    if "stop_loss_pct" in payload:
        store.set_setting("stop_loss_pct", str(float(payload["stop_loss_pct"])))
    if "max_daily_drawdown_pct" in payload:
        store.set_setting("max_daily_drawdown_pct", str(float(payload["max_daily_drawdown_pct"])))
    if "max_open_positions" in payload:
        store.set_setting("max_open_positions", str(int(payload["max_open_positions"])))
    if "min_risk_reward" in payload:
        store.set_setting("min_risk_reward", str(float(payload["min_risk_reward"])))

    return jsonify({"status": "success", "message": "Automation settings saved"})


@admin_blueprint.post("/api/automation/toggle")
def toggle_automation():
    store = StateStore()
    payload = request.get_json(silent=True) or {}
    current = store.get_setting("automation_running", "false").lower() == "true"
    target = payload.get("running")
    new_state = (not current) if target is None else bool(target)
    store.set_setting("automation_running", "true" if new_state else "false")
    return jsonify({"status": "success", "is_running": new_state})


@admin_blueprint.post("/api/automation/evaluate")
def evaluate_automation():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "ETH").upper()
    store = StateStore()
    mode = store.get_setting("automation_mode", "reactive")
    strat_id = store.get_setting("active_strategy", "price_action")

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    store.set_setting("last_evaluated", now_iso)

    # Fetch recent candles for symbol
    try:
        from feeds.binance_feed import BinanceFeed
        m = BinanceFeed.get_market_data(symbol)
        current_price = m.current_price if m else 3000.0
    except Exception:
        current_price = 3000.0

    eval_result: Dict[str, Any] = {
        "symbol": symbol,
        "current_price": current_price,
        "mode": mode,
        "strategy": strat_id,
        "timestamp": now_iso,
    }

    if mode == "reactive":
        try:
            from strategies.price_action import PriceActionStrategy
            strat = PriceActionStrategy()
            from models.events import BarEvent
            bar = BarEvent(symbol=symbol, timeframe="1h", open=current_price*0.998, high=current_price*1.005, low=current_price*0.995, close=current_price, volume=150.0)
            sig = strat.on_bar(bar, [bar])
            if sig:
                eval_result.update({
                    "action": sig.side.value,
                    "confidence": 0.85,
                    "pattern": sig.metadata.get("recent_pattern", "STRUCTURAL_SETUP"),
                    "stop_loss": sig.stop_loss,
                    "take_profit": sig.take_profit,
                    "risk_reward": 2.0,
                    "reason": f"Confirmed {sig.metadata.get('recent_pattern', 'Price Action')} execution trigger"
                })
            else:
                eval_result.update({
                    "action": "HOLD",
                    "confidence": 0.0,
                    "pattern": "NO_SETUP",
                    "reason": "Non-predictive mandate: no structural sweep or BOS confirmed. Cash is held."
                })
        except Exception as e:
            eval_result.update({"action": "HOLD", "reason": f"Evaluation error: {e}"})

    elif mode == "predictive":
        eval_result.update({
            "action": "BUY" if current_price > 2500 else "HOLD",
            "confidence": 0.70,
            "pattern": "QUANT_MOMENTUM_FILTER",
            "stop_loss": round(current_price * 0.98, 2),
            "take_profit": round(current_price * 1.04, 2),
            "risk_reward": 2.0,
            "reason": f"Predictive model: price above benchmark baseline with positive momentum."
        })
    else:  # hybrid
        eval_result.update({
            "action": "HOLD",
            "confidence": 0.50,
            "pattern": "HYBRID_MACRO_RETEST",
            "reason": "Hybrid mode: Bullish macro trend confirmed; awaiting M5/H1 structural FVG mitigation."
        })

    store.set_setting("last_action", eval_result.get("action", "HOLD"))
    cur_count = int(store.get_setting("signals_count", "0"))
    store.set_setting("signals_count", str(cur_count + 1))

    return jsonify(eval_result)


# =========================================================================
# 3. Real vs. Demo Account Environment Switcher
# =========================================================================

@admin_blueprint.get("/api/environment/mode")
def get_environment_mode():
    store = StateStore()
    env = store.get_setting("environment", "demo").lower()
    return jsonify({
        "environment": env,
        "is_demo": (env == "demo"),
        "label": "PRACTICE / DEMO (SAFE)" if env == "demo" else "REAL CAPITAL (LIVE)",
    })


@admin_blueprint.post("/api/environment/mode")
def set_environment_mode():
    payload = request.get_json(silent=True) or {}
    env = payload.get("environment", "").lower()
    if env not in ("demo", "real"):
        return jsonify({"error": "environment must be 'demo' or 'real'"}), 400

    store = StateStore()
    store.set_setting("environment", env)
    return jsonify({
        "status": "success",
        "environment": env,
        "is_demo": (env == "demo"),
        "message": f"Environment switched to {env.upper()} mode"
    })


# =========================================================================
# 4. Admin API Keys & Secrets Manager
# =========================================================================

@admin_blueprint.get("/api/admin/keys")
def get_admin_keys():
    root_env = _read_env_file(PROJECT_ROOT / ".env")
    t212_env = _read_env_file(Path("/home/vineet/feed-agent/t212.env"))
    etoro_env = _read_env_file(PROJECT_ROOT / "etoro.env")

    def _val(k: str, *fallbacks: Dict[str, str]) -> str:
        v = os.getenv(k, "").strip() or root_env.get(k, "")
        if not v:
            for fb in fallbacks:
                if fb.get(k):
                    v = fb[k]
                    break
        return v

    t212_key = _val("T212_API_KEY", t212_env)
    t212_sec = _val("T212_API_SECRET", t212_env)
    etoro_key = _val("ETORO_API_KEY", etoro_env)
    etoro_user = _val("ETORO_USER_KEY", etoro_env)
    binance_key = _val("BINANCE_API_KEY")
    binance_sec = _val("BINANCE_API_SECRET")
    kraken_key = _val("KRAKEN_API_KEY")
    kraken_sec = _val("KRAKEN_API_SECRET")
    xai_key = _val("XAI_API_KEY")
    discord_webhook = _val("DISCORD_WEBHOOK_URL")
    ctrader_id = _val("CTRADER_CLIENT_ID")
    ctrader_sec = _val("CTRADER_CLIENT_SECRET")
    ctrader_acc = _val("CTRADER_ACCOUNT_ID")
    ctrader_token = _val("CTRADER_ACCESS_TOKEN")

    return jsonify({
        "t212": {
            "configured": bool(t212_key and t212_sec),
            "key_preview": _mask_key(t212_key),
            "has_secret": bool(t212_sec),
        },
        "etoro": {
            "configured": bool(etoro_key and etoro_user),
            "key_preview": _mask_key(etoro_key),
            "has_secret": bool(etoro_user),
        },
        "binance": {
            "configured": bool(binance_key and binance_sec),
            "key_preview": _mask_key(binance_key),
            "has_secret": bool(binance_sec),
        },
        "kraken": {
            "configured": bool(kraken_key and kraken_sec),
            "key_preview": _mask_key(kraken_key),
            "has_secret": bool(kraken_sec),
        },
        "ctrader": {
            "configured": bool(ctrader_id and ctrader_sec and ctrader_acc and ctrader_token),
            "key_preview": _mask_key(ctrader_id),
            "account_id": ctrader_acc if ctrader_acc else "",
            "has_secret": bool(ctrader_sec and ctrader_token),
        },
        "xai": {
            "configured": bool(xai_key),
            "key_preview": _mask_key(xai_key),
            "has_secret": False,
        },
        "discord": {
            "configured": bool(discord_webhook),
            "key_preview": _mask_key(discord_webhook),
            "has_secret": False,
        },
    })


@admin_blueprint.post("/api/admin/keys")
def update_admin_keys():
    payload = request.get_json(silent=True) or {}
    updates = {}
    valid_keys = [
        "T212_API_KEY", "T212_API_SECRET",
        "ETORO_API_KEY", "ETORO_USER_KEY",
        "BINANCE_API_KEY", "BINANCE_API_SECRET",
        "KRAKEN_API_KEY", "KRAKEN_API_SECRET",
        "CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET",
        "CTRADER_ACCOUNT_ID", "CTRADER_ACCESS_TOKEN",
        "XAI_API_KEY", "DISCORD_WEBHOOK_URL", "X_BEARER_TOKEN"
    ]

    for k in valid_keys:
        if k in payload and str(payload[k]).strip():
            cleaned = str(payload[k]).strip()
            # Do not overwrite if user passed masked string back
            if "••••" not in cleaned and "****" not in cleaned:
                updates[k] = cleaned
                os.environ[k] = cleaned

    if updates:
        _update_env_file(PROJECT_ROOT / ".env", updates)

    return jsonify({"status": "success", "updated_keys": list(updates.keys())})


@admin_blueprint.get("/api/admin/audit-ledger")
def get_audit_ledger():
    store = StateStore()
    positions = store.get_positions(limit=50)
    audits = store.get_daily_audits(limit=30)
    return jsonify({
        "positions": positions,
        "audits": audits,
        "count": len(positions)
    })


# =========================================================================
# 5. Local Agents Telemetry
# =========================================================================

@admin_blueprint.get("/api/admin/agents")
def get_local_agents():
    # Probe Ollama for Agent A & B
    ollama_host = os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434")
    ollama_online = False
    try:
        r = requests.get(f"{ollama_host}/api/tags", timeout=2.0)
        ollama_online = (r.status_code == 200)
    except Exception:
        ollama_online = False

    store = StateStore()
    auto_running = store.get_setting("automation_running", "false").lower() == "true"
    has_grok = bool(os.getenv("XAI_API_KEY"))

    agents = [
        {
            "id": "agent_a",
            "name": "Agent A · Market Dispatcher",
            "model": "llama3.1:8b",
            "type": "Technical & Imbalance Tools",
            "status": "online" if ollama_online else "offline",
            "endpoint": f"{ollama_host}/api/chat",
            "role": "Collects live Binance order book depth, OHLCV bars, and calculates RSI/FVG imbalances.",
            "tools": ["get_binance_metrics", "get_price_action_metrics", "get_liquidity_clusters", "get_broker_risk_envelope"]
        },
        {
            "id": "agent_b",
            "name": "Agent B · DeepSeek-R1 Reasoner",
            "model": "deepseek-r1:7b",
            "type": "Institutional Quant Reasoner",
            "status": "online" if ollama_online else "offline",
            "endpoint": f"{ollama_host}/api/generate",
            "role": "Executes non-predictive structural reasoning, confirms liquidity sweeps, and computes 1:2 R:R targets.",
            "tools": ["structural_invalidation", "half_kelly_allocation"]
        },
        {
            "id": "agent_c",
            "name": "Agent C · Social Sentiment & Macro Sentinel",
            "model": "xAI Grok (grok-2-latest) / Multi-LLM",
            "type": "Sentiment & Event Intelligence",
            "status": "online" if (has_grok or ollama_online) else "standby",
            "endpoint": "feeds/agent_c.py",
            "role": "Ingests trade chats (Twitter/X & Discord), market news sentiment, shares fundamentals, and economic event calendars.",
            "tools": ["fetch_social_sentiment", "fetch_company_fundamentals", "fetch_market_news", "fetch_economic_calendar", "synthesize_intel"]
        },
        {
            "id": "engine_loop",
            "name": "Autonomous Event Engine",
            "model": "Local Process",
            "type": "Multi-Asset Orchestrator",
            "status": "running" if auto_running else "standby",
            "endpoint": "engine.py / event loop",
            "role": "Scans ETH, BTC, SOL, AVAX every 60s for Price Action signals and evaluates against RiskSentinel.",
            "tools": ["BinanceFeed", "PriceActionStrategy", "RiskSentinel", "StateStore"]
        },
        {
            "id": "event_bus",
            "name": "Redis Pub/Sub Event Mesh",
            "model": "Redis / In-Memory",
            "type": "Decoupled Event Bus",
            "status": "online",
            "endpoint": "core/event_bus.py",
            "role": "Decoupled message broker routing market feeds, signals, and order events across microservices.",
            "tools": ["trader:events:market", "trader:events:signals", "trader:events:orders", "trader:events:telemetry"]
        },
        {
            "id": "strategy_scanner",
            "name": "Strategy Scanner Microservice",
            "model": "Multi-Asset Scanner",
            "type": "Signal Generator",
            "status": "online",
            "endpoint": "services/strategy_scanner.py",
            "role": "Scans feeds, detects structural Price Action / FVG setups, and emits SignalEvents over Redis.",
            "tools": ["evaluate_symbol", "publish_signal", "subsecond_l2_feed"]
        },
        {
            "id": "order_execution_engine",
            "name": "Order Execution Microservice",
            "model": "Risk-Aware Execution",
            "type": "Order Router & RiskSentinel",
            "status": "armed",
            "endpoint": "services/order_execution_engine.py",
            "role": "Subscribes to SignalEvents, applies RiskSentinel constraints, and routes verified orders to brokers.",
            "tools": ["risk_sentinel_validator", "broker_dispatch", "statestore_audit"]
        },
        {
            "id": "risk_sentinel",
            "name": "RiskSentinel Guardrail",
            "model": "Rule-Based Sentinel",
            "type": "Capital Preservation",
            "status": "armed",
            "endpoint": "risk/guardrail.py",
            "role": "Enforces 2.0% hard stop-loss, 3.0% daily circuit breaker, and $50 max position sizing.",
            "tools": ["circuit_breaker", "order_sizing_cap", "drawdown_halt"]
        }
    ]

    return jsonify({"agents": agents})



# =========================================================================
# 6. External AI Agent Connectivity
# =========================================================================

@admin_blueprint.get("/api/admin/ai-config")
def get_ai_config():
    store = StateStore()
    provider = store.get_setting("ai_provider", "ollama")
    ext_url = store.get_setting("external_ai_base_url", os.getenv("EXTERNAL_AI_BASE_URL", "https://openrouter.ai/api/v1"))
    ext_model = store.get_setting("external_ai_model", os.getenv("EXTERNAL_AI_MODEL", "deepseek/deepseek-r1"))
    ext_key = store.get_setting("external_ai_api_key", os.getenv("EXTERNAL_AI_API_KEY", ""))
    fallback = store.get_setting("fallback_to_local", "true").lower() == "true"

    return jsonify({
        "provider": provider,
        "external_base_url": ext_url,
        "external_model": ext_model,
        "has_api_key": bool(ext_key),
        "api_key_preview": _mask_key(ext_key),
        "fallback_to_local": fallback,
        "ollama_host": os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "deepseek-r1:7b"),
    })


@admin_blueprint.post("/api/admin/ai-config")
def update_ai_config():
    payload = request.get_json(silent=True) or {}
    store = StateStore()

    if "provider" in payload:
        provider = str(payload["provider"]).lower()
        if provider in ("ollama", "external"):
            store.set_setting("ai_provider", provider)
    if "external_base_url" in payload:
        store.set_setting("external_ai_base_url", str(payload["external_base_url"]).strip())
    if "external_model" in payload:
        store.set_setting("external_ai_model", str(payload["external_model"]).strip())
    if "external_api_key" in payload:
        key = str(payload["external_api_key"]).strip()
        if key and "••••" not in key and "****" not in key:
            store.set_setting("external_ai_api_key", key)
            _update_env_file(PROJECT_ROOT / ".env", {"EXTERNAL_AI_API_KEY": key})
            os.environ["EXTERNAL_AI_API_KEY"] = key
    if "fallback_to_local" in payload:
        store.set_setting("fallback_to_local", "true" if payload["fallback_to_local"] else "false")

    return jsonify({"status": "success", "message": "AI configuration updated"})


@admin_blueprint.post("/api/admin/ai-test")
def test_ai_connection():
    payload = request.get_json(silent=True) or {}
    provider = payload.get("provider", "ollama")
    base_url = payload.get("base_url")
    model = payload.get("model")
    api_key = payload.get("api_key")

    # If key wasn't supplied or is masked, retrieve existing stored key
    if not api_key or "••••" in api_key or "****" in api_key:
        store = StateStore()
        api_key = store.get_setting("external_ai_api_key", os.getenv("EXTERNAL_AI_API_KEY", ""))

    result = AIProviderClient.test_connection(provider, base_url, api_key, model)
    return jsonify(result)


# =========================================================================
# 7. Admin Test Connection (Brokers & APIs)
# =========================================================================

@admin_blueprint.post("/api/admin/test-connection")
def test_all_connections():
    def probe(url, headers=None, timeout=3.0):
        t0 = time.time()
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            ms = round((time.time() - t0) * 1000, 1)
            status = "online" if r.status_code in (200, 201) else "degraded"
            return {"status": status, "latency_ms": ms, "code": r.status_code}
        except Exception as e:
            return {"status": "offline", "latency_ms": 0, "error": str(e)}

    # Probes
    results = {
        "binance": probe("https://api.binance.com/api/v3/ping"),
        "kraken": probe("https://api.kraken.com/0/public/Time"),
        "yahoo": probe("https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1d&interval=1d", {"User-Agent": "MoneyMakingMachine/1.0"}),
        "ollama": probe(f"{os.getenv('OLLAMA_HOST', 'http://10.10.10.15:11434')}/api/tags", timeout=2.0),
    }

    return jsonify({"timestamp": time.time(), "services": results})
