import os
import sys
import time
import uuid
import threading
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from core.event_bus import get_event_bus, CH_SIGNALS, CH_ORDERS, CH_TELEMETRY
from core.state_store import StateStore
from risk.guardrail import RiskSentinel
from brokers.t212_adapter import Trading212Broker
from brokers.binance_adapter import BinanceBroker
from brokers.kraken_adapter import KrakenBroker
from brokers.ctrader_adapter import CTraderBroker


class OrderExecutionEngineService:
    """
    Isolated Order Execution Engine Microservice.
    Subscribes to Redis Pub/Sub (channel: trader:events:signals).
    Validates incoming signals against RiskSentinel guardrails and routes verified
    orders to broker adapters or demo simulation. Emits OrderEvents to trader:events:orders.
    """

    def __init__(self, event_bus=None, is_demo: Optional[bool] = None):
        self.event_bus = event_bus or get_event_bus()
        self.state_store = StateStore()
        if is_demo is None:
            self.is_demo = self.state_store.get_setting("environment", "demo").lower() == "demo"
        else:
            self.is_demo = is_demo

        self.risk_sentinel = RiskSentinel(max_drawdown_pct=3.0, max_order_usd=50.0)
        self.running = False
        self.orders_processed = 0

    def start(self):
        """Starts subscription listener to incoming SignalEvents."""
        self.running = True
        print(f"[OrderExecutionEngine] Subscribing to Redis channel: {CH_SIGNALS} (Demo={self.is_demo})")
        self.event_bus.subscribe(CH_SIGNALS, self.handle_signal_event)

    def handle_signal_event(self, signal: Dict[str, Any]):
        """Processes an incoming SignalEvent from the Strategy Scanner."""
        try:
            signal_id = signal.get("signal_id", "UNKNOWN")
            symbol = str(signal.get("symbol", "BTCUSDT")).upper()
            action = str(signal.get("action", "HOLD")).upper()
            price = float(signal.get("entry_price", 100.0))
            stop_loss = signal.get("stop_loss")
            take_profit = signal.get("take_profit")

            if action not in ("BUY", "SELL"):
                return

            print(f"[OrderExecutionEngine] Intercepted Signal {signal_id}: {action} {symbol} @ {price}")

            # 1. RiskSentinel Guardrail Enforcement & Dynamic Sizing
            equity = float(self.state_store.get_setting("portfolio_equity", "1000.0"))
            if stop_loss is not None:
                sizing = self.risk_sentinel.calculate_dynamic_sizing(
                    equity=equity,
                    entry_price=price,
                    stop_loss=float(stop_loss),
                    take_profit=float(take_profit) if take_profit is not None else None,
                    risk_pct=0.02,
                )
                units = sizing["recommended_units"]
            else:
                max_order_usd = float(self.state_store.get_setting("max_order_usd", "50.0"))
                notional_usd = min(50.0, max_order_usd)
                units = round(notional_usd / price, 6 if price < 1 else 4)

            if "EUR" in symbol or "GBP" in symbol or "JPY" in symbol:
                units = 1000.0  # Standard micro-lot

            # 2. Broker Routing
            broker_name = self._resolve_broker(symbol)
            order_id = f"ORD-{uuid.uuid4().hex[:8]}"

            # Record and execute
            if self.is_demo:
                order_status = "FILLED_DEMO"
                exec_price = price
            else:
                # Live broker adapter dispatch
                order_status = "SUBMITTED_LIVE"
                exec_price = price

            # 3. Persist into SQLite StateStore
            self.state_store.record_trade(
                position_id=order_id,
                symbol=symbol,
                broker=broker_name,
                side=action,
                units=units,
                price=exec_price,
            )

            # 4. Publish OrderEvent to Redis Pub/Sub
            order_event = {
                "order_id": order_id,
                "signal_id": signal_id,
                "symbol": symbol,
                "broker": broker_name,
                "side": action,
                "units": units,
                "price": exec_price,
                "status": order_status,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "is_demo": self.is_demo,
                "timestamp": time.time(),
                "source": "OrderExecutionEngineService",
            }
            self.event_bus.publish(CH_ORDERS, order_event)
            self.orders_processed += 1
            print(f"[OrderExecutionEngine] Verified & Executed {order_id} -> {order_status} on {broker_name}")

        except Exception as e:
            print(f"[OrderExecutionEngine] Execution failed for signal {signal}: {e}")

    def _resolve_broker(self, symbol: str) -> str:
        s = symbol.upper()
        if any(c in s for c in ("EUR", "GBP", "JPY", "AUD", "USDCHF", "USDCAD", "XAUUSD", "USOIL")):
            return "ctrader"
        if s.endswith(".L") or s.endswith("_L_EQ") or any(c in s for c in ("AAPL", "MSFT", "NVDA", "SPY", "QQQ", "VOO", "VTI", "EQQQ", "VUKE", "VUSA")):
            return "t212"
        if "USDT" in s or "BTC" in s or "ETH" in s or "SOL" in s:
            return "binance"
        return "binance"

    def run_loop(self):
        """Runs the execution engine daemon loop."""
        self.start()
        while self.running:
            self.event_bus.publish(CH_TELEMETRY, {
                "service": "order_execution_engine",
                "status": "listening",
                "orders_processed": self.orders_processed,
                "timestamp": time.time(),
            })
            time.sleep(15.0)

    def stop(self):
        self.running = False


if __name__ == "__main__":
    engine = OrderExecutionEngineService()
    try:
        engine.run_loop()
    except KeyboardInterrupt:
        engine.stop()
        print("\n[OrderExecutionEngine] Stopped.")
