from abc import ABC, abstractmethod
from typing import List, Tuple
from models.position import Position

class BaseBroker(ABC):
    @abstractmethod
    def get_portfolio(self) -> Tuple[float, List[Position]]: pass

    @abstractmethod
    def place_order(self, symbol: str, is_buy: bool, amount: float) -> dict: pass

    @abstractmethod
    def close_position(self, position_id: str) -> bool: pass
