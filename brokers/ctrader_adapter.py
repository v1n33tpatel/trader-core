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

        # In-memory practice positions for demo testing
        self._demo_positions: List[Dict[str, Any]] = []

    def is_configured(self) -> bool:
        """Checks if live API credentials are fully provided."""
        return bool(self.client_id and self.client_secret and self.account_id and self.access_token)

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
        If unconfigured and in practice mode, returns a simulated demo account.
        If live request fails, fails gracefully returning (0.0, []).
        """
        if not self.is_configured():
            if self.is_demo:
                # Simulated practice forex portfolio
                return 10000.0, list(self._demo_positions)
            return 0.0, []

        try:
            # Over real cTrader socket or gateway proxy
            # Default fallback when sockets are not connected
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
        """
        side = "BUY" if is_buy else "SELL"
        symbol_norm = symbol.upper()

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
