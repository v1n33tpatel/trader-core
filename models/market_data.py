from dataclasses import dataclass
from typing import Optional

@dataclass
class MarketData:
    symbol: str
    current_price: float
    change_24h: float
    rsi_14: Optional[float] = None
