import numpy as np
import pandas as pd


def validate_close_prices(close: pd.Series) -> pd.Series:
    if not isinstance(close, pd.Series):
        raise TypeError("close prices must be a pandas Series")
    if not isinstance(close.index, pd.DatetimeIndex):
        raise TypeError("close prices must use a DatetimeIndex")
    if close.empty:
        raise ValueError("close prices cannot be empty")
    if len(close) < 2:
        raise ValueError("at least two close prices are required")
    if close.index.has_duplicates:
        raise ValueError("close price timestamps must be unique")
    if not close.index.is_monotonic_increasing:
        raise ValueError("close price timestamps must be increasing")

    try:
        values = close.astype(float)
    except (TypeError, ValueError) as error:
        raise ValueError("close prices must be numeric") from error

    if not np.isfinite(values.to_numpy()).all():
        raise ValueError("close prices must be finite and contain no missing values")
    if (values <= 0).any():
        raise ValueError("close prices must be positive")
    return values.rename("close")
