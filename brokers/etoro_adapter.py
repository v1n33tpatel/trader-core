import os, uuid, requests
from typing import List, Tuple
from brokers.base import BaseBroker
from models.position import Position
from risk.throttler import RateThrottler

class EtoroBroker(BaseBroker):
    def __init__(self, env_path: str = "/home/vineet/feed-agent/etoro.env", is_demo: bool = True):
        self.is_demo = is_demo
        self.throttler = RateThrottler(1.2)
        self.api_key, self.user_key = self._load(env_path)
        self.id_to_sym = {100002: "ETH", 100001: "BTC", 100085: "SOL", 100015: "ADA", 100003: "XRP", 100067: "DOGE", 100095: "AVAX", 100005: "LTC"}
        self.sym_to_id = {v: k for k, v in self.id_to_sym.items()}

    def _load(self, path):
        ak, uk = "", ""
        if os.path.exists(path):
            with open(path) as f:
                for l in f:
                    if "=" in l and not l.strip().startswith("#"):
                        k, v = l.strip().split("=", 1)
                        if k.strip() == "ETORO_API_KEY": ak = v.strip().strip('"\' ')
                        if k.strip() == "ETORO_USER_KEY": uk = v.strip().strip('"\' ')
        return ak, uk

    def _headers(self):
        return {"x-api-key": self.api_key, "x-user-key": self.user_key, "x-request-id": str(uuid.uuid4()), "Content-Type": "application/json"}

    def get_portfolio(self) -> Tuple[float, List[Position]]:
        self.throttler.wait()
        url = f"https://public-api.etoro.com/api/v1/trading/info/{'demo/' if self.is_demo else ''}portfolio"
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            if r.status_code != 200: return 0.0, []
            d = r.json().get("clientPortfolio", {})
            positions = [Position(str(p.get("positionID")), self.id_to_sym.get(p.get("instrumentID"), f"ID_{p.get('instrumentID')}"), p.get("instrumentID"), p.get("isBuy", True), float(p.get("units", 0.0)), float(p.get("openRate", 0.0)), float(p.get("amount", 0.0))) for p in d.get("positions", [])]
            return float(d.get("credit", 0.0)), positions
        except Exception: return 0.0, []

    def place_order(self, symbol: str, is_buy: bool, amount: float) -> dict:
        self.throttler.wait()
        inst_id = self.sym_to_id.get(symbol)
        if not inst_id: return {"error": f"Unknown symbol {symbol}"}
        url = f"https://public-api.etoro.com/api/v2/trading/execution/{'demo/' if self.is_demo else ''}orders"
        try:
            r = requests.post(url, headers=self._headers(), json={"instrumentId": inst_id, "transaction": "Buy" if is_buy else "SellShort", "leverage": 1, "amount": amount}, timeout=10)
            return r.json() if r.headers.get("content-type") == "application/json" else {"status": r.status_code}
        except Exception as e: return {"error": str(e)}

    def close_position(self, position_id: str, instrument_id: int = None) -> bool:
        self.throttler.wait()
        path = "demo/" if self.is_demo else ""
        url = f"https://public-api.etoro.com/api/v1/trading/execution/{path}market-close-orders/positions/{position_id}"
        payload = {"InstrumentId": int(instrument_id)} if instrument_id else {}
        try:
            r = requests.post(url, headers=self._headers(), json=payload, timeout=10)
            return r.status_code in [200, 201, 202]
        except Exception: return False
