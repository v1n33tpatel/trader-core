from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant_trading.data import validate_close_prices
from quant_trading.metrics import PerformanceMetrics, calculate_metrics
from quant_trading.strategy import Strategy


@dataclass(frozen=True)
class BacktestConfig:
    periods_per_year: int = 252
    one_way_cost_bps: float = 0.0
    execution_delay_bars: int = 1

    def __post_init__(self) -> None:
        if self.periods_per_year < 1:
            raise ValueError("periods_per_year must be positive")
        if not np.isfinite(self.one_way_cost_bps) or self.one_way_cost_bps < 0:
            raise ValueError("one_way_cost_bps must be finite and non-negative")
        if self.execution_delay_bars < 1:
            raise ValueError("execution_delay_bars must be at least 1 for close-only data")


@dataclass(frozen=True)
class BacktestResult:
    target_positions: pd.Series
    positions: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    net_returns: pd.Series
    equity: pd.Series
    metrics: PerformanceMetrics


class BacktestEngine:
    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(self, close: pd.Series, strategy: Strategy) -> BacktestResult:
        prices = validate_close_prices(close)
        target_positions = strategy.target_positions(prices)
        if not isinstance(target_positions, pd.Series):
            raise TypeError("strategy target_positions must return a pandas Series")
        if not target_positions.index.equals(prices.index):
            raise ValueError("strategy positions must use the same index as close prices")

        targets = target_positions.astype(float)
        if not np.isfinite(targets.to_numpy()).all():
            raise ValueError("strategy positions must be finite and contain no missing values")

        positions = targets.shift(self.config.execution_delay_bars + 1).fillna(0.0).rename("position")
        asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
        gross_returns = (positions * asset_returns).rename("gross_return")
        turnover = positions.diff().abs()
        if not turnover.empty:
            turnover.iloc[0] = abs(positions.iloc[0])
            turnover.iloc[-1] += abs(positions.iloc[-1])
        costs = (turnover.fillna(0.0) * self.config.one_way_cost_bps / 10_000).rename("cost")
        net_returns = (gross_returns - costs).rename("net_return")
        equity = (1.0 + net_returns).cumprod().rename("equity")
        metrics = calculate_metrics(net_returns, self.config.periods_per_year)

        return BacktestResult(
            target_positions=targets.rename("target_position"),
            positions=positions,
            gross_returns=gross_returns,
            costs=costs,
            net_returns=net_returns,
            equity=equity,
            metrics=metrics,
        )
