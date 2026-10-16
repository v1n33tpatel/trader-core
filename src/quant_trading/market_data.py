from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import requests


class MarketDataError(ValueError):
    pass


@dataclass(frozen=True)
class MarketSnapshot:
    provider: str
    symbol: str
    interval: str
    quote: dict[str, Any]
    bars: list[dict[str, Any]]


class MarketDataProvider(Protocol):
    name: str

    def fetch(self, symbol: str, interval: str, period: str) -> MarketSnapshot:
        """Fetch a current quote and historical OHLCV bars."""


class YahooFinanceProvider:
    name = "yahoo"
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    PERIODS = {"3d": 3, "1w": 7, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
    INTERVALS = {"1d", "1wk", "1mo", "1h", "30m", "15m"}

    def __init__(self, http: Any = requests) -> None:
        self.http = http

    def fetch(self, symbol: str, interval: str = "1d", period: str = "1y") -> MarketSnapshot:
        ticker = _clean_symbol(symbol)
        if interval not in self.INTERVALS:
            raise MarketDataError("Unsupported Yahoo interval")
        if period not in self.PERIODS:
            raise MarketDataError("Unsupported history period")
        if interval in {"15m", "30m", "1h"} and self.PERIODS[period] > 60:
            raise MarketDataError("Yahoo intraday history is limited to 60 days")

        now = datetime.now(UTC)
        params = {
            "period1": int((now - timedelta(days=self.PERIODS[period])).timestamp()),
            "period2": int(now.timestamp()),
            "interval": interval,
            "events": "div,splits",
        }
        payload = _get_json(self.http, f"{self.BASE_URL}/{ticker}", params=params)
        chart = payload.get("chart", {})
        errors = chart.get("error")
        results = chart.get("result") or []
        if errors or not results:
            raise MarketDataError("No Yahoo Finance data found for this symbol")

        result = results[0]
        timestamps = result.get("timestamp") or []
        quote_data = (result.get("indicators", {}).get("quote") or [{}])[0]
        bars = []
        for index, timestamp in enumerate(timestamps):
            close = _series_value(quote_data.get("close"), index)
            if close is None:
                continue
            bars.append({
                "time": datetime.fromtimestamp(timestamp, UTC).isoformat(),
                "open": _series_value(quote_data.get("open"), index),
                "high": _series_value(quote_data.get("high"), index),
                "low": _series_value(quote_data.get("low"), index),
                "close": close,
                "volume": _series_value(quote_data.get("volume"), index),
            })
        if not bars:
            raise MarketDataError("Yahoo Finance returned no usable price bars")

        meta = result.get("meta", {})
        quote_price = meta.get("regularMarketPrice") or bars[-1]["close"]
        quote_time = meta.get("regularMarketTime")
        return MarketSnapshot(
            provider=self.name,
            symbol=ticker,
            interval=interval,
            quote={
                "price": float(quote_price),
                "currency": meta.get("currency", ""),
                "as_of": datetime.fromtimestamp(quote_time, UTC).isoformat() if quote_time else bars[-1]["time"],
            },
            bars=bars,
        )


class BinanceMarketDataProvider:
    name = "binance"
    BASE_URL = "https://api.binance.com/api/v3"
    INTERVALS = {"1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"}
    MAX_BARS = 5000

    def __init__(self, http: Any = requests) -> None:
        self.http = http

    def fetch(self, symbol: str, interval: str = "1h", period: str = "1y") -> MarketSnapshot:
        ticker = _clean_symbol(symbol).replace("/", "").replace("-", "")
        if interval not in self.INTERVALS:
            raise MarketDataError("Unsupported Binance interval")
        if period not in YahooFinanceProvider.PERIODS:
            raise MarketDataError("Unsupported history period")

        days = YahooFinanceProvider.PERIODS[period]
        interval_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080, "1M": 43800}[interval]
        estimated_bars = int(days * 1440 / interval_minutes) + 2
        if estimated_bars > self.MAX_BARS:
            raise MarketDataError("Selected Binance history exceeds 5,000 bars; choose a shorter period or coarser interval")
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        start_ms = now_ms - days * 24 * 60 * 60 * 1000
        payload: list[list[Any]] = []
        cursor = start_ms
        while cursor < now_ms and len(payload) < self.MAX_BARS:
            page = _get_json(
                self.http,
                f"{self.BASE_URL}/klines",
                params={"symbol": ticker, "interval": interval, "startTime": cursor, "endTime": now_ms, "limit": 1000},
            )
            if not isinstance(page, list):
                raise MarketDataError("Binance returned invalid candle data")
            if not page:
                break
            payload.extend(page)
            next_cursor = int(page[-1][0]) + 1
            if next_cursor <= cursor or len(page) < 1000:
                break
            cursor = next_cursor

        payload = payload[: self.MAX_BARS]
        if not payload:
            raise MarketDataError("No Binance spot data found for this symbol")
        bars = [
            {
                "time": datetime.fromtimestamp(row[0] / 1000, UTC).isoformat(),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in payload
        ]
        quote_payload = _get_json(self.http, f"{self.BASE_URL}/ticker/price", params={"symbol": ticker})
        return MarketSnapshot(
            provider=self.name,
            symbol=ticker,
            interval=interval,
            quote={"price": float(quote_payload["price"]), "currency": "USDT", "as_of": datetime.now(UTC).isoformat()},
            bars=bars,
        )


PROVIDERS: dict[str, MarketDataProvider] = {
    "yahoo": YahooFinanceProvider(),
    "binance": BinanceMarketDataProvider(),
}


def get_market_snapshot(provider: str, symbol: str, interval: str, period: str) -> MarketSnapshot:
    selected = PROVIDERS.get(provider.lower())
    if selected is None:
        raise MarketDataError("Provider must be yahoo or binance")
    return selected.fetch(symbol, interval, period)


def _clean_symbol(symbol: str) -> str:
    ticker = symbol.strip().upper()
    if not ticker or len(ticker) > 32 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-^=/" for char in ticker):
        raise MarketDataError("Invalid symbol")
    return ticker


def _series_value(values: list[Any] | None, index: int) -> float | None:
    if values is None or index >= len(values) or values[index] is None:
        return None
    return float(values[index])


def _get_json(http: Any, url: str, params: dict[str, Any] | None = None) -> Any:
    try:
        response = http.get(
            url,
            params=params,
            headers={"User-Agent": "MoneyMakingMachineResearch/1.0 (market-data; read-only)"},
            timeout=8,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        raise MarketDataError("Market-data provider request failed") from error
    except (ValueError, KeyError, TypeError) as error:
        raise MarketDataError("Market-data provider returned invalid data") from error
