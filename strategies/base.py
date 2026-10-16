from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class Bar:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class StrategySignal:
    symbol: str
    action: str          # BUY, SELL, HOLD, EXIT
    confidence: float    # 0.0 to 1.0
    reason: str
    suggested_sl: Optional[float] = None
    suggested_tp: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class BaseStrategy(ABC):
    def __init__(self, name: str, params: Dict[str, Any]):
        self.name = name
        self.params = params

    @abstractmethod
    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        pass


class BaseEventStrategy(ABC):
    def __init__(self, name: str, params: Dict[str, Any]):
        self.name = name
        self.params = params

    @abstractmethod
    def on_bar(self, bar: Any, history: List[Any]) -> Any:
        pass
