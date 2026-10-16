import os
import requests
import json

class AIStrategyReasoner:
    def __init__(self, ollama_host: str = None, model: str = None):
        host = (ollama_host or os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434")).rstrip("/")
        self.ollama_url = f"{host}/api/generate"
        self.model = model or os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")

    def analyze_macro_strategy(self, portfolio_cash, spy_price, spy_sma200, forex_data):
        prompt = f"""
You are an expert quantitative macro strategist managing a multi-asset portfolio. 
Analyze the following live market telemetry and provide a concise, professional assessment and rebalancing recommendation:

- T212 Practice Cash Available: ${portfolio_cash:.2f}
- S&P 500 (SPY) Price: ${spy_price:.2f}
- S&P 500 200-day SMA: ${spy_sma200:.2f} (Status: {'BULLISH' if spy_price > spy_sma200 else 'BEARISH'})
- Forex Telemetry: {json.dumps(forex_data)}

Provide your response structured as:
1. Macro Health Check
2. Asset Allocation Bias
3. Recommended Action
"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json().get("response", "No response generated.")
            else:
                return f"[AI-ERROR] Ollama returned status code {response.status_code}"
        except Exception as e:
            return f"[AI-ERROR] Failed to connect to DeepSeek-R1 stack: {e}"

    def analyze_price_action(self, symbol: str, price_action_data: dict, current_price: float = None):
        prompt = f"""
You are an expert institutional Price Action quantitative strategist.
Analyze the following market structure telemetry for {symbol} and produce a professional trading assessment:

- Symbol: {symbol}
- Current Price: ${current_price:.4f if current_price else 'N/A'}
- Market Structure Trend: {price_action_data.get('structure', 'N/A')}
- Recent Swing High: {price_action_data.get('last_swing_high', 'N/A')}
- Recent Swing Low: {price_action_data.get('last_swing_low', 'N/A')}
- Detected Pattern: {price_action_data.get('recent_pattern', 'None')}
- Bias: {price_action_data.get('bias', 'NEUTRAL')}
- Lower Wick Ratio: {price_action_data.get('lower_wick_ratio', 0.0) * 100:.1f}%
- Upper Wick Ratio: {price_action_data.get('upper_wick_ratio', 0.0) * 100:.1f}%
- Suggested Invalidation (SL): {price_action_data.get('suggested_sl', 'N/A')}
- Suggested Target (TP): {price_action_data.get('suggested_tp', 'N/A')}

Provide your response structured as:
1. Market Structure Analysis (Pivots & BOS)
2. Liquidity & Order Flow Assessment (Sweeps & Wick Rejection)
3. Trade Recommendation (BUY, SELL, or HOLD with clear Invalidation/Target rationale)
"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=35)
            if response.status_code == 200:
                return response.json().get("response", "No response generated.")
            else:
                return f"[AI-ERROR] Ollama returned status code {response.status_code}"
        except Exception as e:
            return f"[AI-ERROR] Failed to connect to DeepSeek-R1 stack: {e}"

