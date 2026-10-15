from dataclasses import dataclass
from enum import Enum
from typing import Optional

class SignalType(Enum):
    BUY = "BUY"
    SELL_SHORT = "SELL_SHORT"
    EXIT = "EXIT"
    HOLD = "HOLD"

@dataclass
class Signal:
    symbol: str
    action: SignalType
    confidence: float
    reason: str
    suggested_sl: Optional[float] = None
    suggested_tp: Optional[float] = None
