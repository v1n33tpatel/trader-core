import os
import sys
import time
import uuid
import threading
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from core.event_bus import get_event_bus, CH_SIGNALS, CH_MARKET, CH_TELEMETRY
from core.state_store import StateStore
from strategies.active_strategy import CopilotActiveStrategy
from feeds.binance_feed import BinanceFeed


class StrategyScannerService:
    """
    Isolated Strategy Scanner Microservice.
    Continuously monitors multi-asset feeds, detects institutional price action setups,
    and publishes typed SignalEvents to Redis Pub/Sub (channel: trader:events:signals).
    Never executes orders directly.
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        poll_interval_sec: float = 10.0,
        event_bus=None,
    ):
        self.symbols = symbols or ["ETHUSDT", "BTCUSDT", "SOLUSDT", "EURUSD", "SPY"]
        self.poll_interval = poll_interval_sec
        self.event_bus = event_bus or get_event_bus()
        self.strategy = CopilotActiveStrategy()
        self.feed = BinanceFeed()
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def evaluate_symbol(self, symbol: str) -> Optional[dict]:
        """Evaluates price action on a single symbol and emits SignalEvent if actionable."""
        try:
            # For crypto symbols, fetch real or simulated klines
            sym_clean = symbol.upper()
            if "USDT" in sym_clean or sym_clean in ("BTC", "ETH", "SOL", "AVAX"):
                klines = self.feed.fetch_klines(sym_clean, limit=50)
                current_price = klines[-1]["close"] if klines else 2500.0
            else:
                current_price = 1.0850 if "EUR" in sym_clean else 580.0

            action, reason = self.strategy.evaluate_market(sym_clean, self.feed)
            if action in ("BUY", "SELL"):
                # Derive structural stop-loss and take-profit
                risk_pct = 0.015
                stop_loss = round(current_price * (1.0 - risk_pct), 4 if current_price < 10 else 2) if action == "BUY" else round(current_price * (1.0 + risk_pct), 4 if current_price < 10 else 2)
                risk_distance = abs(current_price - stop_loss)
                take_profit = round(current_price + (risk_distance * 2.2), 4 if current_price < 10 else 2) if action == "BUY" else round(current_price - (risk_distance * 2.2), 4 if current_price < 10 else 2)

                signal_id = f"SIG-{uuid.uuid4().hex[:8]}"
                signal_event = {
                    "signal_id": signal_id,
                    "symbol": sym_clean,
                    "action": action,
                    "strategy_id": "price_action_fvg",
                    "entry_price": current_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "risk_reward_ratio": 2.2,
                    "confidence": 0.85,
                    "reason": reason,
                    "timestamp": time.time(),
                    "source": "StrategyScannerService",
                }

                # Publish to Redis Pub/Sub
                self.event_bus.publish(CH_SIGNALS, signal_event)
                print(f"[StrategyScanner] Emitted Signal -> {signal_id}: {action} {sym_clean} @ {current_price}")
                return signal_event
            return None
        except Exception as e:
            print(f"[StrategyScanner] Evaluation error on {symbol}: {e}")
            return None

    def scan_once(self) -> List[dict]:
        """Runs a single pass across all monitored symbols."""
        signals = []
        for symbol in self.symbols:
            sig = self.evaluate_symbol(symbol)
            if sig:
                signals.append(sig)
        return signals

    def run_loop(self):
        """Continuous microservice execution loop."""
        self.running = True
        print(f"[StrategyScanner] Started microservice scanning {self.symbols} (every {self.poll_interval}s)")
        while self.running:
            self.scan_once()
            # Publish heartbeat telemetry
            self.event_bus.publish(CH_TELEMETRY, {
                "service": "strategy_scanner",
                "status": "healthy",
                "symbols_count": len(self.symbols),
                "timestamp": time.time(),
            })
            time.sleep(self.poll_interval)

    def start_in_thread(self) -> threading.Thread:
        self._thread = threading.Thread(target=self.run_loop, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self.running = False


if __name__ == "__main__":
    scanner = StrategyScannerService()
    try:
        scanner.run_loop()
    except KeyboardInterrupt:
        scanner.stop()
        print("\n[StrategyScanner] Stopped.")
