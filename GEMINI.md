# MoneyMakingMachine (trader-core) — Agent & Developer Guide

This repository contains **MoneyMakingMachine / QWERTY CORP**, an algorithmic trading workstation, multi-broker tracking system, offline backtesting framework, and local AI-assisted quantitative research terminal.

---

## 1. Quick Commands & Environment

Always use the project virtual environment located in `.venv`:

```bash
# Run test suite
./.venv/bin/python -m pytest

# Run specific test file
./.venv/bin/python -m pytest tests/test_backtest.py

# Run dashboard locally (development server on port 5000)
./.venv/bin/python main.py

# Run autonomous engine loop
./.venv/bin/python engine.py

# Run standalone momentum demo
./.venv/bin/python examples/momentum_demo.py
```

> [!IMPORTANT]
> The system Python environment does not contain Flask or project dependencies. Always invoke Python tools with `./.venv/bin/python` or activate `. .venv/bin/activate`.

---

## 2. Architecture & Directory Map

```
trader-core/
├── main.py                 # Primary Flask web application entrypoint
├── web_app.py              # Secondary / alternative Flask dashboard runner
├── engine.py               # Autonomous event loop (Binance feed -> Copilot strategy -> RiskSentinel -> StateStore)
├── dashboard.html          # Frontend UI (single-page quant terminal)
├── dashboard.js            # Client-side state, API pings, Canvas charting, Ollama integration
├── dashboard.css           # Terminal styling and dark-theme design system
│
├── src/quant_trading/      # Core backtesting research library (installed as quant-trading-algos)
│   ├── backtest.py         # BacktestEngine, BacktestConfig, BacktestResult (turnover costs & lag)
│   ├── strategy.py         # Strategy protocol, TimeSeriesMomentum strategy
│   ├── data.py             # validate_close_prices (DatetimeIndex, strictly positive, finite)
│   ├── metrics.py          # calculate_metrics (Sharpe, max drawdown, returns, volatility)
│   ├── market_data.py      # YahooFinanceProvider, BinanceMarketDataProvider, get_market_snapshot
│   └── flask_api.py        # research_blueprint routes (/api/market/data, /api/research/*, /api/status)
│
├── brokers/                # Broker integration adapters
│   ├── base.py             # BaseBroker abstract interface
│   ├── t212_adapter.py     # Trading212Broker (Invest account, portfolio & cash balances)
│   ├── etoro_adapter.py    # EtoroBroker (Demo portfolio, orders, rate-throttling)
│   ├── binance_adapter.py  # BinanceBroker (HMAC-SHA256 authenticated spot account balances)
│   └── kraken_adapter.py   # KrakenBroker (HMAC-SHA512 authenticated spot private balance)
│
├── strategies/             # Strategy implementations & registry
│   ├── base.py             # BaseStrategy (evaluates state) & BaseEventStrategy (on_bar event-driven)
│   ├── active_strategy.py  # CopilotActiveStrategy (RSI + Fair Value Gap detection)
│   ├── registry.py         # STRATEGY_CATALOG catalog definitions
│   ├── factory.py          # get_strategy_instance factory loader
│   ├── crypto/             # atr_trailing_breakout, fvg_breakout, rsi_reversion
│   ├── etf/                # sma_macro_regime, dynamic_dca
│   └── forex/              # london_ny_overlap, carry_rsi_swing
│
├── risk/                   # Capital preservation & guardrails
│   ├── guardrail.py        # RiskSentinel (circuit breaker, max drawdown halt, order sizing)
│   ├── risk_manager.py     # Allocation limits & position count checks
│   └── throttler.py        # RateThrottler for API pacing
│
├── models/                 # Shared data contracts
│   ├── events.py           # Immutable BarEvent, SignalEvent, OrderEvent dataclasses
│   ├── market_data.py      # MarketData quote model
│   ├── position.py         # Position model
│   └── signal.py           # Signal and SignalType definitions
│
├── core/                   # Persistence & state
│   └── state_store.py      # SQLite StateStore (trader_state.db positions & daily audits)
│
├── feeds/                  # External data ingestion & reasoning
│   ├── binance_feed.py     # REST klines & live RSI-14 calculator
│   └── ai_reasoner.py      # AIStrategyReasoner connecting to local Ollama instance
│
├── deploy/                 # Container and system deployment
│   └── trader-dashboard-podman.container # Rootful Podman Quadlet systemd service
└── tests/                  # Unit and integration tests (pytest)
```

---

## 3. Development & Coding Guidelines

1. **Security & Credentials**:
   * Never hardcode API keys, secrets, or bearer tokens in source code.
   * Credential resolution priority:
     1. Environment variables (`os.getenv`)
     2. Root `.env`
     3. Broker-specific config files (`t212.env`, `etoro.env`, `config/`)
   * All API status routes (`/api/status`) must return only `online`, `offline`, or `unconfigured`—never reveal tokens or sensitive headers.

2. **Quant & Backtest Mechanics**:
   * Strategy signals must strictly assume execution delay: close-price signals fill at the next close to avoid lookahead bias.
   * Turnover costs (`one_way_cost_bps`) must be deducted on position entries, adjustments, and terminal portfolio liquidation: $\text{Cost}_t = |w_t - w_{t-1}| \times \text{bps} \times 10^{-4}$.
   * Metric annualization factors: daily equities use $\sqrt{252}$; 24/7 daily crypto uses $\sqrt{365}$; hourly crypto uses $\sqrt{365 \times 24} \approx 93.6$.
   * Evaluate strategies using both Sharpe ($\frac{\mu - r_f}{\sigma}$) and Sortino ($\frac{\mu - r_f}{\sigma_{down}}$) to account for downside return asymmetry.
   * Volatility-targeted weights must cap maximum leverage: $w_t = \text{clip}\left(\frac{\sigma_{\text{target}}}{\hat{\sigma}_t} \cdot \text{signal}_t, -L_{\max}, L_{\max}\right)$.
   * All timestamps must be UTC timezone-aware (`datetime.now(timezone.utc)` or `pd.to_datetime(..., utc=True)`). Avoid deprecated `datetime.utcnow()`.

