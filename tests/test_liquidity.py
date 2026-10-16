from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import pytest

from quant_trading import (
    calculate_metrics,
    calculate_half_life,
    kelly_position_fraction,
    detect_cme_gaps,
    calculate_volume_profile,
    estimate_liquidation_clusters,
)
from feeds.sub_agent import TwoTierQuantAgent


def test_sortino_and_calmar_metrics() -> None:
    # Construct returns with upside and downside
    returns = pd.Series([0.02, -0.01, 0.03, -0.015, 0.01, 0.02, -0.005, 0.015])
    metrics = calculate_metrics(returns, periods_per_year=252)

    assert metrics.total_return > 0
    assert metrics.sortino_ratio > 0
    assert metrics.calmar_ratio > 0
    # Downside std is strictly less than total std when positive returns are large
    assert metrics.sortino_ratio >= metrics.sharpe_ratio


def test_sortino_ratio_zero_when_no_downside() -> None:
    returns = pd.Series([0.01, 0.02, 0.015, 0.01])
    metrics = calculate_metrics(returns, periods_per_year=252)
    assert metrics.sortino_ratio == 0.0  # downside_std is 0


def test_calculate_half_life_mean_reverting_vs_trending() -> None:
    # 1. Mean-reverting synthetic Ornstein-Uhlenbeck series:
    # x_t = theta * (mu - x_{t-1}) + epsilon, where theta > 0
    np.random.seed(42)
    n = 200
    x = np.zeros(n)
    theta = 0.2
    mu = 50.0
    for t in range(1, n):
        x[t] = x[t - 1] + theta * (mu - x[t - 1]) + np.random.normal(0, 1.0)

    series_mr = pd.Series(x)
    hl = calculate_half_life(series_mr)
    assert np.isfinite(hl)
    assert hl > 0.0
    # Expected half-life is approx ln(2)/theta = ln(2)/0.2 ≈ 3.46
    assert 1.0 < hl < 10.0

    # 2. Trending random walk (beta >= 0)
    series_trending = pd.Series(np.cumsum(np.ones(100)))
    hl_trend = calculate_half_life(series_trending)
    assert hl_trend == float("inf")

    # 3. Series too short
    assert calculate_half_life(pd.Series([1.0, 2.0])) == float("inf")


def test_kelly_position_fraction() -> None:
    # Standard 60% win rate, 2:1 win/loss ratio (b = 2.0)
    # f* = 0.6 - (0.4 / 2.0) = 0.6 - 0.2 = 0.40
    # Half-kelly (fraction=0.5) -> 0.20
    f = kelly_position_fraction(win_rate=0.6, avg_win=200.0, avg_loss=100.0, fraction=0.5)
    assert pytest.approx(f, rel=1e-3) == 0.20

    # Full Kelly (fraction=1.0)
    f_full = kelly_position_fraction(win_rate=0.6, avg_win=200.0, avg_loss=100.0, fraction=1.0)
    assert pytest.approx(f_full, rel=1e-3) == 0.40

    # Negative expectancy: 40% win rate, 1:1 win/loss ratio -> f* < 0 -> 0.0
    f_neg = kelly_position_fraction(win_rate=0.4, avg_win=100.0, avg_loss=100.0)
    assert f_neg == 0.0

    # Invalid edge cases
    assert kelly_position_fraction(win_rate=0.0, avg_win=100.0, avg_loss=100.0) == 0.0
    assert kelly_position_fraction(win_rate=1.0, avg_win=100.0, avg_loss=100.0) == 0.0
    assert kelly_position_fraction(win_rate=0.5, avg_win=-10.0, avg_loss=100.0) == 0.0
    assert kelly_position_fraction(win_rate=0.5, avg_win=100.0, avg_loss=0.0) == 0.0


