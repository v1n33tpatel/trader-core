from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float


def calculate_metrics(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> PerformanceMetrics:
    if periods_per_year < 1:
        raise ValueError("periods_per_year must be positive")
    if returns.empty:
        raise ValueError("returns cannot be empty")
    if not np.isfinite(returns.to_numpy(dtype=float)).all():
        raise ValueError("returns must be finite and contain no missing values")

    values = returns.astype(float)
    wealth = (1.0 + values).cumprod()
    total_return = float(wealth.iloc[-1] - 1.0)
    annualized_return = (
        float(wealth.iloc[-1] ** (periods_per_year / len(values)) - 1.0)
        if wealth.iloc[-1] > 0
        else float("nan")
    )
    annualized_volatility = float(values.std(ddof=1) * np.sqrt(periods_per_year))
    standard_deviation = values.std(ddof=1)
    sharpe_ratio = (
        float(values.mean() / standard_deviation * np.sqrt(periods_per_year))
        if pd.notna(standard_deviation) and standard_deviation > 0
        else 0.0
    )
    wealth_with_initial = pd.concat(
        [pd.Series([1.0]), wealth.reset_index(drop=True)],
        ignore_index=True,
    )
    max_drawdown = float((wealth_with_initial / wealth_with_initial.cummax() - 1.0).min())

    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
    )
