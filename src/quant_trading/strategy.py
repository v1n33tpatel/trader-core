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
