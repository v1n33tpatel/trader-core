import numpy as np
import pandas as pd
import pytest

from quant_trading import BacktestConfig, BacktestEngine, TimeSeriesMomentum
from quant_trading.data import validate_close_prices


def test_close_signal_waits_for_execution_and_costs_are_net_of_liquidation() -> None:
    close = pd.Series(
        [100.0, 110.0, 99.0, 108.9, 119.79],
        index=pd.date_range("2024-01-01", periods=5, freq="D"),
    )
    strategy = TimeSeriesMomentum(lookback=1, volatility_window=2, max_leverage=1.0)
    result = BacktestEngine(BacktestConfig(one_way_cost_bps=100.0)).run(close, strategy)

    assert result.positions.iloc[0] == 0.0
    assert result.positions.iloc[1] == 0.0
    assert np.isfinite(result.net_returns.to_numpy()).all()
    assert result.costs.iloc[-1] >= 0.0




class FixedStrategy:
    def __init__(self, positions: list[float]) -> None:
        self.positions = positions

    def target_positions(self, close: pd.Series) -> pd.Series:
        return pd.Series(self.positions, index=close.index)


def test_backtest_delays_close_signals_and_charges_turnover_costs() -> None:
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    close = pd.Series([100.0, 110.0, 99.0, 108.9], index=dates)
    strategy = FixedStrategy([1.0, 1.0, 0.0, 0.0])

    result = BacktestEngine(BacktestConfig(one_way_cost_bps=100.0)).run(close, strategy)

    np.testing.assert_allclose(result.positions.to_numpy(), [0.0, 0.0, 1.0, 1.0])
    np.testing.assert_allclose(result.gross_returns.to_numpy(), [0.0, 0.0, -0.1, 0.1])
    np.testing.assert_allclose(result.costs.to_numpy(), [0.0, 0.0, 0.01, 0.01])
    np.testing.assert_allclose(result.net_returns.to_numpy(), [0.0, 0.0, -0.11, 0.09])


def test_momentum_targets_are_finite_and_leverage_capped() -> None:
    dates = pd.date_range("2024-01-01", periods=80, freq="D")
    close = pd.Series(np.linspace(100.0, 130.0, len(dates)), index=dates)
    strategy = TimeSeriesMomentum(
        lookback=5,
        volatility_window=5,
        target_annual_volatility=0.2,
        max_leverage=0.75,
        periods_per_year=365,
    )

    targets = strategy.target_positions(close)

    assert targets.index.equals(close.index)
    assert np.isfinite(targets.to_numpy()).all()
    assert targets.abs().max() <= 0.75
    assert targets.iloc[-1] > 0


def test_price_validation_rejects_duplicate_timestamps() -> None:
    dates = pd.DatetimeIndex(["2024-01-01", "2024-01-01"])
    close = pd.Series([100.0, 101.0], index=dates)

    with pytest.raises(ValueError, match="unique"):
        validate_close_prices(close)


def test_price_validation_requires_two_prices() -> None:
    close = pd.Series([100.0], index=pd.date_range("2024-01-01", periods=1))

    with pytest.raises(ValueError, match="at least two"):
        validate_close_prices(close)


def test_engine_rejects_misaligned_strategy_output() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    close = pd.Series([100.0, 101.0, 102.0], index=dates)

    class MisalignedStrategy:
        def target_positions(self, prices: pd.Series) -> pd.Series:
            return pd.Series([1.0, 1.0], index=prices.index[:2])

    with pytest.raises(ValueError, match="same index"):
        BacktestEngine().run(close, MisalignedStrategy())


def test_run_walk_forward_analysis() -> None:
    from quant_trading import run_walk_forward, WalkForwardResult
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    # Linear upward trend
    close = pd.Series(np.linspace(100.0, 150.0, 100), index=dates)
    strat = TimeSeriesMomentum(lookback=5, volatility_window=5, max_leverage=1.0)

    wf_res = run_walk_forward(close, strat, train_ratio=0.70)
    assert isinstance(wf_res, WalkForwardResult)
    assert wf_res.split_index == 70
    assert len(wf_res.train_result.net_returns) == 70
    assert len(wf_res.validation_result.net_returns) == 30
    assert wf_res.train_result.metrics.sharpe_ratio is not None
    assert wf_res.validation_result.metrics.sharpe_ratio is not None
    assert wf_res.overfitting_ratio >= 0.0
