import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Any
from core.state_store import StateStore
from strategies.registry import STRATEGY_CATALOG


def get_price_action_playbook_doc() -> Dict[str, str]:
    """Generates the Institutional Price Action & Market Structure playbook."""
    content = """# Institutional Price Action & Market Structure Playbook
## MoneyMakingMachine Quantitative Strategy Standard

### 1. Core Mandate: Pure Reactive Execution
- **Non-Predictive Requirement**: Never attempt to forecast or guess future market direction based on lagging oscillator levels (e.g. overbought/oversold RSI alone is strictly forbidden as an entry trigger).
- **Reaction Over Prediction**: React exclusively to verified market structure events that have already printed on the candlestick chart.
- **Strategic Restraint**: "HOLD" is an active, strategic position. Cash preserves purchasing power and eliminates negative carry during chop.

### 2. Market Structure Architecture
- **Swing Highs & Lows**:
  - A valid Swing High requires a central candle whose high exceeds the preceding and succeeding *N* candles (default window: 4 to 5 bars).
  - A valid Swing Low requires a central candle whose low is lower than the preceding and succeeding *N* candles.
- **Break of Structure (BOS)**:
  - **Bullish BOS**: Candle body close strictly above the most recent confirmed Swing High in an existing uptrend.
  - **Bearish BOS**: Candle body close strictly below the most recent confirmed Swing Low in an existing downtrend.
- **Change of Character (ChoCH)**:
  - Occurs when price breaches the structural counter-swing that initiated the most recent leg, indicating potential institutional trend transition.

### 3. Liquidity Sweeps & Pinbar Rejections
- **Liquidity Pools**:
  - Retail stop-losses accumulate above Equal Highs (EQH) and below Equal Lows (EQL).
  - Institutions engineer liquidity sweeps into these pools to accumulate spot inventory against retail stops.
- **Confirmed Bullish Liquidity Sweep**:
  1. Price penetrates below a prior Swing Low or EQL pool.
  2. The bar prints a long lower shadow (wick ratio $\\ge 50\\%$ of total candle range).
  3. The candle closes back inside the prior range, confirming rejection and absorption of retail selling pressure.
- **Confirmed Bearish Liquidity Sweep**:
  1. Price penetrates above a prior Swing High or EQH pool.
  2. The bar prints a long upper shadow (wick ratio $\\ge 50\\%$ of total range).
  3. The candle closes back below the range, confirming rejection and absorption of retail buying pressure.

### 4. Fair Value Gaps (FVG)
- **3-Candle Imbalance**:
  - **Bullish FVG**: Candle 3's low is strictly higher than Candle 1's high, creating an unfilled buy imbalance pocket.
  - **Bearish FVG**: Candle 3's high is strictly lower than Candle 1's low, creating an unfilled sell imbalance pocket.
- **Mitigation Entry**: Entries occur strictly upon a retest of the FVG boundary in alignment with higher timeframe structure.

### 5. Risk-to-Reward (R:R) & Invalidation Rules
- **Structural Invalidation (Stop-Loss)**:
  - For BUY setups: Stop-loss must be anchored strictly below the extreme lower wick of the sweep/rejection candle.
  - For SELL setups: Stop-loss must be anchored strictly above the extreme upper wick of the sweep/rejection candle.
- **Mandatory 1:2 R:R Ratio**:
  - Take-profit must be positioned at a minimum of $2.0\\times$ the risk distance:
    $$\\text{Target Price} = \\text{Entry} + 2.0 \\times (\\text{Entry} - \\text{Stop Loss})$$
  - Any trade setup offering less than 1:2 R:R is automatically invalid and must be rejected.
"""
    return {
        "filename": "institutional_price_action_playbook.md",
        "title": "Institutional Price Action & Market Structure Playbook",
        "description": "Institutional Price Action, FVG, Liquidity Sweeps, and 1:2 R:R guidelines",
        "content": content
    }


