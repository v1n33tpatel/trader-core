import requests
import json

class AIStrategyReasoner:
    def __init__(self, ollama_host: str = "http://192.168.2.15:11434", model: str = "deepseek-r1"):
        self.ollama_url = f"{ollama_host}/api/generate"
        self.model = model

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
