from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, Bar, StrategySignal

class FvgBreakoutStrategy(BaseStrategy):
    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        if len(bars) < 5: return StrategySignal(symbol, "HOLD", 0.0, "Insufficient bars")
        current_price = bars[-1].close
        c1, _, c3 = bars[-3], bars[-2], bars[-1]
        if c3.low > c1.high:
            gap_size = c3.low - c1.high
            if (gap_size / c1.high) * 100.0 >= self.params.get("fvg_threshold_pct", 1.0):
                ce = c1.high + (gap_size * 0.5)
                sl = round(c1.low, 2)
                tp = round(current_price * (1.0 + (self.params.get("tp_pct", 4.5) / 100.0)), 2)
                return StrategySignal(symbol, "BUY", 0.88, f"Bullish FVG target CE {ce:.2f}", suggested_sl=sl, suggested_tp=tp, metadata={"ce": ce})
        return StrategySignal(symbol, "HOLD", 0.5, "No FVG imbalance")
