import os, base64, requests

def normalize_t212_ticker(raw_ticker: str) -> str:
    """
    Normalizes Trading 212 raw tickers into standard display & market data tickers.
    Preserves .L for London Stock Exchange tickers to prevent data mismatches with US equivalents
    (e.g., EQQQ_l_EQ -> EQQQ.L vs US QQQ; VUKE_l_EQ -> VUKE.L).
    """
    if not raw_ticker:
        return ""
    r = raw_ticker.strip()
    if r.endswith("_l_EQ") or r.endswith("l_EQ") or r.endswith(".L"):
        base = r.replace("_l_EQ", "").replace("l_EQ", "").replace(".L", "")
        return f"{base}.L"
    if r.endswith("_US_EQ"):
        return r.replace("_US_EQ", "")
    if r.endswith("_EQ"):
        return r.replace("_EQ", "")
    return r


def to_t212_order_ticker(clean_symbol: str) -> str:
    """
    Maps a clean ticker back to Trading 212 API order symbol.
    EQQQ.L -> EQQQ_l_EQ, AAPL -> AAPL_US_EQ, QQQ -> QQQ_US_EQ.
    """
    if not clean_symbol:
        return ""
    s = clean_symbol.strip()
    if s.endswith("_EQ"):
        return s
    if s.endswith(".L"):
        base = s.replace(".L", "")
        return f"{base}_l_EQ"
    return f"{s}_US_EQ"


class Trading212Broker:
    def __init__(self, is_demo: bool = True):
        self.is_demo = is_demo
        self.base_url = "https://demo.trading212.com/api/v0" if is_demo else "https://live.trading212.com/api/v0"
        self.api_key = os.getenv("T212_API_KEY", "").strip().strip("\"' ")
        self.api_secret = os.getenv("T212_API_SECRET", "").strip().strip("\"' ")
        env_paths = (
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
            "/home/vineet/feed-agent/t212.env",
        )

        for env_path in env_paths:
            if self.api_key and self.api_secret:
                break
            try:
                with open(env_path) as ff:
                    for line in ff:
                        if "=" in line and not line.strip().startswith("#"):
                            k, v = line.strip().split("=", 1)
                            key_clean = k.strip()
                            val_clean = v.strip().strip('"\' ')
                            if key_clean == "T212_API_KEY" and not self.api_key:
                                self.api_key = val_clean
                            elif key_clean == "T212_API_SECRET" and not self.api_secret:
                                self.api_secret = val_clean
            except OSError:
                continue

    def _headers(self):
        credentials = f"{self.api_key}:{self.api_secret}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json"
        }

    def get_portfolio(self):
        if not self.api_key:
            return 0.0, []
        try:
            # 1. Fetch free cash
            cash = 0.0
            r_cash = requests.get(f"{self.base_url}/equity/account/cash", headers=self._headers(), timeout=5)
            if r_cash.status_code == 200:
                cash = float(r_cash.json().get("free", 0.0))
            else:
                r_sum = requests.get(f"{self.base_url}/equity/account/summary", headers=self._headers(), timeout=5)
                if r_sum.status_code == 200:
                    data = r_sum.json()
                    cash = float(data.get("free", 0.0) or data.get("cash", {}).get("availableToTrade", 0.0))

            # 2. Fetch raw positions
            r_pos = requests.get(f"{self.base_url}/equity/portfolio", headers=self._headers(), timeout=5)
            raw_positions = r_pos.json() if r_pos.status_code == 200 else []
            
            positions = []
            for p in raw_positions:
                raw_tkr = p.get("ticker", "UNKNOWN")
                clean_sym = normalize_t212_ticker(raw_tkr)
                
                qty = float(p.get("quantity", 0.0))
                avg_price = float(p.get("averagePrice", 0.0))
                cur_price = float(p.get("currentPrice", 0.0))
                ppl = float(p.get("ppl", 0.0))
                invested = round(qty * avg_price, 2)
                ppl_pct = round((ppl / invested) * 100, 2) if invested > 0 else 0.0

                positions.append({
                    "ticker": clean_sym,
                    "raw_ticker": raw_tkr,
                    "units": qty,
                    "open_price": avg_price,
                    "current_price": cur_price,
                    "invested": invested,
                    "ppl": ppl,
                    "ppl_pct": ppl_pct,
                    "status": "ACTIVE"
                })

            return cash, positions
        except Exception as e:
            print(f"[T212-ERROR] {e}")
            return 0.0, []
