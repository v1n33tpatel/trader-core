from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, Bar, StrategySignal

class LondonNyOverlapStrategy(BaseStrategy):
    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        hour = datetime.now(timezone.utc).hour
        if not (13 <= hour < 17):
            return StrategySignal(symbol, "HOLD", 0.95, f"Outside London/NY overlap session (13-17 UTC).")
        if len(bars) < 8: return StrategySignal(symbol, "HOLD", 0.0, "Insufficient bars")
        
        high_level = max(b.high for b in bars[-7:-1])
        current_bar = bars[-1]
        pip = 0.01 if "JPY" in symbol else 0.0001
        sl_dist = self.params.get("sl_pips", 25) * pip

        if current_bar.close > high_level:
            return StrategySignal(symbol, "BUY", 0.86, f"London/NY session breakout above {high_level:.5f}", suggested_sl=round(current_bar.close - sl_dist, 5), suggested_tp=round(current_bar.close + (sl_dist * 2.0), 5))
        return StrategySignal(symbol, "HOLD", 0.5, "Within session range")
