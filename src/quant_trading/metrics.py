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
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0


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

    # Sortino ratio: downside deviation using returns below 0
    neg_returns = values[values < 0]
    downside_std = float(np.sqrt((neg_returns ** 2).mean())) if len(neg_returns) > 0 else 0.0
    sortino_ratio = (
        float(values.mean() / downside_std * np.sqrt(periods_per_year))
        if downside_std > 0
        else 0.0
    )

    # Calmar ratio: annualized return / |max drawdown|
    calmar_ratio = (
        float(annualized_return / abs(max_drawdown))
        if pd.notna(annualized_return) and max_drawdown < 0
        else 0.0
    )

    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
    )


def calculate_half_life(series: pd.Series) -> float:
    """
    Computes the Ornstein-Uhlenbeck mean-reversion half-life (t_1/2 = -ln(2)/beta).
    Returns float('inf') if series is trending or non-mean reverting.
    """
    if len(series) < 3:
        return float("inf")
    lag = series.shift(1).dropna()
    delta = (series - lag).dropna()
    lag = lag.loc[delta.index]

    cov = np.cov(lag, delta)
    var = cov[0, 0]
    if var <= 0 or not np.isfinite(var):
        return float("inf")
    beta = cov[0, 1] / var

    if beta >= 0 or not np.isfinite(beta):
        return float("inf")
    return float(-np.log(2) / beta)


def kelly_position_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction: float = 0.5,
) -> float:
    """
    Calculates the fractional Kelly criterion position size:
    f* = win_rate - (1 - win_rate) / (avg_win / avg_loss)
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1.0:
        return 0.0
    b = avg_win / avg_loss
    if b <= 0:
        return 0.0
    f_star = win_rate - ((1.0 - win_rate) / b)
    if f_star <= 0 or not np.isfinite(f_star):
        return 0.0
    return float(np.clip(f_star * fraction, 0.0, 1.0))

