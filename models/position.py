from dataclasses import dataclass

@dataclass
class Position:
    position_id: str
    symbol: str
    instrument_id: int
    is_buy: bool
    units: float
    open_rate: float
    invested_amount: float
    net_profit: float = 0.0

    @property
    def netProfit(self) -> float:
        return self.net_profit
