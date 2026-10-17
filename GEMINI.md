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

9. **Market Imbalances, CME Gaps & Liquidity Clusters**:
   * **CME Gaps as Magnets**: Weekend gaps between Friday 17:00 ET close and Sunday 18:00 ET open act as macro mean-reversion targets and high-probability take-profit zones, not immediate breakout triggers.
   * **Liquidity Sweeps**: Clusters of stop-losses resting at Equal Highs (EQH) and Equal Lows (EQL) are frequently swept before genuine market reversals occur. Never place breakout market orders directly into un-swept liquidity pools.
   * **Volume Profile Integration**: Focus entries near the Value Area boundaries (VAH/VAL) or High Volume Nodes (HVN); anticipate rapid price acceleration across Low Volume Nodes (LVN).

10. **Multi-API Rate Limiting, 429 Backoff & Concurrency Invariants**:
    * **Binance Weight Limits & 418 Avoidance**: Spot REST has a 1200 request weight/min IP limit (monitored via `x-mbx-used-weight-1m`). Never burst calls without weight tracking. On HTTP 429, halt immediately and sleep for the duration indicated in `Retry-After`. Continued requests after 429 trigger HTTP 418 (IP ban) lasting from 2 minutes up to 3 days.
    * **Kraken Leaky Bucket Counter**: Private endpoints cost 1–2 points against a decaying call counter (Starter: 15 max, 0.33/s decay; Intermediate/Pro: 20 max, 0.5–1.0/s decay). On `EAPI:Rate limit exceeded`, immediately back off by at least 5 seconds.
    * **Trading 212 Pacing & Cache**: Enforce max 1 request/sec for orders and 30 requests/min for general endpoints. Cache balance/cash queries with short TTL (10–30s) instead of polling on every tick.
    * **eToro Adapter Throttling**: Enforce minimum 1.2s interval between requests via `RateThrottler` to avoid account-level throttling.
    * **Yahoo Finance & Free Feeds**: Limit to max 1–2 req/sec with cached snapshot payloads; rapid polling leads to HTTP 429 or crumb invalidation.
    * **Local Ollama Concurrency**: Local LLM inference must be serialized (concurrency lock / semaphore = 1) with 45–90s timeouts to prevent GPU VRAM exhaustion or queue lockup.
    * **Exponential Backoff with Jitter**: All retry loops on transient HTTP 429/502/503 errors must use exponential backoff with randomized jitter: $t_{\text{wait}} = \min(t_{\max}, 2^{\text{attempt}} + \text{uniform}(0, 1))$.

11. **Dual-Host Topology & Remote Execution Invariants (`lgram` vs `trader`)**:
    * **Host Roles & Environment Separation**:
      - **Developer Laptop (`lgram`)**: Arch Linux laptop where Antigravity runs. Repository workspace is at `/home/vineet/mnt/trader-core` (mounted over SSH). Code authoring, pytest verification, and local development occur here.
      - **Runtime LXC Container (`trader`)**: Production Linux container on the LAN. Repository is at `~/trader-core` (`/home/vineet/trader-core`). Runs systemd Podman Quadlet services (`trader-dashboard`, `trader-engine`), has direct LAN connectivity to Ollama (`10.10.10.15:11434`) and Open-WebUI (`192.168.2.15:8080`), and manages persistent storage at `/var/lib/trader-core/data`.
    * **Path Mapping Invariant**:
      - When proposing terminal commands for the user to run on the server `[vineet@trader ~]$`, ALWAYS use remote container paths (`cd ~/trader-core`), NEVER laptop mount paths (`~/mnt/trader-core` or `/mnt/trader`).
    * **Git Push/Pull Synchronization Invariant**:
      - Code, deployment scripts, or Quadlets authored on `lgram` exist only on `lgram` until committed and pushed.
      - Before instructing the user to execute new scripts or services on `trader`, the agent MUST ensure changes are committed and pushed to `origin/main` on GitHub, and instruct the user to run `git pull` on `trader` first.
    * **Service Execution Target**:
      - Rootful or rootless Podman commands, `systemctl` service starts, and Quadlet activations belong strictly on `trader`.

