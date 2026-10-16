import hashlib
import hmac
import os
import time
import urllib.parse
from typing import Any, Dict, List, Tuple
import requests


def _load_env_key(var_name: str) -> str:
    val = os.getenv(var_name, "").strip("\"' ")
    if val:
        return val
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        if k.strip() == var_name:
                            return v.strip().strip("\"' ")
        except OSError:
            pass
    return ""


class BinanceBroker:
    def __init__(self, is_demo: bool = False):
        self.is_demo = is_demo
        self.base_url = "https://api.binance.com"
        self.api_key = _load_env_key("BINANCE_API_KEY")
        self.api_secret = _load_env_key("BINANCE_API_SECRET")

    def get_portfolio(self) -> Tuple[float, List[Dict[str, Any]]]:
        if not self.api_key or not self.api_secret:
            return 0.0, []
        try:
            params = {"timestamp": int(time.time() * 1000)}
            query = urllib.parse.urlencode(params)
            params["signature"] = hmac.new(
                self.api_secret.encode(), query.encode(), hashlib.sha256
            ).hexdigest()
            r = requests.get(
                f"{self.base_url}/api/v3/account",
                headers={"X-MBX-APIKEY": self.api_key},
                params=params,
                timeout=5,
            )
            if r.status_code != 200:
                return 0.0, []
            balances = r.json().get("balances", [])
            cash = sum(
                float(b["free"]) for b in balances if b["asset"] in ["USDT", "FDUSD", "USDC"]
            )
            positions = []
            for b in balances:
                qty = round(float(b.get("free", 0.0)) + float(b.get("locked", 0.0)), 8)
                if qty > 0 and b["asset"] not in ["USDT", "FDUSD", "USDC"]:
                    positions.append({
                        "ticker": b["asset"] + "USDT",
                        "units": qty,
                        "open_price": 0.0,
                        "strategy": "5m Kline Momentum",
                        "status": "ACTIVE",
                    })
            return cash, positions
        except Exception:
            return 0.0, []
