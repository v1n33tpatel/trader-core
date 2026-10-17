import os
import requests
import json
from feeds.ai_provider import AIProviderClient
from core.state_store import StateStore

class AIStrategyReasoner:
    def __init__(self, ollama_host: str = None, model: str = None, provider_client: AIProviderClient = None):
        if provider_client:
            self.client = provider_client
        else:
            store = StateStore()
            provider = store.get_setting("ai_provider", "ollama")
            ext_url = store.get_setting("external_ai_base_url", os.getenv("EXTERNAL_AI_BASE_URL", "https://openrouter.ai/api/v1"))
            ext_key = store.get_setting("external_ai_api_key", os.getenv("EXTERNAL_AI_API_KEY", ""))
            ext_model = store.get_setting("external_ai_model", os.getenv("EXTERNAL_AI_MODEL", "deepseek/deepseek-r1"))
            
            self.client = AIProviderClient(
                provider=provider,
                ollama_host=ollama_host,
                ollama_model=model,
                external_base_url=ext_url,
                external_api_key=ext_key,
                external_model=ext_model,
                fallback_to_local=True
            )
        self.model = self.client.external_model if self.client.provider == "external" else self.client.ollama_model

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
        res = self.client.generate(prompt)
        return res.get("text", "No response generated.")


    def analyze_price_action(self, symbol: str, price_action_data: dict, current_price: float = None):
        prompt = f"""
You are an expert institutional Price Action quantitative strategist operating under a strict NON-PREDICTIVE mandate.
Do NOT attempt to forecast or predict future market direction. Classify and react ONLY to confirmed structural events that have already printed.

Market Structure Telemetry for {symbol}:
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
1. Market Structure Classification (Pivots, BOS, ChoCH)
2. Liquidity & Order Flow Assessment (Sweeps & Wick Rejections)
3. Trade Recommendation (BUY, SELL, or mandatory HOLD if no confirmed structural pattern is present; state exact Invalidation and R:R Target)
"""
        res = self.client.generate(prompt)
        return res.get("text", "No response generated.")

