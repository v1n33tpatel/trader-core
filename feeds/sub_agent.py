import re
import json
import requests
from typing import Dict, Any, List

class TwoTierQuantAgent:
    """
    Two-Tier Sub-Agent Pipeline:
    Agent A (Llama 3.1 8B): Calls tools and structures technical context.
    Agent B (DeepSeek-R1 7B): Strategic reasoning and risk-governed execution decisions.
    """
    def __init__(
        self,
        ollama_endpoint: str = "http://10.10.10.15:11434",
        dispatcher_model: str = "llama3.1:8b",
        reasoner_model: str = "deepseek-r1:7b"
    ):
        self.endpoint = f"{ollama_endpoint}/api/chat"
        self.generate_url = f"{ollama_endpoint}/api/generate"
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
                    "name": "get_broker_risk_envelope",
                    "description": "Get runtime risk rules, max allocation size, and position caps.",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]

        messages = [
            {"role": "system", "content": "You are a tool dispatcher. Call the necessary tools to gather telemetry before handing off to reasoning."},
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
                elif fn_name == "get_broker_risk_envelope":
                    tool_results["risk_rules"] = self.get_broker_risk_envelope()

        except Exception as e:
            tool_results["dispatcher_fallback"] = str(e)

        # Fallback if dispatcher fails or detects no tools
        if "market_data" not in tool_results:
            match = re.search(r"\b(ETH|BTC|SOL|ADA|AVAX|XRP|DOGE)\b", user_query.upper())
            target_sym = match.group(1) if match else "ETH"
            tool_results["market_data"] = self.get_binance_metrics(target_sym)
        if "risk_rules" not in tool_results:
            tool_results["risk_rules"] = self.get_broker_risk_envelope()

        return tool_results

    # --- Agent B: Quant Reasoner ---
    def run_reasoner(self, strategy_name: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are a quantitative strategist. Analyze the extracted telemetry against our risk rules and produce a trading decision.

TELEMETRY CONTEXT:
{json.dumps(telemetry, indent=2)}

ACTIVE STRATEGY:
{strategy_name}

RULES:
1. BUY requires oversold RSI (<35) or bullish structure.
2. Respect allocation and stop-loss limits.
3. Return STRICT RAW JSON ONLY matching this schema:
{{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": <float 0.0 to 1.0>,
  "reason": "<concise summary>",
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
    def execute(self, query: str, strategy_name: str = "RSI_Mean_Reversion") -> Dict[str, Any]:
        # Step 1: Agent A collects live data
        context = self.run_dispatcher(query)
        # Step 2: Agent B produces final execution parameters
        decision = self.run_reasoner(strategy_name, context)
        return {
            "dispatcher_telemetry": context,
            "quant_decision": decision
        }
