"""
title: TraderCore Quant Hub Tools
author: MoneyMakingMachine / QWERTY CORP
description: Connects Open-WebUI models and autonomous pipelines to trader-core multi-agent algorithmic trading workstation.
version: 1.0.0
license: MIT
requirements: requests, pydantic
"""

import json
import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        trader_core_url: str = Field(
            default="http://127.0.0.1:5000",
            description="Base URL for trader-core dashboard API (e.g., http://localhost:5000 or LAN IP)"
        )
        api_timeout: int = Field(
            default=30,
            description="HTTP request timeout in seconds"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _call_gateway(self, tool_name: str, arguments: dict) -> dict:
        url = f"{self.valves.trader_core_url.rstrip('/')}/api/orchestrator/tools/call"
        try:
            r = requests.post(
                url,
                json={"name": tool_name, "arguments": arguments},
                timeout=self.valves.api_timeout
            )
            if r.status_code == 200:
                data = r.json()
                return data.get("result", data)
            return {"error": f"HTTP {r.status_code}: {r.text}"}
        except Exception as e:
            return {"error": f"Connection failed to trader-core at {url}: {str(e)}"}

    def get_market_intelligence(self, symbol: str = "ETH") -> str:
        """
        Fetch real-time social sentiment from Twitter/X & Discord trade channels,
        breaking financial news, and Tier-1 economic event calendar with countdowns from Agent C.
        :param symbol: Asset ticker symbol (e.g. ETH, BTC, SPY, NVDA, TSLA)
        :return: JSON formatted string containing multi-source sentiment and macro risk telemetry.
        """
        res = self._call_gateway("get_market_intelligence", {"symbol": symbol})
        return json.dumps(res, indent=2)

    def evaluate_price_action(self, symbol: str = "ETH") -> str:
        """
        Evaluate institutional Price Action structure: swing high/low pivots,
        liquidity sweeps, pinbar rejections, Break of Structure (BOS), and Volume Profile (POC/VAH/VAL).
        :param symbol: Ticker symbol (e.g. ETH, BTC, SOL)
        :return: JSON formatted string containing verified market structure metrics.
        """
        res = self._call_gateway("evaluate_price_action", {"symbol": symbol})
        return json.dumps(res, indent=2)

    def get_portfolio_and_risk(self) -> str:
        """
        Get current account environment (DEMO vs REAL), active trading strategy,
        automation mode (reactive/predictive/hybrid), open positions, and RiskSentinel parameters.
        :return: JSON formatted string of current portfolio and risk envelope.
        """
        res = self._call_gateway("get_portfolio_and_risk", {})
        return json.dumps(res, indent=2)

    def switch_strategy(self, strategy_id: str) -> str:
        """
        Switch the active algorithmic strategy across the quantitative engine.
        :param strategy_id: Strategy identifier (e.g. price_action, atr_trailing_breakout, fvg_breakout, rsi_reversion, london_ny_overlap)
        :return: Confirmation of the strategy change.
        """
        res = self._call_gateway("switch_strategy", {"strategy_id": strategy_id})
        return json.dumps(res, indent=2)

    def set_automation_mode(self, mode: str) -> str:
        """
        Set execution engine automation mode.
        :param mode: Execution mode: 'reactive' (non-predictive price action only), 'predictive' (quant models), or 'hybrid'
        :return: Confirmation of the mode update.
        """
        res = self._call_gateway("set_automation_mode", {"mode": mode})
        return json.dumps(res, indent=2)

    def submit_order(
        self,
        symbol: str,
        side: str,
        target_allocation_usd: float = 50.0,
        units: float = 0.0
    ) -> str:
        """
        Validate and submit a trading order through RiskSentinel capital preservation guardrails.
        Defaults safely to practice/demo execution unless live capital is explicitly unlocked in trader-core.
        :param symbol: Asset symbol (e.g. ETH, BTC)
        :param side: 'BUY' or 'SELL'
        :param target_allocation_usd: Target trade allocation in USD (default $50.0)
        :param units: Asset units (optional, computed automatically from target allocation if 0)
        :return: Order fill status and RiskSentinel execution parameters.
        """
        res = self._call_gateway("submit_order", {
            "symbol": symbol,
            "side": side,
            "target_allocation_usd": target_allocation_usd,
            "units": units,
            "force_live": False
        })
        return json.dumps(res, indent=2)

    def run_executive_synthesis(self, symbol: str = "ETH") -> str:
        """
        Trigger an autonomous multi-agent synthesis: reconciles Agent A (Price Action & Structure),
        Agent B (Quant Reasoner), Agent C (Social Sentiment & Macro Calendar), and RiskSentinel
        into an actionable executive trading directive.
        :param symbol: Asset symbol (e.g. ETH, BTC, SPY)
        :return: Executive trade directive with invalidation levels, take profit, and allocation.
        """
        url = f"{self.valves.trader_core_url.rstrip('/')}/api/orchestrator/synthesize"
        try:
            r = requests.post(url, json={"symbol": symbol}, timeout=self.valves.api_timeout)
            if r.status_code == 200:
                return json.dumps(r.json(), indent=2)
            return json.dumps({"error": f"HTTP {r.status_code}: {r.text}"})
        except Exception as e:
            return json.dumps({"error": f"Failed to synthesize via trader-core: {str(e)}"})
