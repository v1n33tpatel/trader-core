from datetime import UTC, datetime

import pytest

from quant_trading.market_data import (
    BinanceMarketDataProvider,
    MarketDataError,
    YahooFinanceProvider,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHttp:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers, timeout))
        return FakeResponse(self.payloads.pop(0))


def test_yahoo_provider_normalizes_quote_and_ohlcv_bars() -> None:
    timestamp = int(datetime(2025, 1, 2, tzinfo=UTC).timestamp())
    http = FakeHttp([{
        "chart": {
            "error": None,
            "result": [{
                "timestamp": [timestamp, timestamp + 86400],
                "indicators": {"quote": [{
                    "open": [100, 101],
                    "high": [103, 104],
                    "low": [99, 100],
                    "close": [102, 103],
                    "volume": [1200, 1400],
                }]},
                "meta": {"regularMarketPrice": 103.5, "regularMarketTime": timestamp + 86400, "currency": "USD"},
            }],
        },
    }])

    snapshot = YahooFinanceProvider(http).fetch("spy", "1d", "1y")

    assert snapshot.provider == "yahoo"
    assert snapshot.symbol == "SPY"
    assert snapshot.quote["price"] == 103.5
    assert snapshot.quote["currency"] == "USD"
    assert snapshot.bars[0]["open"] == 100.0
    assert snapshot.bars[-1]["close"] == 103.0
    assert snapshot.bars[-1]["volume"] == 1400.0


def test_binance_provider_normalizes_kline_and_current_quote() -> None:
    http = FakeHttp([
        [[1735776000000, "100", "105", "99", "104", "10"]],
        {"symbol": "BTCUSDT", "price": "104.5"},
    ])

    snapshot = BinanceMarketDataProvider(http).fetch("BTCUSDT", "1h", "1mo")

    assert snapshot.provider == "binance"
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.quote["price"] == 104.5
    assert snapshot.bars[0]["close"] == 104.0
    assert snapshot.bars[0]["high"] == 105.0
    assert len(http.calls) == 2


def test_provider_rejects_unsupported_interval_before_request() -> None:
    http = FakeHttp([])

    with pytest.raises(MarketDataError, match="interval"):
        BinanceMarketDataProvider(http).fetch("BTCUSDT", "2h", "1mo")
    assert http.calls == []


def test_binance_rejects_history_that_exceeds_bar_cap() -> None:
    http = FakeHttp([])

    with pytest.raises(MarketDataError, match="5,000 bars"):
        BinanceMarketDataProvider(http).fetch("BTCUSDT", "5m", "1mo")
    assert http.calls == []


def test_yahoo_rejects_intraday_history_longer_than_sixty_days() -> None:
    http = FakeHttp([])

    with pytest.raises(MarketDataError, match="60 days"):
        YahooFinanceProvider(http).fetch("SPY", "1h", "3mo")
    assert http.calls == []
