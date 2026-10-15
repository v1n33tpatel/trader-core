from typing import List
from models.signal import Signal, SignalType
from models.position import Position

class RiskManager:
    def __init__(self, max_open_positions: int = 5, max_allocation_per_trade: float = 50.0):
        self.max_open_positions = max_open_positions
        self.max_allocation = max_allocation_per_trade

    def validate_signal(self, signal: Signal, open_positions: List[Position], available_cash: float) -> bool:
        if signal.action == SignalType.EXIT: return True
        if len(open_positions) >= self.max_open_positions: return False
        if available_cash < self.max_allocation: return False
        return True
