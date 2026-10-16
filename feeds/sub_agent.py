import os
import re
import json
import requests
from typing import Dict, Any, List

class TwoTierQuantAgent:
    """
    Two-Tier Sub-Agent Pipeline:
    Agent A (Llama 3.1 8B): Calls tools and structures technical & price action context.
    Agent B (DeepSeek-R1 7B): Strategic reasoning, institutional market structure analysis, and execution decisions.
    """
    def __init__(
        self,
        ollama_endpoint: str = None,
        dispatcher_model: str = "llama3.1:8b",
        reasoner_model: str = "deepseek-r1:7b"
    ):
        base = (ollama_endpoint or os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434")).rstrip("/")
        self.endpoint = f"{base}/api/chat"
        self.generate_url = f"{base}/api/generate"
        self.dispatcher_model = dispatcher_model
        self.reasoner_model = reasoner_model

    # --- Tool Definitions for Agent A ---
    @staticmethod
    def get_binance_metrics(symbol: str) -> Dict[str, Any]:
        """Fetch 1h candlestick data, RSI(14), and FVGs from Binance."""
        pair = f"{symbol.upper()}USDT" if not symbol.endswith("USDT") else symbol.upper()
        try:
            r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=1h&limit=30", timeout=5)
            if r.status_code != 200:
                return {"error": f"Failed Binance API response: {r.status_code}"}
            candles = [{"high": float(k[2]), "low": float(k[3]), "close": float(k[4])} for k in r.json()]
            closes = [c["close"] for c in candles]

            # RSI 14
            gains, losses = [], []
            for i in range(1, len(closes)):
                diff = closes[i] - closes[i - 1]
                gains.append(diff if diff >= 0 else 0.0)
                losses.append(abs(diff) if diff < 0 else 0.0)
            avg_gain = sum(gains[-14:]) / 14.0
            avg_loss = sum(losses[-14:]) / 14.0
            rsi = 100.0 if avg_loss == 0 else round(100.0 - (100.0 / (1.0 + (avg_gain / avg_loss))), 2)

            # FVG Detection
            fvgs = []
            for i in range(2, len(candles)):
                c1, c3 = candles[i - 2], candles[i]
                if c3["low"] > c1["high"]:
                    fvgs.append(f"Bullish FVG: {c1['high']} - {c3['low']}")
                elif c3["high"] < c1["low"]:
                    fvgs.append(f"Bearish FVG: {c3['high']} - {c1['low']}")

            return {
                "symbol": symbol.upper(),
                "price": closes[-1],
                "change_24h": round(((closes[-1] - closes[0]) / closes[0]) * 100, 2),
                "rsi_14": rsi,
                "fvgs": fvgs[-2:] if fvgs else ["No active imbalances"]
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_price_action_metrics(symbol: str) -> Dict[str, Any]:
        """Fetch candles and analyze swing pivots, sweeps, pinbar rejections, and BOS."""
        pair = f"{symbol.upper()}USDT" if not symbol.endswith("USDT") else symbol.upper()
        try:
            r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=1h&limit=50", timeout=5)
            if r.status_code != 200:
                return {"error": f"Failed Binance API response: {r.status_code}"}
            candles = [
                {
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
                for k in r.json()
            ]
            from strategies.price_action import PriceActionStrategy
            strat = PriceActionStrategy()
            structure = strat.analyze_market_structure(candles)
            structure["symbol"] = symbol.upper()
            return structure
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_liquidity_clusters(symbol: str) -> Dict[str, Any]:
        """Fetch candles and calculate Volume Profile (POC/VAH/VAL) and liquidation clusters."""
        pair = f"{symbol.upper()}USDT" if not symbol.endswith("USDT") else symbol.upper()
        try:
            r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=1h&limit=100", timeout=5)
            if r.status_code != 200:
                return {"error": f"Failed Binance API response: {r.status_code}"}
            from datetime import datetime, timezone
            from quant_trading.liquidity import calculate_volume_profile, estimate_liquidation_clusters, detect_cme_gaps
            candles = [
                {
                    "timestamp": datetime.fromtimestamp(k[0] / 1000.0, tz=timezone.utc).isoformat(),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
                for k in r.json()
            ]
            current_price = candles[-1]["close"]
            vp = calculate_volume_profile(candles, num_bins=40)
            liq = estimate_liquidation_clusters(current_price)
            cme = detect_cme_gaps(candles)
            return {
                "symbol": symbol.upper(),
                "current_price": current_price,
                "volume_profile": vp,
                "liquidation_clusters": liq,
                "cme_gaps": cme,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_broker_risk_envelope() -> Dict[str, Any]:
        """Fetch internal risk parameters and portfolio balance limits."""
        return {
            "max_allocation_per_trade_usd": 50.0,
            "max_open_positions": 5,
            "min_risk_reward_ratio": 2.0,
            "max_drawdown_limit_pct": 3.0
        }

    # --- Agent A: Tool Dispatcher ---
    def run_dispatcher(self, user_query: str) -> Dict[str, Any]:
        tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "get_binance_metrics",
                    "description": "Fetch live market prices, 14-period RSI, and Fair Value Gaps for a crypto symbol.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Ticker symbol, e.g. ETH, BTC, SOL"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_price_action_metrics",
                    "description": "Fetch institutional market structure, swing pivots, liquidity sweeps, pinbar rejections, and BOS.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Ticker symbol, e.g. ETH, BTC, SOL"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_liquidity_clusters",
                    "description": "Fetch Volume Profile (POC, VAH, VAL, LVN) and estimated liquidation clusters for a symbol.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Ticker symbol, e.g. ETH, BTC, SOL"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_broker_risk_envelope",
                    "description": "Get runtime risk rules, max allocation size, and position caps.",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]

        messages = [
            {"role": "system", "content": "You are a tool dispatcher. Call the necessary tools to gather market, price action, and risk telemetry before handing off to reasoning."},
            {"role": "user", "content": user_query}
        ]

        tool_results = {}
        try:
            r = requests.post(self.endpoint, json={
                "model": self.dispatcher_model,
                "messages": messages,
                "tools": tools_schema,
                "stream": False
            }, timeout=30)
            res = r.json()
            tool_calls = res.get("message", {}).get("tool_calls", [])

            for call in tool_calls:
                fn_name = call.get("function", {}).get("name")
                args = call.get("function", {}).get("arguments", {})
                if fn_name == "get_binance_metrics":
                    sym = args.get("symbol", "ETH")
                    tool_results["market_data"] = self.get_binance_metrics(sym)
                elif fn_name == "get_price_action_metrics":
                    sym = args.get("symbol", "ETH")
                    tool_results["price_action"] = self.get_price_action_metrics(sym)
                elif fn_name == "get_liquidity_clusters":
                    sym = args.get("symbol", "ETH")
                    tool_results["liquidity_clusters"] = self.get_liquidity_clusters(sym)
                elif fn_name == "get_broker_risk_envelope":
                    tool_results["risk_rules"] = self.get_broker_risk_envelope()

        except Exception as e:
            tool_results["dispatcher_fallback"] = str(e)

        # Fallback if dispatcher fails or detects no tools
        match = re.search(r"\b(ETH|BTC|SOL|ADA|AVAX|XRP|DOGE)\b", user_query.upper())
        target_sym = match.group(1) if match else "ETH"
        if "market_data" not in tool_results:
            tool_results["market_data"] = self.get_binance_metrics(target_sym)
        if "price_action" not in tool_results:
            tool_results["price_action"] = self.get_price_action_metrics(target_sym)
        if "liquidity_clusters" not in tool_results:
            tool_results["liquidity_clusters"] = self.get_liquidity_clusters(target_sym)
        if "risk_rules" not in tool_results:
            tool_results["risk_rules"] = self.get_broker_risk_envelope()

        return tool_results

    # --- Agent B: Quant Reasoner ---
    def run_reasoner(self, strategy_name: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are a quantitative strategist executing a strictly REACTIVE, NON-PREDICTIVE institutional Price Action framework.
DO NOT attempt to forecast or predict future market direction. React ONLY to verified price action patterns that have already printed.

TELEMETRY CONTEXT:
{json.dumps(telemetry, indent=2)}

ACTIVE STRATEGY:
{strategy_name}

RULES:
1. NON-PREDICTIVE MANDATE: Never buy or sell based on predictive indicator guesses (e.g. oversold/overbought RSI alone is strictly forbidden as an entry trigger).
2. CONFIRMED BUY TRIGGERS: Execute BUY only on a confirmed Bullish Liquidity Sweep (pinbar hammer rejecting below prior low), Bullish Break of Structure (BOS), Bullish Change of Character (ChoCH), or Bullish FVG Mitigation Retest.
3. CONFIRMED SELL/EXIT TRIGGERS: Execute SELL/EXIT on a confirmed Bearish Liquidity Sweep (shooting star rejecting above prior high), Bearish BOS, Bearish ChoCH, or Bearish FVG Retest.
4. STRUCTURAL INVALIDATION: Anchor suggested_sl strictly to the extreme structural wick of the pattern (below sweep low for BUY; above sweep high for SELL).
5. MANDATORY 1:2 R:R: Ensure suggested_tp provides at least a 1:2 Risk-to-Reward ratio relative to the invalidation stop loss.
6. MANDATORY HOLD: If no confirmed structural Price Action setup is currently active, return action "HOLD" with target_allocation_usd 0.0. Cash is a strategic position.
7. ALLOCATION GUARDRAILS: Respect allocation limits ($50 max per trade).
8. Return STRICT RAW JSON ONLY matching this schema:
{{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": <float 0.0 to 1.0>,
  "reason": "<concise summary identifying the confirmed Price Action setup and invalidation level>",
  "target_allocation_usd": <float>,
  "suggested_sl": <float>,
  "suggested_tp": <float>
}}
"""
        try:
            r = requests.post(self.generate_url, json={
                "model": self.reasoner_model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }, timeout=90)
            res_text = r.json().get("response", "{}")
            # Strip internal <think>...</think> tags emitted by DeepSeek-R1
            clean_json_str = re.sub(r"<think>.*?</think>", "", res_text, flags=re.DOTALL).strip()
            return json.loads(clean_json_str)
        except Exception as e:
            return {"action": "HOLD", "reason": f"Reasoner error: {str(e)}", "confidence": 0.0}

    # --- Full Pipeline Execution ---
    def execute(self, query: str, strategy_name: str = "Price_Action") -> Dict[str, Any]:
        # Step 1: Agent A collects live data & price action structure
        context = self.run_dispatcher(query)
        # Step 2: Agent B produces final execution parameters
        decision = self.run_reasoner(strategy_name, context)
        return {
            "dispatcher_telemetry": context,
            "quant_decision": decision
        }
