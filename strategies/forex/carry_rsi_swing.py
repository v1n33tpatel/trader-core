from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, Bar, StrategySignal

class CarryRsiSwingStrategy(BaseStrategy):
    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        if len(bars) < 15: return StrategySignal(symbol, "HOLD", 0.0, "Insufficient bars")
        closes = [b.close for b in bars]
        diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gain, loss = sum(max(d, 0) for d in diffs[-14:]) / 14.0, sum(max(-d, 0) for d in diffs[-14:]) / 14.0
        rsi = 100.0 if loss == 0 else 100.0 - (100.0 / (1.0 + (gain / loss)))
        
        current_price = closes[-1]
        pip = 0.01 if "JPY" in symbol else 0.0001
        sl_dist = self.params.get("sl_pips", 20) * pip
        tp_dist = self.params.get("tp_pips", 40) * pip

        if rsi <= self.params.get("rsi_oversold", 28.0):
            return StrategySignal(symbol, "BUY", 0.80, f"Oversold swing deviation (RSI: {rsi:.1f})", suggested_sl=round(current_price - sl_dist, 5), suggested_tp=round(current_price + tp_dist, 5))
        if rsi >= self.params.get("rsi_overbought", 72.0):
            return StrategySignal(symbol, "SELL", 0.80, f"Overbought swing deviation (RSI: {rsi:.1f})", suggested_sl=round(current_price + sl_dist, 5), suggested_tp=round(current_price - tp_dist, 5))
        return StrategySignal(symbol, "HOLD", 0.5, f"Neutral RSI ({rsi:.1f})")
