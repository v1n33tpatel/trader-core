from models.events import BarEvent, SignalEvent, SignalSide
from strategies.base import BaseStrategy
from typing import Optional, List

class CopilotActiveStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="CopilotActiveStrategy", params={
            "rsi_buy": 30.0,
            "rsi_sell": 70.0,
            "tp_pct": 3.5,
            "sl_pct": 2.0
        })

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