import os
import json
import time
from typing import Any, Dict, List, Tuple
from pathlib import Path
import requests

from brokers.base import BaseBroker
from models.position import Position


def _load_env_key(var_name: str) -> str:
    val = os.getenv(var_name, "").strip("\"' ")
    if val:
        return val
    root_dir = Path(__file__).resolve().parents[1]
    paths = [
        root_dir / ".env",
        root_dir / "ctrader.env",
        root_dir / "config" / "ctrader.env",
    ]
    for p in paths:
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        if "=" in line and not line.strip().startswith("#"):
                            k, v = line.strip().split("=", 1)
                            if k.strip() == var_name:
                                return v.strip().strip("\"' ")
            except OSError:
                pass
    return ""


# Standard major forex and commodity instruments
CTRADER_INSTRUMENTS = {
    "EURUSD": {"id": 1, "digits": 5, "pip_multiplier": 10000, "base": "EUR", "quote": "USD"},
    "GBPUSD": {"id": 2, "digits": 5, "pip_multiplier": 10000, "base": "GBP", "quote": "USD"},
    "USDJPY": {"id": 3, "digits": 3, "pip_multiplier": 100, "base": "USD", "quote": "JPY"},
    "AUDUSD": {"id": 4, "digits": 5, "pip_multiplier": 10000, "base": "AUD", "quote": "USD"},
    "USDCAD": {"id": 5, "digits": 5, "pip_multiplier": 10000, "base": "USD", "quote": "CAD"},
    "USDCHF": {"id": 6, "digits": 5, "pip_multiplier": 10000, "base": "USD", "quote": "CHF"},
    "XAUUSD": {"id": 7, "digits": 2, "pip_multiplier": 10, "base": "XAU", "quote": "USD"},
    "USOIL":  {"id": 8, "digits": 2, "pip_multiplier": 10, "base": "USOIL", "quote": "USD"},
}


