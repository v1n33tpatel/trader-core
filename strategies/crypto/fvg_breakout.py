from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, Bar, StrategySignal

class FvgBreakoutStrategy(BaseStrategy):
    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        if len(bars) < 5:
            return StrategySignal(symbol, "HOLD", 0.0, "Insufficient bars")
        current_price = bars[-1].close
        c1, c2, c3 = bars[-3], bars[-2], bars[-1]

        # 1. Bullish Fair Value Gap & 50% Consequent Encroachment (CE)
        if c3.low > c1.high:
            gap_size = c3.low - c1.high
            if (gap_size / c1.high) * 100.0 >= self.params.get("fvg_threshold_pct", 0.5):
                ce = round(c1.high + (gap_size * 0.5), 2 if current_price >= 10 else 4)
                sl = round(c1.low, 2 if current_price >= 10 else 4)
                risk_dist = max(ce - sl, current_price * 0.005)
                # Guaranteed >= 1:2.0 R:R
                tp = round(ce + (risk_dist * 2.2), 2 if current_price >= 10 else 4)
                return StrategySignal(
                    symbol,
                    "BUY",
                    0.88,
                    f"Bullish FVG: Target 50% CE limit {ce:.2f} (SL: {sl:.2f}, TP: {tp:.2f}, R:R 1:2.2)",
                    suggested_sl=sl,
                    suggested_tp=tp,
                    metadata={"ce": ce, "gap_size": round(gap_size, 4), "entry_limit": ce, "fvg_top": c3.low, "fvg_bottom": c1.high}
                )

        # 2. Bearish Fair Value Gap & 50% Consequent Encroachment (CE)
        if c3.high < c1.low:
            gap_size = c1.low - c3.high
            if (gap_size / c1.low) * 100.0 >= self.params.get("fvg_threshold_pct", 0.5):
                ce = round(c3.high + (gap_size * 0.5), 2 if current_price >= 10 else 4)
                sl = round(c1.high, 2 if current_price >= 10 else 4)
                risk_dist = max(sl - ce, current_price * 0.005)
                tp = round(ce - (risk_dist * 2.2), 2 if current_price >= 10 else 4)
                return StrategySignal(
                    symbol,
                    "SELL",
                    0.88,
                    f"Bearish FVG: Target 50% CE limit {ce:.2f} (SL: {sl:.2f}, TP: {tp:.2f}, R:R 1:2.2)",
                    suggested_sl=sl,
                    suggested_tp=tp,
                    metadata={"ce": ce, "gap_size": round(gap_size, 4), "entry_limit": ce, "fvg_top": c1.low, "fvg_bottom": c3.high}
                )

        return StrategySignal(symbol, "HOLD", 0.5, "No unmitigated FVG imbalance")
