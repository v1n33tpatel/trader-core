import yfinance as yf
import pandas as pd

class ForexFeed:
    PAIRS = {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "AUDUSD": "AUDUSD=X",
        "USDCAD": "USDCAD=X"
    }

    @staticmethod
    def get_market_data(symbol_key: str = "EURUSD") -> dict:
        ticker = ForexFeed.PAIRS.get(symbol_key.upper(), "EURUSD=X")
        try:
            data = yf.download(ticker, period="1mo", interval="1h", progress=False)
            if data.empty:
                return {"error": f"No data returned for {ticker}"}
            close_series = data['Close'][ticker] if hasattr(data.columns, 'levels') and len(data.columns.levels) > 1 else data['Close']
            closes = close_series.dropna().tolist()
            if len(closes) < 15:
                return {"error": "Insufficient candle history"}
            current_price = float(closes[-1])
            change_24h = round(((closes[-1] - closes[-24]) / closes[-24]) * 100, 2) if len(closes) >= 24 else 0.0
            gains, losses = [], []
            for i in range(1, len(closes)):
                diff = closes[i] - closes[i - 1]
                gains.append(diff if diff >= 0 else 0.0)
                losses.append(0.0 if diff >= 0 else abs(diff))
            avg_gain = sum(gains[-14:]) / 14.0
            avg_loss = sum(losses[-14:]) / 14.0
            rsi = 100.0 if avg_loss == 0 else round(100.0 - (100.0 / (1.0 + (avg_gain / avg_loss))), 2)
            return {
                "symbol": symbol_key.upper(),
                "ticker": ticker,
                "current_price": current_price,
                "change_24h": change_24h,
                "rsi_14": rsi,
                "timeframe": "1h"
            }
        except Exception as e:
            return {"error": str(e)}
