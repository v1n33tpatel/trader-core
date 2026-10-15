from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, Bar, StrategySignal

class AtrTrailingBreakoutStrategy(BaseStrategy):
    def _calculate_atr(self, bars: List[Bar], period: int = 14) -> float:
        if len(bars) < period + 1: return 1.0
        trs = [max(bars[i].high - bars[i].low, abs(bars[i].high - bars[i-1].close), abs(bars[i].low - bars[i-1].close)) for i in range(1, len(bars))]
        return sum(trs[-period:]) / period

    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        lookback = self.params.get("lookback_period", 20)
        if len(bars) < lookback + 1: return StrategySignal(symbol, "HOLD", 0.0, "Insufficient bars")
        recent_high = max(b.high for b in bars[-(lookback + 1):-1])
        current_price = bars[-1].close
        atr = self._calculate_atr(bars, self.params.get("atr_period", 14))
        atr_mult = self.params.get("atr_multiplier", 2.5)

        for pos in current_positions:
            if pos.get("symbol") == symbol or pos.get("ticker") == symbol:
                trail_sl = round(current_price - (atr * atr_mult), 2)
                if current_price < trail_sl: return StrategySignal(symbol, "EXIT", 1.0, f"ATR Trailing Stop breached ({trail_sl})")
                return StrategySignal(symbol, "HOLD", 0.7, f"Holding trend, stop at {trail_sl}")

        if current_price > recent_high:
            sl = round(current_price - (atr * atr_mult), 2)
            tp = round(current_price + (atr * self.params.get("tp_atr_mult", 4.0)), 2)
            return StrategySignal(symbol, "BUY", 0.85, f"Breakout above {lookback}-bar high ({recent_high:.2f})", suggested_sl=sl, suggested_tp=tp)

        return StrategySignal(symbol, "HOLD", 0.5, "Within channel")
