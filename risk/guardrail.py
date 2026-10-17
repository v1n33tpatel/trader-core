import logging
from typing import Optional
from models.events import SignalEvent, OrderEvent, SignalSide

logger = logging.getLogger("RiskSentinel")

class RiskSentinel:
    def __init__(
        self,
        max_open_positions: int = 5,
        max_drawdown_pct: float = 3.0,
        max_order_usd: float = 50.0,
        event_risk_guard: bool = True,
    ):
        self.max_positions = max_open_positions
        self.max_drawdown = max_drawdown_pct
        self.max_order_usd = max_order_usd
        self.event_risk_guard = event_risk_guard
        self.circuit_broken = False

    def validate_signal(
        self,
        signal: SignalEvent,
        current_open_positions: int,
        daily_loss_pct: float,
        current_price: float,
        event_risk_level: Optional[str] = None,
    ) -> Optional[OrderEvent]:
        if self.circuit_broken:
            logger.warning("Circuit breaker tripped: rejecting signal.")
            return None

        if self.event_risk_guard and event_risk_level == "HIGH":
            logger.warning("Tier-1 Macro Event imminent: holding execution to avoid binary event slippage.")
            return None

        if daily_loss_pct >= self.max_drawdown:
            self.circuit_broken = True
            logger.critical(f"Daily drawdown limit hit ({daily_loss_pct:.2f}% >= {self.max_drawdown}%). Halting trading.")
            return None


        if signal.side == SignalSide.BUY and current_open_positions >= self.max_positions:
            logger.warning(f"Max positions reached ({current_open_positions}/{self.max_positions}).")
            return None

        if signal.side in [SignalSide.HOLD, SignalSide.CLOSE]:
            return None

        units = round(self.max_order_usd / current_price, 6) if current_price > 0 else 0.0

        return OrderEvent(
            broker="trading212" if "L" in signal.symbol or "=" in signal.symbol else "etoro",
            symbol=signal.symbol,
            side=signal.side,
            units=units,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit
        )
