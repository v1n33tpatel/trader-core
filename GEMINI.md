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
   * Turnover costs (`one_way_cost_bps`) must be deducted on position entries, adjustments, and terminal portfolio liquidation.
   * All timestamps must be UTC timezone-aware (`datetime.now(timezone.utc)` or `pd.to_datetime(..., utc=True)`). Avoid deprecated `datetime.utcnow()`.

3. **Broker Adapters**:
   * All broker adapters must fail gracefully, returning `(0.0, [])` when credentials are unconfigured or when network timeouts occur.
   * Float asset amounts (crypto quantities, cash) should be rounded cleanly (e.g. 8 decimals for crypto satoshis, 2 decimals for fiat currency) to avoid floating-point representation artifacts.

4. **Testing Requirements**:
   * Whenever adding new strategies, broker functions, or API routes, write corresponding tests under `tests/`.
   * Ensure tests run cleanly with `./.venv/bin/python -m pytest`.
