from models.events import BarEvent, SignalEvent, SignalSide
from strategies.base import BaseEventStrategy
from typing import Optional, List, Dict, Any

class CopilotActiveStrategy(BaseEventStrategy):
    def __init__(self):
        super().__init__(name="CopilotActiveStrategy", params={
            "rsi_buy": 30.0,
            "rsi_sell": 70.0,
            "tp_pct": 3.5,
            "sl_pct": 2.0,
            "fvg_threshold_pct": 0.5
        })

    def detect_fair_value_gap(self, history: List[BarEvent]) -> Optional[Dict[str, Any]]:
        if len(history) < 3:
            return None
        c1, _, c3 = history[-3], history[-2], history[-1]
        if c3.low > c1.high:
            gap_size = c3.low - c1.high
            gap_pct = (gap_size / c1.high) * 100.0 if c1.high > 0 else 0.0
            if gap_pct >= self.params.get("fvg_threshold_pct", 0.0):
                ce = c1.high + (gap_size * 0.5)
                return {
                    "type": "bullish",
                    "gap_size": round(gap_size, 4),
                    "gap_pct": round(gap_pct, 2),
                    "consequent_encroachment": round(ce, 4),
                }
        elif c3.high < c1.low:
            gap_size = c1.low - c3.high
            gap_pct = (gap_size / c1.low) * 100.0 if c1.low > 0 else 0.0
            if gap_pct >= self.params.get("fvg_threshold_pct", 0.0):
                ce = c3.high + (gap_size * 0.5)
                return {
                    "type": "bearish",
                    "gap_size": round(gap_size, 4),
                    "gap_pct": round(gap_pct, 2),
                    "consequent_encroachment": round(ce, 4),
                }
        return None

    def on_bar(self, bar: BarEvent, history: List[BarEvent]) -> Optional[SignalEvent]:
        if len(history) < 15:
            return None
        # Geometry: detect institutional imbalances
        fvg = self.detect_fair_value_gap(history)
        
        # Simple sample signal logic
        closes = [h.close for h in history[-15:]]
        diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0.0 for d in diffs]
        losses = [-d if d < 0 else 0.0 for d in diffs]
        avg_gain, avg_loss = sum(gains)/14.0, sum(losses)/14.0
        rsi = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))

        if rsi <= self.params["rsi_buy"]:
            sl = round(bar.close * (1 - self.params["sl_pct"] / 100.0), 4)
            tp = round(bar.close * (1 + self.params["tp_pct"] / 100.0), 4)
            return SignalEvent(
                strategy_id=self.name,
                symbol=bar.symbol,
                side=SignalSide.BUY,
                confidence=0.85,
                stop_loss=sl,
                take_profit=tp,
                metadata={"rsi": rsi, "fvg": fvg}
            )
        return None