import numpy as np
import pandas as pd

from quant_trading import BacktestConfig, BacktestEngine, TimeSeriesMomentum


def main() -> None:
    random = np.random.default_rng(7)
    dates = pd.date_range("2020-01-01", periods=750, freq="B")
    returns = random.normal(loc=0.0002, scale=0.01, size=len(dates))
    close = pd.Series(100.0 * np.cumprod(1.0 + returns), index=dates, name="close")

    strategy = TimeSeriesMomentum(
        lookback=40,
        volatility_window=20,
        target_annual_volatility=0.12,
        max_leverage=1.0,
        periods_per_year=252,
    )
    result = BacktestEngine(
        BacktestConfig(periods_per_year=252, one_way_cost_bps=2.0)
    ).run(close, strategy)
    print(result.metrics)


if __name__ == "__main__":
    main()
