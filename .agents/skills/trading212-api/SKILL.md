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

## 4. Limit Order Placement (Precision Entries)
> [!IMPORTANT]
> Use Limit Orders (`/equity/orders/limit`) for all structural pullback entries (VAL, FVG CE) to prevent slippage. Avoid automated social "Pies" which execute market-on-open orders with severe fill slippage.

```python
def place_t212_limit_order(
    base_url: str,
    headers: dict,
    ticker: str,
    quantity: float,
    limit_price: float,
    time_validity: str = "DAY"  # "DAY" or "GOOD_TILL_CANCEL"
) -> dict:
    qty = abs(quantity)
    payload = {
        "ticker": ticker,           # e.g. "EQQQ_l_EQ"
        "quantity": qty,
        "limitPrice": round(limit_price, 4),
        "timeValidity": time_validity,
    }
    res = requests.post(f"{base_url}/equity/orders/limit", headers=headers, json=payload, timeout=5)
    res.raise_for_status()
    return res.json()
```

---

## 5. UK/EU UCITS ETF Mapping Table (Invest / ISA Accounts)
Direct US-domiciled ETFs cannot be purchased in UK/EU retail Invest or ISA accounts under PRIIPs regulations. Map US benchmarks to LSE UCITS equivalents:

| US Benchmark | LSE UCITS Ticker | T212 API Ticker | TER | Currency | Trait |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **QQQ** | `QQQA.L` | `QQQA_l_EQ` | 0.13% | GBX (Pence) | Lowest TER, unhedged GBP tracking |
| **QQQ** | `EQQQ.L` | `EQQQ_l_EQ` | 0.30% | GBX (Pence) | Sister fund to QQQ, distributing quarterly |
| **QQQ** | `EQGB.L` | `EQGB_l_EQ` | 0.35% | GBX (Pence) | Accumulating, currency-hedged to GBP |
| **SPY** | `VUSA.L` | `VUSA_l_EQ` | 0.07% | GBX (Pence) | S&P 500, distributing quarterly |
| **SPY** | `VUAG.L` | `VUAG_l_EQ` | 0.07% | GBX (Pence) | S&P 500, accumulating |
| **FTSE 100** | `VUKE.L` | `VUKE_l_EQ` | 0.09% | GBX (Pence) | Core UK equity benchmark |

---

## 6. FX Drag & Technical Target Mapping

### A. FX Drag Rules
* Trading USD-denominated tickers with GBP base currency incurs **0.15% on entry** and **0.15% on exit** (0.30% round trip).
* Executing via native **GBX (pence)** UCITS trackers eliminates this FX drag entirely.

### B. Proportional USD-to-GBX Limit Calculation
When converting a US Dollar structural target (e.g., QQQ Value Area Low at $\$482.65$) to an LSE UCITS equivalent:

$$\Delta\% = \frac{\text{Target}_{\text{USD}} - \text{Price}_{\text{US, spot}}}{\text{Price}_{\text{US, spot}}}$$
$$\text{Limit}_{\text{GBX}} = \text{Price}_{\text{UCITS, spot}} \times (1 + \Delta\%)$$

```python
def calculate_ucits_target_price(us_spot: float, us_target: float, ucits_spot: float) -> float:
    if us_spot <= 0 or ucits_spot <= 0:
        return 0.0
    pct_change = (us_target - us_spot) / us_spot
    return round(ucits_spot * (1.0 + pct_change), 2)
```

---

## 7. Account Profile Matrix
| Feature | Invest Account | Tax-Free ISA | CFD Account |
| :--- | :--- | :--- | :--- |
| **Direct US ETFs (QQQ, SPY)** | ❌ Blocked (PRIIPs) | ❌ Blocked (PRIIPs) | ✅ Allowed (`QQQ_US_EQ`) |
| **UCITS Equivalents (EQQQ, QQQA)**| ✅ Allowed | ✅ Allowed | ⚠️ Inefficient |
| **Leverage / Margin** | 1:1 (Cash Only) | 1:1 (Cash Only) | Up to 1:5 (20% margin) |
| **Overnight Financing / Swap** | None (£0.00) | None (£0.00) | Charged daily (compounding drag) |
| **Best Strategy Fit** | Multi-day / Multi-week DCA | Multi-year Tax-Free DCA | Short-term intraday scalp/swing |

---

## 8. Pytest Mocking Pattern
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
