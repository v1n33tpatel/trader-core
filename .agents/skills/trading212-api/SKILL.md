---
name: trading212-api
description: >-
  Use this skill whenever integrating, modifying, or testing Trading 212 Public API (v0) endpoints,
  authenticating via HTTP Basic Auth, handling negative-quantity sell orders, or writing mocked unit tests.
---

# Trading 212 API (v0) Integration & Cheatsheet

Guidelines, schemas, and reference patterns for the Trading 212 Public API (v0) for Equities (Invest and ISA).

## Base URLs
* **Demo / Paper**: `https://demo.trading212.com/api/v0`
* **Live Trading**: `https://live.trading212.com/api/v0`

---

## 1. Authentication (HTTP Basic Auth)
```python
import base64
import requests

def t212_headers(api_key: str, api_secret: str) -> dict:
    credentials = f"{api_key}:{api_secret}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
    }
```

---

## 2. Portfolio & Cash Ingestion
```python
def get_t212_account(base_url: str, headers: dict) -> tuple[float, list[dict]]:
    # 1. Fetch free cash
    r_cash = requests.get(f"{base_url}/equity/account/cash", headers=headers, timeout=5)
    cash = float(r_cash.json().get("free", 0.0)) if r_cash.status_code == 200 else 0.0

    # 2. Fetch positions
    r_pos = requests.get(f"{base_url}/equity/portfolio", headers=headers, timeout=5)
    positions = []
    if r_pos.status_code == 200:
        for p in r_pos.json():
            raw_ticker = p.get("ticker", "")
            clean = raw_ticker.replace("_US_EQ", "").replace("_EQ", "").replace("l_EQ", "").replace(".L", "")
            positions.append({
                "ticker": clean,
                "raw_ticker": raw_ticker,
                "units": float(p.get("quantity", 0.0)),
                "average_price": float(p.get("averagePrice", 0.0)),
                "current_price": float(p.get("currentPrice", 0.0)),
                "ppl": float(p.get("ppl", 0.0)),
            })
    return cash, positions
```

---

## 3. Order Placement Rules
> [!IMPORTANT]
> To **SELL**, `quantity` must be **NEGATIVE** (e.g. `-10.0`). Positive quantity represents a BUY.

```python
def place_t212_market_order(base_url: str, headers: dict, ticker: str, quantity: float, side: str) -> dict:
    # Ensure quantity sign matches side
    qty = abs(quantity) if side.upper() == "BUY" else -abs(quantity)
    payload = {
        "ticker": ticker,      # e.g. "AAPL_US_EQ"
        "quantity": qty,       # Positive = BUY, Negative = SELL
    }
    res = requests.post(f"{base_url}/equity/orders/market", headers=headers, json=payload, timeout=5)
    res.raise_for_status()
    return res.json()
```

---

## 4. Pytest Mocking Pattern
```python
def test_t212_portfolio(monkeypatch):
    class MockCashResponse:
        status_code = 200
        def json(self): return {"free": 542.50, "total": 1200.00}

    class MockPosResponse:
        status_code = 200
        def json(self): return [
            {"ticker": "AAPL_US_EQ", "quantity": 10.0, "averagePrice": 150.0, "currentPrice": 160.0, "ppl": 100.0}
        ]

    def mock_get(url, **kwargs):
        if "cash" in url: return MockCashResponse()
        return MockPosResponse()

    monkeypatch.setattr("requests.get", mock_get)
```
