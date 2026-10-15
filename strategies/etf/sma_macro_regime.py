from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, Bar, StrategySignal

class SmaMacroRegimeStrategy(BaseStrategy):
    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        period = min(self.params.get("trend_sma", 200), len(bars) - 1)
        if period < 15: return StrategySignal(symbol, "HOLD", 0.0, "Insufficient bars")
        closes = [b.close for b in bars]
        current_price = closes[-1]
        sma = sum(closes[-period:]) / period
        
        diffs = [closes[i] - closes[i - 1] for i in range(len(closes) - 14, len(closes))]
        gain, loss = sum(max(d, 0.0) for d in diffs) / 14.0, sum(max(-d, 0.0) for d in diffs) / 14.0
        rsi = 100.0 if loss == 0 else 100.0 - (100.0 / (1.0 + (gain / loss)))

        if current_price >= sma and rsi <= self.params.get("pullback_rsi", 45.0):
            sl = round(current_price * (1.0 - (self.params.get("sl_pct", 3.5) / 100.0)), 2)
            tp = round(current_price * (1.0 + (self.params.get("tp_pct", 6.0) / 100.0)), 2)
            return StrategySignal(symbol, "BUY", 0.82, f"Bullish regime (Price > SMA) + Pullback RSI {rsi:.1f}", suggested_sl=sl, suggested_tp=tp)

        if current_price < sma:
            return StrategySignal(symbol, "HOLD", 0.9, f"Defensive posture: Price below SMA ({sma:.2f})")
        return StrategySignal(symbol, "HOLD", 0.5, "Bullish trend healthy")
