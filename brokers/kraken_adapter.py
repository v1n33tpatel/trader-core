import base64
import hashlib
import hmac
import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import requests

from risk.throttler import RateThrottler


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


def normalize_kraken_asset(asset: str) -> str:
    """
    Normalizes Kraken asset names by stripping legacy X/Z prefixes and staking suffixes.
    XXBT -> BTC, XETH -> ETH, ZUSD -> USD, ZEUR -> EUR, DOT.S -> DOT.
    """
    if not asset:
        return ""
    # Strip staking suffixes like .S, .F, .M
    base = asset.split(".")[0].strip()
    # Normalize legacy prefixes
    if base.startswith("X") and len(base) == 4 and base[1:] in ("XBT", "ETH", "LTC", "XRP", "XLM"):
        base = base[1:]
    if base == "XBT":
        return "BTC"
    if base.startswith("Z") and len(base) == 4 and base[1:] in ("USD", "EUR", "GBP", "CAD", "JPY"):
        return base[1:]
    return base


class KrakenBroker:
    def __init__(self, is_demo: bool = False):
        self.is_demo = is_demo
        self.base_url = "https://api.kraken.com"
        self.api_key = _load_env_key("KRAKEN_API_KEY")
        self.api_secret = _load_env_key("KRAKEN_API_SECRET")
        self._throttler = RateThrottler(min_interval_seconds=1.0)
        self._pairs_cache: Dict[str, Any] = {"ts": 0, "data": {}}

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
            self._throttler.wait()
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
                + float(balances.get("ZEUR", 0.0))
            )
            positions = []
            for asset, qty_str in balances.items():
                qty = float(qty_str)
                clean = normalize_kraken_asset(asset)
                if qty > 0.0001 and clean not in ["USD", "EUR", "GBP", "USDT"]:
                    positions.append({
                        "ticker": clean,
                        "raw_ticker": asset,
                        "units": qty,
                        "strategy": "Spot Swing Hold",
                        "status": "ACTIVE",
                    })
            return cash, positions
        except Exception:
            return 0.0, []

    def fetch_asset_pairs(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetches all active Kraken spot crypto trading pairs.
        Cached for 6 hours to respect rate limits.
        """
        now = time.time()
        if not force_refresh and self._pairs_cache["data"] and (now - self._pairs_cache["ts"] < 21600):
            return self._pairs_cache["data"]

        try:
            self._throttler.wait()
            r = requests.get(f"{self.base_url}/0/public/AssetPairs", timeout=10)
            res = r.json()
            pairs = res.get("result", {})
            normalized_pairs: Dict[str, Any] = {}
            for p, d in pairs.items():
                wsname = d.get("wsname", p)
                base = normalize_kraken_asset(d.get("base", ""))
                quote = normalize_kraken_asset(d.get("quote", ""))
                normalized_pairs[p] = {
                    "pair": p,
                    "wsname": wsname,
                    "base": base,
                    "quote": quote,
                    "status": d.get("status", "online"),
                    "lot_decimals": d.get("lot_decimals", 8),
                    "pair_decimals": d.get("pair_decimals", 2),
                    "ordermin": float(d.get("ordermin", 0.0001)),
                }
            self._pairs_cache = {"ts": now, "data": normalized_pairs}
            return normalized_pairs
        except Exception:
            return self._pairs_cache["data"]

    def fetch_ticker(self, pair: str) -> Dict[str, Any]:
        """
        Fetches 24h ticker summary (last price, high, low, volume, vwap).
        """
        try:
            self._throttler.wait()
            r = requests.get(f"{self.base_url}/0/public/Ticker?pair={pair}", timeout=5)
            res = r.json()
            data = res.get("result", {})
            if not data:
                return {}
            # Kraken returns the pair name as the primary dictionary key
            p_key = next(iter(data.keys()))
            tick = data[p_key]
            return {
                "pair": pair,
                "last_price": float(tick.get("c", [0.0])[0]),
                "high_24h": float(tick.get("h", [0.0])[1]),
                "low_24h": float(tick.get("l", [0.0])[1]),
                "volume_24h": float(tick.get("v", [0.0])[1]),
                "vwap_24h": float(tick.get("p", [0.0])[1]),
            }
        except Exception:
            return {}

    def fetch_ohlc(self, pair: str, interval: int = 15) -> List[Dict[str, Any]]:
        """
        Fetches recent candlestick bars for volume profile and FVG calculation.
        Interval in minutes: 1, 5, 15, 30, 60, 240, 1440.
        """
        try:
            self._throttler.wait()
            r = requests.get(f"{self.base_url}/0/public/OHLC?pair={pair}&interval={interval}", timeout=8)
            res = r.json()
            data = res.get("result", {})
            p_key = next((k for k in data.keys() if k != "last"), None)
            if not p_key:
                return []
            raw_bars = data[p_key]
            bars = []
            for b in raw_bars:
                bars.append({
                    "timestamp": float(b[0]),
                    "open": float(b[1]),
                    "high": float(b[2]),
                    "low": float(b[3]),
                    "close": float(b[4]),
                    "vwap": float(b[5]),
                    "volume": float(b[6]),
                    "count": int(b[7]),
                })
            return bars
        except Exception:
            return []

    def place_order(
        self,
        pair: str,
        side: str,
        ordertype: str = "limit",
        volume: float = 0.001,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Submits an authenticated spot order to Kraken private endpoint (/0/private/AddOrder).
        If self.is_demo is True, returns simulated paper execution without hitting live exchange.
        """
        if self.is_demo:
            return {
                "status": "SIMULATED",
                "mode": "DEMO",
                "txid": [f"DEMO-KRAKEN-{int(time.time() * 1000)}"],
                "descr": f"{side.upper()} {volume} {pair} @ {price or 'MARKET'} (Simulated Fills)",
            }

        if not self.api_key or not self.api_secret:
            return {"status": "FAILED", "error": "Unconfigured Kraken API credentials"}

        try:
            self._throttler.wait()
            urlpath = "/0/private/AddOrder"
            data: Dict[str, Any] = {
                "nonce": int(time.time() * 1000),
                "pair": pair,
                "type": side.lower(),
                "ordertype": ordertype.lower(),
                "volume": str(volume),
            }
            if ordertype.lower() == "limit" and price is not None:
                data["price"] = str(round(price, 4))

            r = requests.post(
                f"{self.base_url}{urlpath}",
                headers=self._headers(urlpath, data),
                data=data,
                timeout=8,
            )
            res = r.json()
            if res.get("error"):
                return {"status": "FAILED", "error": res.get("error")}
            return {
                "status": "SUBMITTED",
                "mode": "REAL",
                "txid": res.get("result", {}).get("txid", []),
                "descr": res.get("result", {}).get("descr", {}).get("order", ""),
            }
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}