3. **Broker Adapters**:
   * All broker adapters must fail gracefully, returning `(0.0, [])` when credentials are unconfigured or when network timeouts occur.
   * Float asset amounts (crypto quantities, cash) should be rounded cleanly (e.g. 8 decimals for crypto satoshis, 2 decimals for fiat currency) to avoid floating-point representation artifacts.

4. **Testing Requirements**:
   * Whenever adding new strategies, broker functions, or API routes, write corresponding tests under `tests/`.
   * Ensure tests run cleanly with `./.venv/bin/python -m pytest`.

5. **Binance API & Crypto Feed Guidelines**:
   * **Endpoint & Base URL**: Standard Spot REST base is `https://api.binance.com`. Klines are fetched from `/api/v3/klines`.
   * **Pair Normalization**: Always normalize crypto symbols to uppercase concatenated format without slashes (e.g. `BTCUSDT`, `ETHUSDT`). Use `f"{symbol.upper()}USDT" if not symbol.endswith("USDT") else symbol.upper()`.
   * **Kline Schema & Type Parsing**: Kline values from Binance arrive as strings. Always explicitly cast open `k[1]`, high `k[2]`, low `k[3]`, close `k[4]`, and volume `k[5]` to `float`.
   * **HMAC-SHA256 Signing**: For private endpoints (`/api/v3/account`, `/api/v3/order`), include `X-MBX-APIKEY` header, `recvWindow=5000`, `timestamp` in ms (`int(time.time() * 1000)`), and append the hex digest signature.
   * **Web Architecture & Security**: Never expose Binance API keys or private endpoints directly to the browser frontend. All authenticated requests must be proxied through the backend. For live client-side candlestick/ticker updates without backend polling, connect the browser directly to Binance public WebSockets (`wss://stream.binance.com:9443/ws/<symbol>@kline_<interval>`).
   * **Mock-First Testing**: Pytest tests must never issue live HTTP requests to Binance; always mock via `monkeypatch` with sample kline lists.

6. **Kraken API & Broker Guidelines**:
   * **Endpoint & Base URLs**: REST base is `https://api.kraken.com`. WebSocket v2 base is `wss://ws.kraken.com/v2` (public) and `wss://ws-auth.kraken.com/v2` (private with token).
   * **Authentication (HMAC-SHA512)**: Private endpoints require `API-Key` and `API-Sign` headers. The signature is computed over `urlpath + sha256(nonce + postdata)` using `base64.b64decode(api_secret)` with SHA512.
   * **Nonce Invariant**: `nonce` must be a strictly increasing integer (`int(time.time() * 1000)`).
   * **Asset Normalization**: Strip legacy `X` and `Z` prefixes from assets (e.g. `XXBT` -> `BTC`, `ZUSD` -> `USD`) and ignore staking suffixes (`.S`, `.F`).
   * **Web Security**: Never expose Kraken credentials to the frontend. For live web charts, connect browsers directly to WebSocket v2 `ohlc` channel.
   * **Mock-First Testing**: Pytest tests must mock private Kraken balance responses and never hit live endpoints.

7. **Trading 212 API & Broker Guidelines**:
   * **Endpoint & Base URLs**: Demo is `https://demo.trading212.com/api/v0`; Live is `https://live.trading212.com/api/v0`.
   * **Authentication**: Use HTTP Basic Auth with base64-encoded `API_KEY:API_SECRET` in the `Authorization` header.
   * **Order Sign Invariant**: Buy orders require positive quantity (`quantity > 0`); sell orders **must** use negative quantity (`quantity < 0`, e.g. `-10.0`).
   * **Non-Idempotent Market Orders**: Market orders cannot be safely retried upon timeout; check `/equity/orders` or order history before re-submitting.
   * **Ticker Normalization**: Strip exchange suffixes (`_US_EQ`, `_EQ`, `l_EQ`, `.L`) for clean UI display, but retain the raw ticker for API order requests.
   * **Rate Limits & Fail-Safe**: Per-account rate limits return HTTP 429. Adapters must fail safely, returning `(0.0, [])` upon error.
   * **Mock-First Testing**: Pytest tests must never issue live HTTP calls to Trading 212; always mock via `monkeypatch`.

8. **cTrader Open API & Broker Guidelines**:
   * **Endpoints & Ports**: Live host is `live.ctraderapi.com`; Demo host is `demo.ctraderapi.com`. Port `5035` is Protocol Buffers (TCP/WSS); Port `5036` is JSON.
   * **Two-Tier Authentication**: First exchange OAuth 2.0 authorization code for `accessToken` via `https://connect.spotware.com/apps/token`. Over the socket, send `ProtoOAApplicationAuthReq` (with `clientId`/`clientSecret`), then `ProtoOAAccountAuthReq` (with `ctidTraderAccountId`/`accessToken`).
   * **Web Security**: Client secrets and OAuth token exchanges must remain strictly on the backend. Never expose cTrader application secrets to frontend JavaScript.
   * **Mock-First Testing**: Pytest tests must never open live sockets to cTrader; always mock transport layers and message handlers.

