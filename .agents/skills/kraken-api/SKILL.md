---
name: kraken-api
description: >-
  Use this skill whenever integrating, modifying, or testing Kraken REST API endpoints,
  WebSocket v2 feeds, HMAC-SHA512 authenticated private requests, or writing mocked unit tests.
---

# Kraken API Integration & Cheatsheet

Guidelines, schemas, and reference patterns for interacting with Kraken REST and WebSocket v2 APIs.

## Base URLs
* **REST API**: `https://api.kraken.com`
* **WebSocket v2 (Public)**: `wss://ws.kraken.com/v2`
* **WebSocket v2 (Private)**: `wss://ws-auth.kraken.com/v2`

---

## 1. REST Authentication (HMAC-SHA512)
```python
import base64
import hashlib
import hmac
import time
import urllib.parse
import requests

def kraken_signed_post(urlpath: str, api_key: str, api_secret: str, data: dict = None) -> dict:
    data = data or {}
    data["nonce"] = int(time.time() * 1000)
    
    postdata = urllib.parse.urlencode(data)
    encoded = (str(data["nonce"]) + postdata).encode()
    message = urlpath.encode() + hashlib.sha256(encoded).digest()
    mac = hmac.new(base64.b64decode(api_secret), message, hashlib.sha512)
    
    headers = {
        "API-Key": api_key,
        "API-Sign": base64.b64encode(mac.digest()).decode(),
    }
    url = f"https://api.kraken.com{urlpath}"
    res = requests.post(url, headers=headers, data=data, timeout=5)
    return res.json()
```

---

## 2. Browser WebSocket v2 Streaming (`dashboard.js`)
Public feeds connect directly from client-side JavaScript without credentials:

```javascript
function subscribeKrakenLiveCandles(pair, intervalMinutes, onUpdate) {
  const socket = new WebSocket("wss://ws.kraken.com/v2");

  socket.onopen = () => {
    socket.send(JSON.stringify({
      method: "subscribe",
      params: {
        channel: "ohlc",
        symbol: [pair], // e.g. ["BTC/USD"]
        interval: intervalMinutes, // e.g. 60 for 1h
      }
    }));
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.channel === "ohlc" && data.data) {
      data.data.forEach((bar) => {
        onUpdate({
          time: new Date(bar.timestamp).getTime() / 1000,
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
          volume: bar.volume,
        });
      });
    }
  };

  socket.onerror = (err) => console.warn("Kraken WebSocket stream error:", err);
  return socket;
}
```

---

## 3. Balance Parsing & Asset Normalization
```python
def parse_kraken_balances(raw_result: dict) -> tuple[float, list[dict]]:
    cash = float(raw_result.get("ZUSD", 0.0)) + float(raw_result.get("USD", 0.0)) + float(raw_result.get("USDT", 0.0))
    positions = []
    for asset, qty_str in raw_result.items():
        qty = float(qty_str)
        # Strip legacy prefixes and staking suffixes
        clean = asset.split(".")[0].replace("X", "").replace("Z", "")
        if qty > 0.0001 and clean not in ["USD", "EUR", "GBP", "USDT"]:
            positions.append({
                "ticker": clean,
                "units": qty,
                "strategy": "Spot Swing Hold",
                "status": "ACTIVE",
            })
    return cash, positions
```

---

## 4. Pytest Mocking Pattern
```python
def test_kraken_portfolio(monkeypatch):
    mock_result = {
        "error": [],
        "result": {
            "ZUSD": "1250.50",
            "XXBT": "0.15000000",
            "XETH": "2.50000000",
        }
    }
    class MockResponse:
        status_code = 200
        def json(self): return mock_result

    monkeypatch.setattr("requests.post", lambda url, **kwargs: MockResponse())
```
