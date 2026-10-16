---
name: binance-api
description: >-
  Use this skill whenever integrating, modifying, or testing Binance REST API endpoints,
  fetching spot klines/orderbook data, signing authenticated private requests (HMAC-SHA256),
  or writing mocked unit tests for crypto feeds.
---

# Binance API Integration & Cheatsheet

Guidelines, schemas, and reference patterns for interacting with the Binance Spot REST API across data feeds, broker adapters, and unit tests.

## Base URLs
* **Production**: `https://api.binance.com`
* **Testnet**: `https://testnet.binance.vision`

---

## 1. Symbol Normalization
Binance expects concatenated uppercase symbols with quote asset (e.g., `BTCUSDT`, `ETHUSDT`). Never pass separated pairs like `BTC/USDT` or `BTC-USDT`.

```python
def normalize_binance_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    return f"{s}USDT" if not s.endswith("USDT") else s
```

---

## 2. Public Klines / Candlestick Ingestion
* **Endpoint**: `GET /api/v3/klines`
* **Query Parameters**:
  * `symbol`: e.g. `BTCUSDT`
  * `interval`: `1m`, `5m`, `15m`, `1h`, `4h`, `1d`
  * `limit`: default 500, max 1000

### Parsing Schema:
Binance returns a nested array of 12 elements. Numeric values (open, high, low, close, volume) arrive as **strings** and must be converted to `float`:

```python
import requests

def get_binance_klines(symbol: str, interval: str = "1h", limit: int = 50) -> list[dict]:
    pair = normalize_binance_symbol(symbol)
    url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={interval}&limit={limit}"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    
    return [
        {
            "timestamp": int(k[0]),       # Open time in ms
            "open": float(k[1]),          # Open price
            "high": float(k[2]),          # High price
            "low": float(k[3]),           # Low price
            "close": float(k[4]),         # Close price
            "volume": float(k[5]),        # Volume
            "close_time": int(k[6]),      # Close time in ms
        }
        for k in response.json()
    ]
```

---

## 3. Authenticated Private Requests (HMAC-SHA256)
Private endpoints (e.g. `/api/v3/account`, `/api/v3/order`) require:
1. `X-MBX-APIKEY` request header.
2. `timestamp` in milliseconds (`int(time.time() * 1000)`).
3. `recvWindow=5000` to prevent clock-skew errors (`-1021 INVALID_TIMESTAMP`).
4. HMAC-SHA256 signature calculated over the query string using the API secret.

```python
import hmac
import hashlib
import time
import requests

def binance_signed_request(endpoint: str, api_key: str, api_secret: str, params: dict = None) -> dict:
    if not api_key or not api_secret:
        return {}
        
    query_params = dict(params or {})
    query_params["timestamp"] = int(time.time() * 1000)
    query_params["recvWindow"] = 5000
    
    query_str = "&".join(f"{k}={v}" for k, v in query_params.items())
    signature = hmac.new(
        api_secret.encode("utf-8"),
        query_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    headers = {"X-MBX-APIKEY": api_key}
    url = f"https://api.binance.com{endpoint}?{query_str}&signature={signature}"
    res = requests.get(url, headers=headers, timeout=5)
    res.raise_for_status()
    return res.json()
```

---

## 4. Pytest Mocking Pattern
Unit tests must **never** make live HTTP requests to `api.binance.com`. Use pytest's `monkeypatch` fixture to simulate the raw 6-element or 7-element kline tuples:

```python
def test_binance_feed(monkeypatch):
    mock_klines = [
        [1600000000000 + (i * 3600000), "100.0", "105.0", "98.0", "102.0", "50.0", 1600003600000 + (i * 3600000)]
        for i in range(25)
    ]
    class MockResponse:
        status_code = 200
        def json(self): return mock_klines
        def raise_for_status(self): pass

    monkeypatch.setattr("requests.get", lambda url, **kwargs: MockResponse())
```
