import uuid
from typing import List, Tuple
from brokers.base import BaseBroker
from models.position import Position

class MockBroker(BaseBroker):
    def __init__(self, initial_cash: float = 10000.0):
        self.cash = initial_cash
        self.positions: List[Position] = []

    def get_portfolio(self) -> Tuple[float, List[Position]]:
        return self.cash, self.positions

    def place_order(self, symbol: str, is_buy: bool, amount: float) -> dict:
        if self.cash < amount: return {"error": "No funds"}
        self.cash -= amount
        pos = Position(str(uuid.uuid4())[:8], symbol, 999999, is_buy, round(amount / 100.0, 4), 100.0, amount)
        self.positions.append(pos)
        return {"status": "SUCCESS", "position": pos}

    def close_position(self, position_id: str) -> bool:
        for i, p in enumerate(self.positions):
            if p.position_id == position_id:
                self.cash += p.invested_amount
                self.positions.pop(i)
                return True
        return False