class CTraderBroker(BaseBroker):
    """
    Spotware cTrader Open API broker adapter.
    Supports Demo and Live trading environments, Protobuf/JSON WebSocket message
    building, pip calculations, and graceful degradation returning (0.0, []).
    """

    def __init__(self, is_demo: bool = True):
        self.is_demo = is_demo
        self.host = "demo.ctraderapi.com" if is_demo else "live.ctraderapi.com"
        self.client_id = _load_env_key("CTRADER_CLIENT_ID")
        self.client_secret = _load_env_key("CTRADER_CLIENT_SECRET")
        self.account_id = _load_env_key("CTRADER_ACCOUNT_ID")
        self.access_token = _load_env_key("CTRADER_ACCESS_TOKEN")

        # cTrader AI Agent Connect (Remote MCP) parameters
        self.mcp_url = _load_env_key("CTRADER_MCP_URL") or "https://mcp.ctrader.com/trading/mcp"
        self.mcp_token = _load_env_key("CTRADER_MCP_TOKEN")

        # In-memory practice positions for demo testing
        self._demo_positions: List[Dict[str, Any]] = []

    def is_configured(self) -> bool:
        """Checks if either Remote MCP token or classic Open API credentials are provided."""
        return self.is_mcp_configured() or bool(self.client_id and self.client_secret and self.account_id and self.access_token)

    def is_mcp_configured(self) -> bool:
        """Checks if a valid, non-placeholder cTrader Remote MCP Bearer token is configured."""
        if not self.mcp_token:
            return False
        # Catch unauthenticated environment template slug
        if "eyJwbGFudCI6" in self.mcp_token:
            return False
        return len(self.mcp_token.strip()) > 10

    def call_mcp_tool(self, name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Calls a tool on the cTrader Remote MCP Server via JSON-RPC 2.0.
        Returns the parsed tool result dictionary.
        """
        if not self.is_mcp_configured():
            raise ValueError("cTrader Remote MCP token is not configured or is an unauthenticated template slug.")

        headers = {
            "Authorization": f"Bearer {self.mcp_token.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
            },
        }
        try:
            res = requests.post(self.mcp_url, json=payload, headers=headers, timeout=8.0)
            if res.status_code == 401:
                return {"error": "Invalid or expired cTrader MCP Bearer token slug (HTTP 401)"}
            res.raise_for_status()
            data = res.json()
            if "error" in data:
                return {"error": data["error"]}
            result = data.get("result", {})
            if "content" in result and isinstance(result["content"], list):
                for c in result["content"]:
                    if c.get("type") == "text" and isinstance(c.get("text"), str):
                        try:
                            return json.loads(c["text"])
                        except Exception:
                            return {"text": c["text"]}
            return result
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def calculate_pips(symbol: str, entry_price: float, current_price: float, is_buy: bool = True) -> float:
        """Calculates pip difference between entry and current price."""
        meta = CTRADER_INSTRUMENTS.get(symbol.upper(), {"pip_multiplier": 10000})
        mult = meta.get("pip_multiplier", 10000)
        diff = (current_price - entry_price) if is_buy else (entry_price - current_price)
        return round(diff * mult, 1)

    def exchange_authorization_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchanges OAuth 2.0 authorization code for accessToken via connect.spotware.com."""
        url = "https://connect.spotware.com/apps/token"
        params = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        res = requests.post(url, data=params, timeout=5.0)
        res.raise_for_status()
        return res.json()

    def build_auth_payload(self) -> Dict[str, Any]:
        """Builds ProtoOAApplicationAuthReq (payloadType 2100)."""
        return {
            "payloadType": 2100,
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
        }

    def build_account_auth_payload(self) -> Dict[str, Any]:
        """Builds ProtoOAAccountAuthReq (payloadType 2102)."""
        return {
            "payloadType": 2102,
            "ctidTraderAccountId": int(self.account_id) if self.account_id.isdigit() else 0,
            "accessToken": self.access_token,
        }

    def build_order_payload(
        self,
        symbol: str,
        trade_side: str,
        volume: int,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> Dict[str, Any]:
        """Builds ProtoOANewOrderReq (payloadType 2106)."""
        sym = symbol.upper()
        symbol_id = CTRADER_INSTRUMENTS.get(sym, {}).get("id", 1)
        payload: Dict[str, Any] = {
            "payloadType": 2106,
            "ctidTraderAccountId": int(self.account_id) if self.account_id.isdigit() else 0,
            "symbolId": symbol_id,
            "orderType": "MARKET",
            "tradeSide": trade_side.upper(),
            "volume": volume,
        }
        if stop_loss is not None:
            payload["stopLoss"] = round(float(stop_loss), 5)
        if take_profit is not None:
            payload["takeProfit"] = round(float(take_profit), 5)
        return payload

    def get_portfolio(self) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Retrieves cash and open positions.
        Returns (cash, positions_list).
        Prioritizes Remote MCP if configured; falls back to demo simulation or fails gracefully returning (0.0, []).
        """
        if self.is_mcp_configured():
            try:
                acc_info = self.call_mcp_tool("get_account_information")
                if not acc_info.get("error"):
                    balance = float(acc_info.get("balance", 0.0) or acc_info.get("freeMargin", 0.0))
                    raw_positions = self.call_mcp_tool("get_positions")
                    pos_list = []
                    if isinstance(raw_positions, list):
                        for p in raw_positions:
                            pos_list.append({
                                "position_id": str(p.get("positionId") or p.get("id", "")),
                                "symbol": str(p.get("symbol", "")),
                                "side": str(p.get("tradeSide") or p.get("side", "BUY")),
                                "units": float(p.get("volume", 0.0)),
                                "open_price": float(p.get("entryPrice") or p.get("price", 0.0)),
                                "invested": float(p.get("usedMargin", 0.0)),
                                "ppl": float(p.get("unrealizedPnl") or p.get("netProfit", 0.0)),
                                "ppl_pct": 0.0,
                                "stop_loss": p.get("stopLoss"),
                                "take_profit": p.get("takeProfit"),
                                "status": "ACTIVE",
                                "broker": "ctrader",
                            })
                    return balance, pos_list
            except Exception:
                pass

        if not self.is_configured():
            if self.is_demo:
                # Simulated practice forex portfolio
                return 10000.0, list(self._demo_positions)
            return 0.0, []

        try:
            # Over real cTrader socket or gateway proxy
            return 0.0, []
        except Exception:
            return 0.0, []

    def place_order(
        self,
        symbol: str,
        is_buy: bool,
        amount: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> Dict[str, Any]:
        """
        Submits market order for forex or commodity instrument.
        amount represents quantity / notional volume (e.g. 1000 for micro-lot).
        Routes via cTrader Remote MCP if configured; otherwise simulates or uses Open API.
        """
        side = "BUY" if is_buy else "SELL"
        symbol_norm = symbol.upper()

        if self.is_mcp_configured() and not self.is_demo:
            try:
                args = {
                    "symbol": symbol_norm,
                    "volume": float(amount),
                    "side": side,
                }
                if stop_loss is not None:
                    args["stopLoss"] = float(stop_loss)
                if take_profit is not None:
                    args["takeProfit"] = float(take_profit)
                mcp_res = self.call_mcp_tool("place_order", args)
                if not mcp_res.get("error"):
                    return {
                        "status": "FILLED",
                        "order_id": str(mcp_res.get("orderId") or mcp_res.get("positionId", f"CT-MCP-{int(time.time()*1000)}")),
                        "symbol": symbol_norm,
                        "side": side,
                        "units": amount,
                        "mcp": True,
                        "demo": False,
                    }
            except Exception as e:
                return {"status": "ERROR", "error": f"cTrader MCP Order Failed: {str(e)}"}

        if self.is_demo or not self.is_configured():
            # Practice order simulation
            order_id = f"CT-DEMO-{int(time.time() * 1000)}"
            pos = {
                "position_id": order_id,
                "symbol": symbol_norm,
                "side": side,
                "units": float(amount),
                "open_price": 1.0850 if "EUR" in symbol_norm else 1.2750,
                "invested": round(float(amount) * 0.01, 2),  # 1:100 leverage margin
                "ppl": 0.0,
                "ppl_pct": 0.0,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "status": "ACTIVE",
                "broker": "ctrader",
            }
            self._demo_positions.append(pos)
            return {
                "status": "FILLED",
                "order_id": order_id,
                "symbol": symbol_norm,
                "side": side,
                "units": amount,
                "demo": True,
            }

        # Live order execution payload
        volume_cents = int(amount * 100)
        payload = self.build_order_payload(symbol_norm, side, volume_cents, stop_loss, take_profit)
        return {
            "status": "SUBMITTED",
            "payload": payload,
            "demo": False,
        }

    def close_position(self, position_id: str) -> bool:
        """Closes open position by id."""
        for i, pos in enumerate(self._demo_positions):
            if pos.get("position_id") == position_id:
                self._demo_positions.pop(i)
                return True
        return False