def get_risksentinel_envelope_doc() -> Dict[str, str]:
    """Generates the RiskSentinel capital preservation rules."""
    content = """# RiskSentinel Capital Preservation & Execution Envelope
## Safety Guardrails and Pre-Macro Event Halts

### 1. Pre-Macro Event Risk Halts
- **Tier-1 Macro Reports Monitored**:
  - Core Consumer Price Index (Core CPI MoM / YoY)
  - Federal Open Market Committee (FOMC) Interest Rate Decisions & Press Conferences
  - Non-Farm Payrolls (NFP) & Unemployment Rate
  - Gross Domestic Product (GDP Advance prints)
- **Automated Circuit Breaker**:
  - When a Tier-1 macro release is scheduled within **30 minutes** (`minutes_away <= 30`), `RiskSentinel` automatically enters **EVENT_RISK_HALT**.
  - All new buy/sell order signals are rejected to prevent execution during catastrophic binary spread widening and high-slippage volatility.
  - Execution resumes only after the macro print has cleared and liquidity normalizes.

### 2. Portfolio Drawdown & Order Sizing Rules
- **Daily Drawdown Circuit Breaker**:
  - Hard limit: **3.0%** maximum account drawdown per rolling 24-hour cycle.
  - If daily realized losses reach or exceed 3.0%, the circuit breaker trips permanently for the day, halting all automated trading until the daily audit reset.
- **Risk Per Trade**:
  - Maximum risk allocation per trade: **2.0%** of total account equity.
- **Order Dollar Allocation Cap**:
  - Standard trade size cap: **$50.00 USD** max per individual order.
  - Prevents single-position concentration risk.
- **Position Count Limits**:
  - Maximum concurrent open positions: **5 active positions**.
  - New buy signals are rejected if the portfolio already holds 5 positions.

### 3. Execution Fail-Safes
- If connection to market feeds, Ollama, or brokers drops, the system defaults to **SAFE HOLD**.
- Orders are never retried upon network timeouts without verifying broker order state first (preventing duplicate execution).
"""
    return {
        "filename": "risksentinel_execution_envelope.md",
        "title": "RiskSentinel Capital Preservation Envelope",
        "description": "RiskSentinel capital preservation envelope, 2% stop-loss, 3% circuit breaker, pre-macro halts",
        "content": content
    }


def get_broker_execution_doc() -> Dict[str, str]:
    """Generates broker integration rules and sign conventions."""
    content = """# Multi-Broker API & Execution Invariants
## Trading 212, eToro, Binance, and Kraken Integration Standards

### 1. Trading 212 API (Invest Account)
- **Base URLs**:
  - Demo: `https://demo.trading212.com/api/v0`
  - Live: `https://live.trading212.com/api/v0`
- **CRITICAL Order Sign Invariant**:
  - Buy orders require positive quantity: `quantity > 0` (e.g. `+5.0`).
  - Sell orders MUST use negative quantity: `quantity < 0` (e.g. `-5.0`).
- **Rate Limits**:
  - Max 1 request/sec for orders; max 30 requests/min for general queries.
  - Cache balance/cash queries with short TTL (10–30s).

### 2. Binance Spot REST API
- **Endpoint**: `https://api.binance.com`
- **Symbol Normalization**: Uppercase concatenated format without slashes (e.g. `BTCUSDT`, `ETHUSDT`).
- **Authentication**: HMAC-SHA256 signature with `X-MBX-APIKEY` header and `recvWindow=5000`.
- **IP Weight Limit**: 1,200 request weight/min. On HTTP 429, back off immediately using exponential jitter. Continued requests after 429 trigger HTTP 418 bans.

### 3. Kraken Spot API
- **Endpoint**: `https://api.kraken.com`
- **Authentication**: HMAC-SHA512 over `urlpath + sha256(nonce + postdata)` with base64 secret.
- **Nonce Requirement**: Strictly increasing integer millisecond timestamp.
- **Asset Normalization**: Strip legacy `X` and `Z` prefixes (e.g. `XXBT` -> `BTC`, `ZUSD` -> `USD`).

### 4. Demo vs. Real Safety Standard
- The workstation defaults strictly to **`DEMO`** execution.
- Switching to live real capital requires explicit confirmation via the safety modal and updates `trader_state.db` setting `environment_mode="real"`.
"""
    return {
        "filename": "multi_broker_execution_guide.md",
        "title": "Multi-Broker API & Execution Invariants",
        "description": "Multi-broker order invariants, rate limits, and sign conventions",
        "content": content
    }


