import numpy as np
import pandas as pd
import pytest

from quant_trading.flask_api import build_backtest_response, demo_prices


def test_demo_prices_are_deterministic_and_backtestable() -> None:
    first = demo_prices()
    second = demo_prices()

    assert first == second
    assert len(first) == 750
    response = build_backtest_response({"prices": first})

    assert response["strategy"] == "Time-series momentum"
    assert response["observations"] == 750
    assert response["curve"]
    assert set(response["metrics"]) == {
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "sharpe_ratio",
        "max_drawdown",
    }


def test_backtest_accepts_csv_close_prices() -> None:
    dates = pd.date_range("2024-01-01", periods=80, freq="B")
    close = 100.0 * np.cumprod(1.0 + np.linspace(-0.004, 0.005, len(dates)))
    csv_rows = "date,close\n" + "".join(
        f"{date:%Y-%m-%d},{value:.6f}\n"
        for date, value in zip(dates, close, strict=True)
    )

    response = build_backtest_response({"csv": csv_rows, "lookback": 5, "volatility_window": 5})

    assert response["observations"] == len(dates)
    assert response["start_date"].startswith("2024-01-01")
    assert response["end_date"].startswith("2024-04")


def test_backtest_rejects_csv_without_required_columns() -> None:
    with pytest.raises(ValueError, match="date and close"):
        build_backtest_response({"csv": "time,price\n2024-01-01,100\n"})


def test_backtest_rejects_non_finite_parameters() -> None:
    with pytest.raises(ValueError, match="finite"):
        build_backtest_response({"prices": demo_prices(), "max_leverage": float("inf")})