12. **Local Ollama Model Inventory & Role Assignments (`10.10.10.15:11434`)**:
    * **Installed Model Catalog & Roles**:
      - `llama3.1:8b`: Primary Fast Dispatcher, multi-broker tool caller, and reactive technical scanner.
      - `deepseek-r1:14b`: Primary Institutional Quant Reasoner (chain-of-thought price action, liquidity sweeps, 1:2 R:R validation). Must be pulled on Ollama host via `ollama pull deepseek-r1:14b`.
      - `deepseek-r1:7b`: Fallback Deep Reasoner if 14B is offline, loading, or unpulled.
      - `nomic-embed-text:latest`: Vector embedding model for Open-WebUI Knowledge Base & RAG playbooks.
      - `qwen2.5-coder:14b`: Advanced quantitative logic, formula derivation, and script synthesis.
      - `llama3.2:3b` / `qwen3:4b-instruct`: Low-latency lightweight conversational fallbacks.
    * **Model Fallback Invariant**:
      - All backend routes querying Ollama (`/api/research/analyze`, `/api/orchestrator/synthesize`, `/api/agent/query`) must dynamically probe `/api/tags`.
      - If the preferred Deep Reasoner (`deepseek-r1:14b`) is not installed or returns HTTP 404, the system must automatically fall back to `deepseek-r1:7b` without raising an unhandled 500/502 error to the user.

13. **Systematic Day Trading Discipline & Execution Invariants**:
    * **Mandatory Risk-to-Reward Constraint ($\text{R:R} \ge 2.0$)**:
      - Every single trade setup proposed, backtested, or executed must demonstrate a mathematical Risk-to-Reward ratio of at least $1:2.0$:
        $$\text{R:R} = \frac{|\text{TakeProfit} - \text{Entry}|}{|\text{Entry} - \text{StopLoss}|} \ge 2.0$$
      - Sub-1:2 trades are strictly rejected by `RiskSentinel`.
    * **Hard Day Trading Guardrails**:
      - **Max Order Notional**: Maximum order allocation is capped at $\$50.00$ USD per trade.
      - **Stop-Loss Cap**: Stop loss distance cannot exceed $2.0\%$ of entry price.
      - **Daily Drawdown Circuit Breaker**: If realized intraday loss hits $3.0\%$, all trading halts for 24 hours.
    * **Session Awareness & High-Liquidity Windows**:
      - Focus intraday execution within high-volume session windows:
        - London Open: `07:00 – 10:00 UTC`
        - London / New York Overlap: `12:00 – 16:00 UTC`
        - Asian Range Sweep: `00:00 – 04:00 UTC`
      - Prohibit initiating new breakout entries during low-volume "dead zones" (21:00 – 23:00 UTC) or weekend crypto/forex gap-risk periods.
    * **Flat End-of-Day (EOD) Protocol**:
      - Day trading positions must be closed or transitioned to breakeven trailing stops before session close (21:00 UTC for equities/forex) to avoid overnight financing costs and gap risk.
    * **No Market Chasing**:
      - Entries must be anchored to structural price action: Fair Value Gap (FVG) retests, liquidity pool sweeps (EQH/EQL), or Value Area High/Low (VAH/VAL) rejections.

14. **Social Sentiment & Macro Event Catalyst Invariants (Agent C Sentinel)**:
    * **Tier-1 Macro Event Trading Embargo**:
      - Automated entry execution must pause 30 minutes prior to and 15 minutes after Tier-1 economic releases (US Core CPI, FOMC Rate Decision & Press Conference, Non-Farm Payrolls / NFP, Core PCE) to protect capital from extreme binary spread widening and stop-hunt wicks.
    * **Social Sentiment Divergence Invariant**:
      - Track Twitter/X and Discord trader sentiment consensus against price structure:
        - **Retail Bull Trap**: Heavy bullish chatter ($>75\%$ bull sentiment) into equal highs (EQH) resistance indicates institutional distribution / liquidity sweep; avoid buying breakouts.
        - **Capitulation Long**: Extreme bearish sentiment ($>75\%$ bear chatter) accompanied by hammer rejection wicks into an unfilled FVG or CME gap indicates high-probability mean reversion accumulation.
    * **On-Chain Whale Flow Signals**:
      - Large exchange outflows ($>\$20\text{M}$) confirm institutional spot absorption (bullish supply sink).
      - Large exchange inflows to spot/derivative wallets indicate imminent dumping or hedging pressure.
    * **Multi-LLM Hierarchical Reasoning**:
      - Fast triage via `llama3.1:8b`, deep chain-of-thought structural reasoning via `deepseek-r1:14b` (fallback `7b`), and market intelligence briefs synthesized by Agent C Sentinel.




