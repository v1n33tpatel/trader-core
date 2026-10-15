from typing import List, Optional
from strategies.base import BaseStrategy
from models.market_data import MarketData
from models.position import Position
from models.signal import Signal, SignalType

class RsiReversalStrategy(BaseStrategy):
    def evaluate_entry(self, data: MarketData, open_positions: List[Position]) -> Optional[Signal]:
        if any(p.symbol == data.symbol for p in open_positions): return None
        rsi_thresh = self.params.get("rsi_buy", 30.0)
        if data.rsi_14 is not None and data.rsi_14 <= rsi_thresh:
            return Signal(data.symbol, SignalType.BUY, 0.85, f"RSI Oversold ({data.rsi_14:.1f})")
        return None

    def evaluate_exit(self, position: Position, data: MarketData) -> Optional[Signal]:
        pct = ((data.current_price - position.open_rate) / position.open_rate) * 100.0
        if pct >= self.params.get("tp_pct", 3.0):
            return Signal(data.symbol, SignalType.EXIT, 1.0, f"TP Hit (+{pct:.2f}%)")
        if pct <= -self.params.get("sl_pct", 2.0):
            return Signal(data.symbol, SignalType.EXIT, 1.0, f"SL Hit ({pct:.2f}%)")
        if data.rsi_14 is not None and data.rsi_14 >= self.params.get("rsi_exit", 65.0) and pct > 0.5:
            return Signal(data.symbol, SignalType.EXIT, 0.9, f"RSI Exit ({data.rsi_14:.1f})")
        return None
