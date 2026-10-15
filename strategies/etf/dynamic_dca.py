from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, Bar, StrategySignal

class DynamicDcaStrategy(BaseStrategy):
    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        if not bars: return StrategySignal(symbol, "HOLD", 0.0, "No bar data")
        closes = [b.close for b in bars[-15:]]
        diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gain, loss = sum(max(d, 0) for d in diffs) / 14.0, sum(max(-d, 0) for d in diffs) / 14.0
        rsi = 100.0 if loss == 0 else 100.0 - (100.0 / (1.0 + (gain / loss)))
        
        mult = 1.5 if rsi <= 30.0 else (1.2 if rsi <= 42.0 else (0.5 if rsi >= 70.0 else 1.0))
        target_allocation = round(self.params.get("dca_step_usd", 50.0) * mult, 2)
        return StrategySignal(symbol, "BUY", 0.90, f"DCA allocation with {mult}x RSI dip boost (RSI: {rsi:.1f})", metadata={"allocation_usd": target_allocation, "multiplier": mult})
