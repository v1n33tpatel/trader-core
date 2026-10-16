---
name: api-rate-limiting
description: >-
  Use this skill whenever managing API rate limits, tracking request weights (Binance),
  implementing leaky bucket counters (Kraken), handling HTTP 429/418 errors,
  or writing retry loops with exponential backoff and jitter across brokers.
---

# Multi-Broker API Rate Limiting & 429 Resilience Guide

This guide establishes exact rate limit specifications, penalty thresholds, header parsing patterns, and Python algorithms for pacing requests across all external broker and data APIs in **MoneyMakingMachine (`trader-core`)**.

---

## 1. Multi-Broker Rate Limit Matrix

| Provider / API | Rate Limit Model | Threshold / Capacity | Penalty / Status Code | Key Headers to Watch |
| :--- | :--- | :--- | :--- | :--- |
| **Binance Spot** | Weight-based (Per IP & Account) | 1,200 weight / min (IP)<br>6,000 raw requests / min | **HTTP 429** (Rate Limit Exceeded)<br>**HTTP 418** (IP Ban: 2 min – 3 days) | `x-mbx-used-weight-1m`<br>`Retry-After` |
| **Kraken Spot** | Leaky Bucket Call Counter | Tier-dependent (15–20 max counter)<br>Decay: 0.33 to 1.0 points / sec | `EAPI:Rate limit exceeded`<br>(HTTP 200 with error array) | Response body error field |
| **Trading 212** | Fixed Window / Account & IP | Orders: 1 req / sec<br>General / Info: 30–50 req / min | **HTTP 429** (Too Many Requests) | `x-ratelimit-reset`<br>`Retry-After` |
| **eToro** | Fixed Interval Pacing | Max 10–20 req / min<br>Min 1.2s delay between calls | **HTTP 429** or account lock | `Retry-After` |
| **cTrader Open** | Message / Quota Pacing | 50 messages / sec per connection<br>5 historical req / sec per account | Socket disconnect or `OA_ERROR` | `ProtoOAErrorRes` |
| **Yahoo Finance** | Dynamic / Unofficial IP rate | ~1–2 req / sec<br>Requires caching (TTL $\ge$ 60s) | **HTTP 429** or Crumb invalidation | `Retry-After` |
| **Local Ollama** | GPU Hardware Concurrency | Serial (1 concurrent request)<br>Context queue timeout 45–90s | **HTTP 502 / 504** or OOM GPU crash | None (Client-side semaphore) |

---

## 2. Binance API: Weight-Based Management

### Rules of Engagement
1. **Weight Tracking**: Each endpoint consumes a distinct "weight":
   * `GET /api/v3/ping` = 1
   * `GET /api/v3/time` = 1
   * `GET /api/v3/klines` = 2
   * `GET /api/v3/ticker/price` = 2 (single symbol) or 4 (all symbols)
   * `GET /api/v3/account` = 20
   * `POST /api/v3/order` = 1
2. **Buffer Margin**: Stop issuing non-essential requests once `x-mbx-used-weight-1m` reaches **950** (80% of the 1200 limit).
3. **HTTP 418 Ban Avoidance**:
   * If Binance returns **HTTP 429**, stop ALL requests immediately.
   * Parse `Retry-After` (in seconds). If not present, default to a minimum sleep of 60 seconds.
   * Continuing to send requests after receiving a 429 escalates to **HTTP 418**, which bans the IP address from 2 minutes up to 3 days.

### Sliding-Window Python Implementation

```python
import time
from collections import deque
from typing import Optional

class BinanceWeightTracker:
    def __init__(self, max_weight_per_min: int = 1000):
        self.max_weight = max_weight_per_min  # Conservative buffer under 1200
        self.window = deque()  # (timestamp, weight)

    def acquire(self, weight: int = 2) -> None:
        now = time.time()
        # Evict calls older than 60 seconds
        while self.window and now - self.window[0][0] >= 60.0:
            self.window.popleft()

        current_weight = sum(w for _, w in self.window)
        if current_weight + weight > self.max_weight:
            sleep_duration = 60.0 - (now - self.window[0][0]) + 0.1
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            return self.acquire(weight)

        self.window.append((time.time(), weight))
```

---

## 3. Kraken API: Leaky Bucket Counter

### Rules of Engagement
1. Each tier has a maximum counter limit:
   * **Starter**: 15 max, decay rate = 0.33 / sec
   * **Intermediate**: 20 max, decay rate = 0.50 / sec
   * **Pro**: 20 max, decay rate = 1.00 / sec
2. Endpoint costs:
   * Public OHLC/Ticker: 1 point
   * Private Balance / OpenOrders: 1 point
   * Private AddOrder / CancelOrder: 0 points (orders do not consume call counter)
   * Private Ledgers / TradeHistory: 2 points
3. When `counter + cost > max_counter`, the client must sleep until `(cost) / decay_rate` has elapsed.

### Leaky Bucket Python Implementation

```python
import time

class KrakenLeakyBucket:
    def __init__(self, max_capacity: float = 15.0, decay_rate: float = 0.33):
        self.max_capacity = max_capacity
        self.decay_rate = decay_rate
        self.current_counter = 0.0
        self.last_update = time.time()

    def acquire(self, cost: float = 1.0) -> None:
        now = time.time()
        elapsed = now - self.last_update
        # Counter decays over time down to minimum 0.0
        self.current_counter = max(0.0, self.current_counter - (elapsed * self.decay_rate))
        self.last_update = now

        if self.current_counter + cost > self.max_capacity:
            wait_time = (self.current_counter + cost - self.max_capacity) / self.decay_rate
            time.sleep(wait_time)
            return self.acquire(cost)

        self.current_counter += cost
```

---

## 4. Exponential Backoff with Jitter Invariant

Whenever retrying transient errors (HTTP 429, 502, 503, connection timeouts), always apply **Full Jitter** to prevent "thundering herd" synchronizations:

$$t_{\text{wait}} = \min(t_{\max}, 2^{\text{attempt}} + \text{uniform}(0, 1))$$

```python
import random
import time
from functools import wraps
import requests

def retry_with_jitter(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    response = func(*args, **kwargs)
                    if isinstance(response, requests.Response):
                        if response.status_code == 429:
                            retry_after = response.headers.get("Retry-After")
                            wait = float(retry_after) if retry_after else min(max_delay, (base_delay * (2 ** attempt)) + random.uniform(0.1, 1.0))
                            time.sleep(wait)
                            continue
                        elif response.status_code in (502, 503, 504):
                            wait = min(max_delay, (base_delay * (2 ** attempt)) + random.uniform(0.1, 1.0))
                            time.sleep(wait)
                            continue
                    return response
                except (requests.RequestException, TimeoutError):
                    if attempt == max_retries - 1:
                        raise
                    wait = min(max_delay, (base_delay * (2 ** attempt)) + random.uniform(0.1, 1.0))
                    time.sleep(wait)
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

---

## 5. Local Ollama AI Concurrency Lock

Local models (e.g. `deepseek-r1:7b`) loaded into GPU memory should not receive concurrent requests from the dashboard, background tasks, and research API simultaneously. Serialize access using a process-wide thread lock:

```python
import threading

OLLAMA_LOCK = threading.Lock()

def query_ollama_serialized(url: str, payload: dict, timeout: int = 60) -> dict:
    with OLLAMA_LOCK:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
```