def get_live_state_journal_doc() -> Dict[str, str]:
    """Dynamically compiles live trading state and audit logs from StateStore."""
    store = StateStore()
    env = store.get_setting("environment_mode", "demo").upper()
    strat = store.get_setting("active_strategy", "price_action")
    mode = store.get_setting("automation_mode", "reactive")
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Fetch positions from SQLite
    positions_md = []
    try:
        with sqlite3.connect(store.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT position_id, symbol, broker, side, units, entry_price, current_price, opened_at FROM positions")
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    pnl = round((r[6] - r[5]) * r[4], 2) if r[3] == "BUY" else round((r[5] - r[6]) * r[4], 2)
                    positions_md.append(f"| {r[0]} | {r[1]} | {r[2].upper()} | {r[3]} | {r[4]} | ${r[5]:.2f} | ${r[6]:.2f} | ${pnl:+.2f} | {r[7]} |")
            else:
                positions_md.append("| — | No active open positions | — | — | — | — | — | — | — |")
    except Exception as e:
        positions_md.append(f"| Error fetching positions: {str(e)} |")

    # Fetch daily audit
    audit_md = []
    try:
        with sqlite3.connect(store.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT date, realized_pnl, order_count FROM daily_audit ORDER BY date DESC LIMIT 5")
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    audit_md.append(f"| {r[0]} | ${r[1]:+.2f} | {r[2]} orders |")
            else:
                audit_md.append("| Today | $0.00 | 0 orders |")
    except Exception as e:
        audit_md.append(f"| Error fetching audit: {str(e)} |")

    content = f"""# TraderCore Active State & Execution Journal
**Generated Snapshot**: {now_utc}

### 1. Workstation Runtime Configuration
- **Account Mode**: `{env}` ({'Practice Simulation' if env == 'DEMO' else 'LIVE CAPITAL AT RISK'})
- **Active Algorithmic Strategy**: `{strat}`
- **Engine Automation Mode**: `{mode.upper()}`
- **Capital Safety Guard**: RiskSentinel ARMED ($50 Max Order, 2.0% Stop, 3.0% Circuit Breaker)

### 2. Active Portfolio Positions
| Position ID | Symbol | Broker | Side | Units | Entry Price | Current Price | Unrealized PnL | Opened At |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{chr(10).join(positions_md)}

### 3. Recent Daily Audit History
| Date | Realized PnL | Order Count |
| :--- | :--- | :--- |
{chr(10).join(audit_md)}

### 4. Operational Directives for the AI Orchestrator
- Treat the above positions and limits as ground truth.
- Do not exceed the 5-position cap or $50 allocation limit.
- If in DEMO mode, execute simulated orders via the StateStore. If in REAL mode, require strict risk validation.
"""
    return {
        "filename": "live_state_journal.md",
        "title": "TraderCore Live State & Execution Journal",
        "description": "Live snapshot of active positions, daily audit, and workstation settings",
        "content": content
    }


def get_all_rag_documents() -> List[Dict[str, str]]:
    """Returns all 4 RAG knowledge documents ready for Open-WebUI ingestion."""
    return [
        get_price_action_playbook_doc(),
        get_risksentinel_envelope_doc(),
        get_broker_execution_doc(),
        get_live_state_journal_doc()
    ]
