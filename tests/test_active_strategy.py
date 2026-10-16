from datetime import datetime, timezone
from models.events import BarEvent, SignalSide
from strategies.active_strategy import CopilotActiveStrategy


def test_copilot_active_strategy_fvg_detection() -> None:
    strategy = CopilotActiveStrategy()
    now = datetime.now(timezone.utc)

    # Bullish FVG: candle 3 low > candle 1 high
    b1 = BarEvent(symbol="BTC", timeframe="1h", open=100.0, high=105.0, low=99.0, close=104.0, volume=10.0, timestamp=now)
    b2 = BarEvent(symbol="BTC", timeframe="1h", open=104.0, high=115.0, low=103.0, close=114.0, volume=20.0, timestamp=now)
    b3 = BarEvent(symbol="BTC", timeframe="1h", open=114.0, high=120.0, low=108.0, close=118.0, volume=15.0, timestamp=now)

    fvg = strategy.detect_fair_value_gap([b1, b2, b3])
    assert fvg is not None
    assert fvg["type"] == "bullish"
    assert fvg["gap_size"] == 3.0  # 108.0 - 105.0
    assert fvg["consequent_encroachment"] == 106.5


def test_copilot_active_strategy_on_bar_signals() -> None:
    strategy = CopilotActiveStrategy()
    now = datetime.now(timezone.utc)

    # Need at least 15 bars with dropping prices to create oversold RSI (<=30)
    history = []
    price = 200.0
    for i in range(20):
        price -= 5.0
        bar = BarEvent(
            symbol="ETH",
            timeframe="1h",
            open=price + 2.0,
            high=price + 3.0,
            low=price - 1.0,
            close=price,
            volume=50.0,
            timestamp=now,
        )
        history.append(bar)

    signal = strategy.on_bar(history[-1], history)
    assert signal is not None
    assert signal.side == SignalSide.BUY
    assert signal.symbol == "ETH"
    assert signal.stop_loss < history[-1].close
    assert signal.take_profit > history[-1].close
