import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.events import BarEvent, SignalSide
from feeds.binance_feed import BinanceFeed
from risk.guardrail import RiskSentinel
from core.state_store import StateStore
from strategies.price_action import PriceActionStrategy

def run_orchestrator():
    store = StateStore()
    sentinel = RiskSentinel(max_open_positions=5, max_drawdown_pct=3.0, max_order_usd=50.0)
    strategy = PriceActionStrategy(pivot_window=4, min_wick_ratio=0.50, risk_reward_ratio=2.0)
    symbols = ["ETH", "BTC", "SOL", "AVAX"]

    print("[ENGINE] Multi-asset orchestrator initialized with Reactive Price Action Engine. Event loop running...")
    history_cache = {s: [] for s in symbols}

    while True:
        try:
            for sym in symbols:
                m = BinanceFeed.get_market_data(sym)
                if not m:
                    continue
                bar = BarEvent(
                    symbol=sym,
                    timeframe="1h",
                    open=m.current_price,
                    high=getattr(m, 'high_24h', m.current_price),
                    low=getattr(m, 'low_24h', m.current_price),
                    close=m.current_price,
                    volume=getattr(m, 'volume', 100.0)
                )
                history = history_cache[sym]
                history.append(bar)
                if len(history) > 50:
                    history.pop(0)

                signal = strategy.on_bar(bar, history)
                if signal:
                    order = sentinel.validate_signal(
                        signal=signal,
                        current_open_positions=0,
                        daily_loss_pct=0.0,
                        current_price=bar.close
                    )
                    if order:
                        pattern = signal.metadata.get("recent_pattern", "PRICE_ACTION") if signal.metadata else "PRICE_ACTION"
                        sl_str = f"${signal.stop_loss:.2f}" if signal.stop_loss else "N/A"
                        tp_str = f"${signal.take_profit:.2f}" if signal.take_profit else "N/A"
                        print(f"[ENGINE-ORDER] {order.broker.upper()} | {order.side.value} {order.units} {order.symbol} @ ${bar.close:.2f} | Setup: {pattern} | Invalidation: {sl_str} | Target: {tp_str}")
                        store.record_trade(f"sim_{int(time.time())}", order.symbol, order.broker, order.side.value, order.units, bar.close)
        except Exception as e:
            print(f"[ENGINE-ERROR] {e}")
        time.sleep(60)

if __name__ == "__main__":
    run_orchestrator()
