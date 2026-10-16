from datetime import datetime, timezone
import pytest
from models.events import BarEvent, SignalSide
from strategies.base import Bar, StrategySignal
from strategies.price_action import PriceActionStrategy
from strategies.factory import get_strategy_instance
from strategies.registry import STRATEGY_CATALOG
from feeds.sub_agent import TwoTierQuantAgent


def test_price_action_registered_in_catalog() -> None:
    assert "crypto" in STRATEGY_CATALOG
    assert "price_action" in STRATEGY_CATALOG["crypto"]
    metadata = STRATEGY_CATALOG["crypto"]["price_action"]
    assert "Institutional Price Action" in metadata["name"]
    assert "pivot_window" in metadata["params"]


def test_price_action_factory_instantiation() -> None:
    instance = get_strategy_instance("price_action", category="crypto")
    assert isinstance(instance, PriceActionStrategy)
    assert instance.pivot_window == 5


def test_detect_swing_pivots() -> None:
    strat = PriceActionStrategy(pivot_window=2)
    now = datetime.now(timezone.utc)
    
    # 5 bars with a peak at index 2
    # closes/highs: 10, 15, 20, 15, 10
    bars = [
        BarEvent(symbol="BTC", timeframe="1h", open=10.0, high=10.0, low=9.0, close=10.0, volume=1.0, timestamp=now),
        BarEvent(symbol="BTC", timeframe="1h", open=15.0, high=15.0, low=14.0, close=15.0, volume=1.0, timestamp=now),
        BarEvent(symbol="BTC", timeframe="1h", open=20.0, high=22.0, low=19.0, close=20.0, volume=1.0, timestamp=now),
        BarEvent(symbol="BTC", timeframe="1h", open=15.0, high=15.0, low=14.0, close=15.0, volume=1.0, timestamp=now),
        BarEvent(symbol="BTC", timeframe="1h", open=10.0, high=10.0, low=9.0, close=10.0, volume=1.0, timestamp=now),
    ]

    highs, lows = strat.detect_swing_pivots(bars)
    assert len(highs) == 1
    assert highs[0]["index"] == 2
    assert highs[0]["price"] == 22.0
    assert len(lows) == 0


def test_detect_bullish_liquidity_sweep_pinbar() -> None:
    strat = PriceActionStrategy(pivot_window=2, min_wick_ratio=0.50)
    now = datetime.now(timezone.utc)

    # 1. Create a prior swing low at 95.0
    # bars: 105, 100, 95 (swing low), 100, 102
    bars = [
        BarEvent(symbol="ETH", timeframe="1h", open=105.0, high=106.0, low=104.0, close=105.0, volume=10.0, timestamp=now),
        BarEvent(symbol="ETH", timeframe="1h", open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0, timestamp=now),
        BarEvent(symbol="ETH", timeframe="1h", open=96.0, high=97.0, low=95.0, close=96.0, volume=10.0, timestamp=now),
        BarEvent(symbol="ETH", timeframe="1h", open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0, timestamp=now),
        BarEvent(symbol="ETH", timeframe="1h", open=102.0, high=103.0, low=101.0, close=102.0, volume=10.0, timestamp=now),
    ]
    
    # 2. Add current candle that sweeps below 95.0 down to 92.0, but closes at 97.0 (pinbar hammer with long lower wick)
    # Range: 97.5 - 92.0 = 5.5. Lower wick: min(97.0, 97.0) - 92.0 = 5.0. Lower wick ratio: 5.0 / 5.5 = 0.909 >= 0.50.
    sweep_bar = BarEvent(symbol="ETH", timeframe="1h", open=97.0, high=97.5, low=92.0, close=97.0, volume=50.0, timestamp=now)
    all_bars = bars + [sweep_bar]

    analysis = strat.analyze_market_structure(all_bars)
    assert analysis["sweep_detected"] is True
    assert analysis["sweep_type"] == "bullish"
    assert analysis["sweep_level"] == 95.0

    # Test on_bar execution
    sig = strat.on_bar(sweep_bar, all_bars)
    assert sig is not None
    assert sig.side == SignalSide.BUY
    assert sig.symbol == "ETH"
    assert sig.stop_loss < sweep_bar.close
    assert sig.stop_loss <= 92.0  # Invalidation is anchored near sweep wick low
    assert sig.take_profit > sweep_bar.close


