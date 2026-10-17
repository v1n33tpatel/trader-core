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


@dataclass(frozen=True)
class WalkForwardResult:
    train_result: BacktestResult
    validation_result: BacktestResult
    full_result: BacktestResult
    split_index: int
    train_end: str
    validation_start: str
    overfitting_ratio: float


def run_walk_forward(
    close: pd.Series,
    strategy: Strategy,
    config: BacktestConfig | None = None,
    train_ratio: float = 0.70,
) -> WalkForwardResult:
    """
    Executes Walk-Forward Analysis (e.g., 70% in-sample train, 30% out-of-sample forward test)
    to evaluate strategy performance without overfitting.
    """
    prices = validate_close_prices(close)
    n = len(prices)
    if n < 20:
        raise ValueError("At least 20 observations are required for walk-forward analysis")

    split = int(n * train_ratio)
    if split < 10 or (n - split) < 5:
        raise ValueError("Insufficient observations for train and validation split")

    cfg = config or BacktestConfig()
    engine = BacktestEngine(cfg)
    full_result = engine.run(prices, strategy)

    # Train (in-sample)
    train_returns = full_result.net_returns.iloc[:split]
    train_metrics = calculate_metrics(train_returns, cfg.periods_per_year)
    train_equity = (1.0 + train_returns).cumprod()
    train_result = BacktestResult(
        target_positions=full_result.target_positions.iloc[:split],
        positions=full_result.positions.iloc[:split],
        gross_returns=full_result.gross_returns.iloc[:split],
        costs=full_result.costs.iloc[:split],
        net_returns=train_returns,
        equity=train_equity,
        metrics=train_metrics,
    )

    # Validation (out-of-sample)
    val_returns = full_result.net_returns.iloc[split:]
    val_metrics = calculate_metrics(val_returns, cfg.periods_per_year)
    val_equity = (1.0 + val_returns).cumprod()
    val_result = BacktestResult(
        target_positions=full_result.target_positions.iloc[split:],
        positions=full_result.positions.iloc[split:],
        gross_returns=full_result.gross_returns.iloc[split:],
        costs=full_result.costs.iloc[split:],
        net_returns=val_returns,
        equity=val_equity,
        metrics=val_metrics,
    )

    train_sharpe = train_metrics.sharpe_ratio if (train_metrics.sharpe_ratio is not None and np.isfinite(train_metrics.sharpe_ratio)) else 0.0
    val_sharpe = val_metrics.sharpe_ratio if (val_metrics.sharpe_ratio is not None and np.isfinite(val_metrics.sharpe_ratio)) else 0.0
    overfitting_ratio = round(val_sharpe / max(0.01, train_sharpe), 2) if train_sharpe > 0 else 0.0

    return WalkForwardResult(
        train_result=train_result,
        validation_result=val_result,
        full_result=full_result,
        split_index=split,
        train_end=str(prices.index[split - 1]),
        validation_start=str(prices.index[split]),
        overfitting_ratio=overfitting_ratio,
    )
