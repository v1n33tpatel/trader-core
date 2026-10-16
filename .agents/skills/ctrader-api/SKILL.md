---
name: ctrader-api
description: >-
  Use this skill whenever integrating, modifying, or testing cTrader Open API endpoints,
  Protobuf/JSON WebSocket connections, OAuth 2.0 token exchanges, or writing mocked unit tests.
---

# cTrader Open API Integration & Cheatsheet

Guidelines, message structures, and reference patterns for the Spotware cTrader Open API.

## Hosts & Ports
* **Live Host**: `live.ctraderapi.com`
* **Demo Host**: `demo.ctraderapi.com`
* **Port 5035**: Protocol Buffers (TCP or WebSocket `wss://live.ctraderapi.com:5035`)
* **Port 5036**: JSON (TCP or WebSocket `wss://live.ctraderapi.com:5036`)

---

## 1. Authentication Lifecycle

### Step 1: OAuth 2.0 Web Token Exchange (HTTP REST)
```python
import requests

def exchange_ctrader_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    url = "https://connect.spotware.com/apps/token"
    params = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    res = requests.post(url, data=params, timeout=5)
    res.raise_for_status()
    return res.json()  # Returns accessToken and refreshToken
```

### Step 2: Socket Authorization (Protobuf / JSON over Port 5035 or 5036)
1. **Application Auth** (`ProtoOAApplicationAuthReq`, payloadType 2100):
   ```json
   {
     "payloadType": 2100,
     "clientId": "YOUR_CLIENT_ID",
     "clientSecret": "YOUR_CLIENT_SECRET"
   }
   ```
2. **Account Auth** (`ProtoOAAccountAuthReq`, payloadType 2102):
   ```json
   {
     "payloadType": 2102,
     "ctidTraderAccountId": 1234567,
     "accessToken": "USER_ACCESS_TOKEN"
   }
   ```

---

## 2. Market Data Ingestion

### A. Subscribe to Live Spot Quotes (`ProtoOASubscribeSpotsReq`, payloadType 2127)
```json
{
  "payloadType": 2127,
  "ctidTraderAccountId": 1234567,
  "symbolId": [1, 2]  // e.g. EURUSD, GBPUSD symbol IDs
}
```
*Server streams `ProtoOASpotEvent` (payloadType 2131) with live bid/ask quotes.*

### B. Historical Candlesticks (`ProtoOAGetTrendbarsReq`, payloadType 2137)
```json
{
  "payloadType": 2137,
  "ctidTraderAccountId": 1234567,
  "symbolId": 1,
  "period": "H1", // M1, M5, M15, H1, H4, D1
  "fromTimestamp": 1600000000000,
  "toTimestamp": 1600086400000
}
```

---

## 3. Order Placement (`ProtoOANewOrderReq`, payloadType 2106)
```json
{
  "payloadType": 2106,
  "ctidTraderAccountId": 1234567,
  "symbolId": 1,
  "orderType": "MARKET",
  "tradeSide": "BUY", // BUY or SELL
  "volume": 100000,   // Volume in cents (e.g. 100000 = 1 standard lot of 100,000 units)
  "stopLoss": 1.0850,
  "takeProfit": 1.0950
}
```

---

## 4. Pytest Mocking Pattern
```python
def test_ctrader_token_exchange(monkeypatch):
    class MockTokenResponse:
        status_code = 200
        def json(self):
            return {
                "accessToken": "mock_access_token_123",
                "refreshToken": "mock_refresh_token_456",
                "expiresIn": 2592000
            }
        def raise_for_status(self): pass

    monkeypatch.setattr("requests.post", lambda url, **kwargs: MockTokenResponse())
```