def test_detect_bearish_liquidity_sweep_shooting_star() -> None:
    strat = PriceActionStrategy(pivot_window=2, min_wick_ratio=0.50)
    now = datetime.now(timezone.utc)

    # 1. Prior swing high at 110.0
    bars = [
        BarEvent(symbol="SOL", timeframe="1h", open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0, timestamp=now),
        BarEvent(symbol="SOL", timeframe="1h", open=105.0, high=106.0, low=104.0, close=105.0, volume=10.0, timestamp=now),
        BarEvent(symbol="SOL", timeframe="1h", open=109.0, high=110.0, low=108.0, close=109.0, volume=10.0, timestamp=now),
        BarEvent(symbol="SOL", timeframe="1h", open=105.0, high=106.0, low=104.0, close=105.0, volume=10.0, timestamp=now),
        BarEvent(symbol="SOL", timeframe="1h", open=104.0, high=105.0, low=103.0, close=104.0, volume=10.0, timestamp=now),
    ]

    # 2. Current candle sweeps 110.0 up to 115.0, closes down at 104.0 (shooting star)
    # Range: 115.0 - 103.5 = 11.5. Upper wick: 115.0 - 104.0 = 11.0. Upper wick ratio: 11.0 / 11.5 = 0.956 >= 0.50.
    sweep_bar = BarEvent(symbol="SOL", timeframe="1h", open=104.0, high=115.0, low=103.5, close=104.0, volume=40.0, timestamp=now)
    all_bars = bars + [sweep_bar]

    analysis = strat.analyze_market_structure(all_bars)
    assert analysis["sweep_detected"] is True
    assert analysis["sweep_type"] == "bearish"
    assert analysis["sweep_level"] == 110.0

    sig = strat.on_bar(sweep_bar, all_bars)
    assert sig is not None
    assert sig.side == SignalSide.SELL
    assert sig.stop_loss > sweep_bar.close
    assert sig.stop_loss >= 115.0  # Invalidation is anchored near sweep wick high
    assert sig.take_profit < sweep_bar.close


def test_detect_break_of_structure() -> None:
    strat = PriceActionStrategy(pivot_window=2)
    now = datetime.now(timezone.utc)

    # Swing high at 110.0
    bars = [
        BarEvent(symbol="BTC", timeframe="1h", open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0, timestamp=now),
        BarEvent(symbol="BTC", timeframe="1h", open=105.0, high=106.0, low=104.0, close=105.0, volume=10.0, timestamp=now),
        BarEvent(symbol="BTC", timeframe="1h", open=109.0, high=110.0, low=108.0, close=109.0, volume=10.0, timestamp=now),
        BarEvent(symbol="BTC", timeframe="1h", open=105.0, high=106.0, low=104.0, close=105.0, volume=10.0, timestamp=now),
        BarEvent(symbol="BTC", timeframe="1h", open=104.0, high=105.0, low=103.0, close=104.0, volume=10.0, timestamp=now),
    ]

    # Solid breakout candle closing well above 110.0 (e.g., 114.0) with small upper wick
    bos_bar = BarEvent(symbol="BTC", timeframe="1h", open=106.0, high=114.5, low=105.5, close=114.0, volume=100.0, timestamp=now)
    all_bars = bars + [bos_bar]

    analysis = strat.analyze_market_structure(all_bars)
    assert analysis["bos_detected"] is True
    assert analysis["bos_type"] == "bullish"
    assert analysis["bos_level"] == 110.0

    sig = strat.on_bar(bos_bar, all_bars)
    assert sig is not None
    assert sig.side == SignalSide.BUY


def test_evaluate_state_based_price_action() -> None:
    strat = PriceActionStrategy(pivot_window=2)
    ts = datetime.now(timezone.utc).timestamp()

    bars = [
        Bar(timestamp=ts, open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0),
        Bar(timestamp=ts, open=105.0, high=106.0, low=104.0, close=105.0, volume=10.0),
        Bar(timestamp=ts, open=109.0, high=110.0, low=108.0, close=109.0, volume=10.0),
        Bar(timestamp=ts, open=105.0, high=106.0, low=104.0, close=105.0, volume=10.0),
        Bar(timestamp=ts, open=104.0, high=105.0, low=103.0, close=104.0, volume=10.0),
        Bar(timestamp=ts, open=106.0, high=114.5, low=105.5, close=114.0, volume=100.0),
    ]

    sig = strat.evaluate("BTC", bars, current_positions=[])
    assert sig is not None
    assert sig.action == "BUY"
    assert sig.symbol == "BTC"
    assert sig.confidence > 0.0
    assert sig.suggested_sl is not None
    assert sig.suggested_tp is not None


def test_subagent_price_action_metrics(monkeypatch) -> None:
    mock_klines = [
        [1600000000000, "100.0", "105.0", "98.0", "102.0", "100.0"]
        for _ in range(25)
    ]
    class MockResponse:
        status_code = 200
        def json(self):
            return mock_klines

    monkeypatch.setattr("requests.get", lambda url, timeout=5: MockResponse())
    agent = TwoTierQuantAgent()
    metrics = agent.get_price_action_metrics("BTC")
    assert isinstance(metrics, dict)
    assert metrics["symbol"] == "BTC"
    assert "trend" in metrics
    assert "sweep_detected" in metrics
    assert "bos_detected" in metrics
    assert "swing_high" in metrics
    assert "swing_low" in metrics
