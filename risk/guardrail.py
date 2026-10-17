import logging
from typing import Optional, Dict, Any
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

    def calculate_dynamic_sizing(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
        take_profit: Optional[float] = None,
        risk_pct: float = 0.02,
    ) -> Dict[str, Any]:
        """
        Calculates position sizing from invalidation distance:
        Position Size = (Equity * 0.02) / |Entry Price - Stop Loss|
        Capped strictly by self.max_order_usd ($50.00 USD).
        """
        risk_distance = abs(entry_price - stop_loss)
        if risk_distance <= 0 or entry_price <= 0:
            return {
                "valid": False,
                "reason": "Invalid entry or stop loss price",
                "risk_reward_ratio": 0.0,
                "recommended_notional_usd": 0.0,
                "recommended_units": 0.0,
                "max_loss_base_currency": 0.0,
            }

        stop_loss_pct = (risk_distance / entry_price) * 100.0
        risk_budget_usd = equity * risk_pct

        # Theoretical units from risk budget:
        theoretical_units = risk_budget_usd / risk_distance
        theoretical_notional = theoretical_units * entry_price

        # Hard cap at max_order_usd ($50.00 USD)
        final_notional = min(theoretical_notional, self.max_order_usd)
        final_units = round(final_notional / entry_price, 6 if entry_price < 1 else 4)
        actual_risk_usd = round(final_units * risk_distance, 2)

        # Mandatory R:R ratio check
        rr_ratio = 0.0
        if take_profit is not None:
            reward_distance = abs(take_profit - entry_price)
            rr_ratio = round(reward_distance / risk_distance, 2)

        is_valid = (take_profit is None or rr_ratio >= 1.99) and stop_loss_pct <= 2.05

        return {
            "valid": is_valid,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_distance": round(risk_distance, 4),
            "stop_loss_pct": round(stop_loss_pct, 2),
            "risk_reward_ratio": rr_ratio,
            "equity": equity,
            "risk_budget_usd": round(risk_budget_usd, 2),
            "recommended_notional_usd": round(final_notional, 2),
            "recommended_units": final_units,
            "max_loss_base_currency": actual_risk_usd,
            "capped_by_max_order": theoretical_notional > self.max_order_usd,
        }

    def audit_pre_trade(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        mode: str = "DEMO",
        broker: str = "binance",
    ) -> Dict[str, Any]:
        """Runs the interactive pre-trade audit validating capital preservation bounds."""
        audit = self.calculate_dynamic_sizing(
            equity=equity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_pct=0.02,
        )
        audit["mode"] = mode.upper()
        audit["broker"] = broker.lower()
        audit["status"] = "PASSED" if audit.get("valid") else "REJECTED"
        return audit

    def validate_signal(
        self,
        signal: SignalEvent,
        current_open_positions: int,
        daily_loss_pct: float,
        current_price: float,
        event_risk_level: Optional[str] = None,
        equity: float = 1000.0,
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

        # R:R constraint validation
        if signal.stop_loss is not None and signal.take_profit is not None:
            risk_dist = abs(current_price - signal.stop_loss)
            reward_dist = abs(signal.take_profit - current_price)
            if risk_dist > 0:
                rr = reward_dist / risk_dist
                if rr < 1.99:
                    logger.warning(f"R:R ratio {rr:.2f} violates mandatory 1:2.0 constraint. Rejecting.")
                    return None

        # Calculate dynamic units with 2% equity risk cap
        if signal.stop_loss is not None:
            sizing = self.calculate_dynamic_sizing(
                equity=equity,
                entry_price=current_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                risk_pct=0.02,
            )
            units = sizing["recommended_units"]
        else:
            units = round(self.max_order_usd / current_price, 6) if current_price > 0 else 0.0

        # Intelligent broker routing
        sym = signal.symbol.upper()
        if any(c in sym for c in ("EUR", "GBP", "JPY", "AUD", "USDCHF", "USDCAD")):
            broker = "ctrader"
        elif any(c in sym for c in (".L", "_L_EQ", "SPY", "QQQ", "VOO", "VTI", "AAPL", "MSFT", "NVDA")):
            broker = "trading212"
        elif "USDT" in sym or "BTC" in sym or "ETH" in sym or "SOL" in sym:
            broker = "binance"
        else:
            broker = "trading212" if ("L" in signal.symbol or "=" in signal.symbol) else "etoro"

        return OrderEvent(
            broker=broker,
            symbol=signal.symbol,
            side=signal.side,
            units=units,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit
        )
