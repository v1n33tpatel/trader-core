from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd

from quant_trading.data import validate_close_prices


class Strategy(Protocol):
    def target_positions(self, close: pd.Series) -> pd.Series:
        """Return target exposures known at each close timestamp."""


@dataclass(frozen=True)
class TimeSeriesMomentum:
    lookback: int = 20
    volatility_window: int = 20
    target_annual_volatility: float = 0.15
    max_leverage: float = 1.0
    periods_per_year: int = 252

    def __post_init__(self) -> None:
        if self.lookback < 1:
            raise ValueError("lookback must be positive")
        if self.volatility_window < 2:
            raise ValueError("volatility_window must be at least 2")
        if not np.isfinite(self.target_annual_volatility) or self.target_annual_volatility <= 0:
            raise ValueError("target_annual_volatility must be finite and positive")
        if not np.isfinite(self.max_leverage) or self.max_leverage <= 0:
            raise ValueError("max_leverage must be finite and positive")
        if self.periods_per_year < 1:
            raise ValueError("periods_per_year must be positive")

    def target_positions(self, close: pd.Series) -> pd.Series:
        prices = validate_close_prices(close)
        returns = prices.pct_change(fill_method=None)
        direction = np.sign(prices.pct_change(self.lookback, fill_method=None))
        annualized_volatility = (
            returns.rolling(self.volatility_window, min_periods=self.volatility_window)
            .std(ddof=1)
            * np.sqrt(self.periods_per_year)
        )
        raw_exposure = direction * self.target_annual_volatility / annualized_volatility
        positions = raw_exposure.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return positions.clip(-self.max_leverage, self.max_leverage).rename("target_position")


@dataclass(frozen=True)
class MACDStrategy:
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    volatility_window: int = 20
    target_annual_volatility: float = 0.15
    max_leverage: float = 1.0
    periods_per_year: int = 252
    use_trend_filter: bool = False
    trend_filter_period: int = 200
    min_histogram_threshold: float = 0.0
    allow_short: bool = False

    def __post_init__(self) -> None:
        if self.fast_period < 1:
            raise ValueError("fast_period must be positive")
        if self.slow_period <= self.fast_period:
            raise ValueError("slow_period must be greater than fast_period")
        if self.signal_period < 1:
            raise ValueError("signal_period must be positive")
        if self.volatility_window < 2:
            raise ValueError("volatility_window must be at least 2")
        if not np.isfinite(self.target_annual_volatility) or self.target_annual_volatility <= 0:
            raise ValueError("target_annual_volatility must be finite and positive")
        if not np.isfinite(self.max_leverage) or self.max_leverage <= 0:
            raise ValueError("max_leverage must be finite and positive")
        if self.periods_per_year < 1:
            raise ValueError("periods_per_year must be positive")
        if self.trend_filter_period < 1:
            raise ValueError("trend_filter_period must be positive")

    def target_positions(self, close: pd.Series) -> pd.Series:
        prices = validate_close_prices(close)
        returns = prices.pct_change(fill_method=None)

        ema_fast = prices.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = prices.ewm(span=self.slow_period, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        is_bullish = (macd_line > signal_line) & (histogram > self.min_histogram_threshold)
        is_bearish = (macd_line < signal_line) & (histogram < -self.min_histogram_threshold)

        if self.use_trend_filter and len(prices) >= self.trend_filter_period:
            trend_ema = prices.ewm(span=self.trend_filter_period, adjust=False).mean()
            is_bullish = is_bullish & (prices >= trend_ema)
            is_bearish = is_bearish | (prices < trend_ema)

        direction = pd.Series(0.0, index=prices.index)
        direction[is_bullish] = 1.0
        if self.allow_short:
            direction[is_bearish] = -1.0

        annualized_volatility = (
            returns.rolling(self.volatility_window, min_periods=self.volatility_window)
            .std(ddof=1)
            * np.sqrt(self.periods_per_year)
        )
        raw_exposure = direction * self.target_annual_volatility / annualized_volatility
        positions = raw_exposure.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return positions.clip(-self.max_leverage, self.max_leverage).rename("target_position")

