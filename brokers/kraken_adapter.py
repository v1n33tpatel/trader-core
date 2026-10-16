import base64
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


class KrakenBroker:
    def __init__(self, is_demo: bool = False):
        self.is_demo = is_demo
        self.base_url = "https://api.kraken.com"
        self.api_key = _load_env_key("KRAKEN_API_KEY")
        self.api_secret = _load_env_key("KRAKEN_API_SECRET")

    def _headers(self, urlpath: str, data: Dict[str, Any]) -> Dict[str, str]:
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512)
        return {
            "API-Key": self.api_key,
            "API-Sign": base64.b64encode(mac.digest()).decode(),
        }

    def get_portfolio(self) -> Tuple[float, List[Dict[str, Any]]]:
        if not self.api_key or not self.api_secret:
            return 0.0, []
        try:
            urlpath = "/0/private/Balance"
            data = {"nonce": int(time.time() * 1000)}
            r = requests.post(
                f"{self.base_url}{urlpath}",
                headers=self._headers(urlpath, data),
                data=data,
                timeout=5,
            )
            res = r.json()
            if res.get("error"):
                return 0.0, []
            balances = res.get("result", {})
            cash = (
                float(balances.get("ZUSD", 0.0))
                + float(balances.get("USD", 0.0))
                + float(balances.get("USDT", 0.0))
            )
            positions = []
            for asset, qty_str in balances.items():
                qty = float(qty_str)
                clean = asset.replace("X", "").replace("Z", "")
                if qty > 0.0001 and clean not in ["USD", "EUR", "GBP", "USDT"]:
                    positions.append({
                        "ticker": clean,
                        "units": qty,
                        "strategy": "Spot Swing Hold",
                        "status": "ACTIVE",
                    })
            return cash, positions
        except Exception:
            return 0.0, []
