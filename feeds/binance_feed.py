import requests
from typing import Optional
from models.market_data import MarketData

class BinanceFeed:
    @staticmethod
    def get_market_data(symbol: str) -> Optional[MarketData]:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1h&limit=28"
        try:
            r = requests.get(url, timeout=4)
            if r.status_code != 200: return None
            closes = [float(k[4]) for k in r.json()]
            if len(closes) < 15: return None
            g, l = [], []
            for i in range(1, len(closes)):
                d = closes[i] - closes[i - 1]
                g.append(d if d >= 0 else 0.0)
                l.append(0.0 if d >= 0 else abs(d))
            avg_g, avg_l = sum(g[-14:]) / 14.0, sum(l[-14:]) / 14.0
            rsi = 100.0 if avg_l == 0 else round(100.0 - (100.0 / (1.0 + (avg_g / avg_l))), 2)
            return MarketData(symbol=symbol, current_price=closes[-1], change_24h=round(((closes[-1] - closes[0]) / closes[0]) * 100, 2), rsi_14=rsi)
        except Exception: return None