def test_detect_cme_gaps_bullish_and_bearish() -> None:
    # Friday close to Sunday open gap
    # Friday: 2024-01-05 (weekday 4)
    # Sunday: 2024-01-07 (weekday 6)
    fri_dt = datetime(2024, 1, 5, 21, 0, tzinfo=timezone.utc)
    sun_dt = datetime(2024, 1, 7, 23, 0, tzinfo=timezone.utc)

    # Bullish Gap: Sunday open/low is higher than Friday high
    bars_bullish = [
        {"timestamp": fri_dt.isoformat(), "open": 40000.0, "high": 40500.0, "low": 39800.0, "close": 40200.0},
        {"timestamp": sun_dt.isoformat(), "open": 41500.0, "high": 42000.0, "low": 41200.0, "close": 41800.0},
    ]
    gaps_bullish = detect_cme_gaps(bars_bullish)
    assert len(gaps_bullish) == 1
    assert gaps_bullish[0]["type"] == "bullish_gap"
    assert gaps_bullish[0]["direction"] == "UP"
    assert gaps_bullish[0]["gap_low"] == 40500.0
    assert gaps_bullish[0]["gap_high"] == 41200.0
    assert gaps_bullish[0]["gap_size"] == 700.0

    # Bearish Gap: Sunday open/high is lower than Friday low
    bars_bearish = [
        {"timestamp": fri_dt.isoformat(), "open": 40000.0, "high": 40500.0, "low": 39800.0, "close": 40200.0},
        {"timestamp": sun_dt.isoformat(), "open": 39000.0, "high": 39200.0, "low": 38500.0, "close": 38800.0},
    ]
    gaps_bearish = detect_cme_gaps(bars_bearish)
    assert len(gaps_bearish) == 1
    assert gaps_bearish[0]["type"] == "bearish_gap"
    assert gaps_bearish[0]["direction"] == "DOWN"
    assert gaps_bearish[0]["gap_low"] == 39200.0
    assert gaps_bearish[0]["gap_high"] == 39800.0
    assert gaps_bearish[0]["gap_size"] == 600.0


def test_detect_cme_gaps_dataframe_and_empty() -> None:
    assert detect_cme_gaps([]) == []
    df_empty = pd.DataFrame()
    assert detect_cme_gaps(df_empty) == []


def test_calculate_volume_profile() -> None:
    # 50 candles oscillating around 50,000 with heavy volume at 50,000
    rows = []
    base_price = 50000.0
    for i in range(50):
        # Peak volume concentrated near 50,000
        vol = 1000.0 if 20 <= i <= 30 else 50.0
        p = base_price + (i - 25) * 20.0
        rows.append({
            "high": p + 10.0,
            "low": p - 10.0,
            "close": p,
            "volume": vol,
        })

    profile = calculate_volume_profile(rows, num_bins=20)
    assert "poc" in profile
    assert "vah" in profile
    assert "val" in profile
    assert profile["val"] <= profile["poc"] <= profile["vah"]
    assert profile["val"] >= profile["price_min"]
    assert profile["vah"] <= profile["price_max"]
    assert isinstance(profile["low_volume_nodes"], list)


def test_estimate_liquidation_clusters() -> None:
    entry = 60000.0
    clusters = estimate_liquidation_clusters(entry, leverage_tiers=[10, 25, 50, 100])
    assert "long_liquidations" in clusters
    assert "short_liquidations" in clusters

    long_liqs = {item["leverage"]: item["price"] for item in clusters["long_liquidations"]}
    short_liqs = {item["leverage"]: item["price"] for item in clusters["short_liquidations"]}

    # Long liquidation prices are below entry price: entry * (1 - 1/lev + 0.005)
    # 10x: 60000 * (1 - 0.10 + 0.005) = 60000 * 0.905 = 54300.0
    assert pytest.approx(long_liqs["10x"], abs=1.0) == 54300.0
    # 100x: 60000 * (1 - 0.01 + 0.005) = 60000 * 0.995 = 59700.0
    assert pytest.approx(long_liqs["100x"], abs=1.0) == 59700.0

    # Short liquidation prices are above entry price: entry * (1 + 1/lev - 0.005)
    # 10x: 60000 * (1 + 0.10 - 0.005) = 60000 * 1.095 = 65700.0
    assert pytest.approx(short_liqs["10x"], abs=1.0) == 65700.0
    # 100x: 60000 * (1 + 0.01 - 0.005) = 60000 * 1.005 = 60300.0
    assert pytest.approx(short_liqs["100x"], abs=1.0) == 60300.0

    # Invalid entry
    empty_clusters = estimate_liquidation_clusters(0.0)
    assert empty_clusters["long_liquidations"] == []
    assert empty_clusters["short_liquidations"] == []


def test_subagent_get_liquidity_clusters(monkeypatch) -> None:
    mock_klines = [
        [1600000000000 + i * 3600000, "100.0", "105.0", "98.0", "102.0", "100.0"]
        for i in range(30)
    ]

    class MockResponse:
        status_code = 200

        def json(self):
            return mock_klines

    monkeypatch.setattr("requests.get", lambda url, timeout=5: MockResponse())

    agent = TwoTierQuantAgent()
    result = agent.get_liquidity_clusters("BTC")
    assert isinstance(result, dict)
    assert result["symbol"] == "BTC"
    assert "volume_profile" in result
    assert "liquidation_clusters" in result
    assert "cme_gaps" in result
    assert "poc" in result["volume_profile"]
    assert "vah" in result["volume_profile"]
    assert "val" in result["volume_profile"]
