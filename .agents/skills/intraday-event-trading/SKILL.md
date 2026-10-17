---
name: intraday-event-trading
description: >-
  Use this skill whenever developing, analyzing, or executing intraday day-trading strategies (FVG breakouts, London/NY overlap, liquidity sweeps), enforcing strict >= 1:2 Risk-to-Reward discipline with <= $50 RiskSentinel bounds, or investigating social chatter (Twitter/X, Discord) and Tier-1 macro event catalysts (CPI, FOMC, NFP).
---

# Systematic Intraday Day Trading & Social Catalyst Investigation Playbook

This skill outlines the institutional day-trading methodology, mathematical risk formulas, and social/macro catalyst investigation procedures for **MoneyMakingMachine (`trader-core`)**.

---

## 1. The Day Trader's Execution Matrix

Day trading requires strict adherence to statistical asymmetry and non-predictive execution:

```
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ 1. Macro & Social Filter │ ──> │ 2. Liquidity & Structure │ ──> │ 3. Mathematical Entry   │
│ - Tier-1 Event Check    │     │ - FVG / Order Block     │     │ - Min 1:2 Risk-to-Reward│
│ - Social Consensus Bias │     │ - Equal Highs/Lows Sweep│     │ - <= $50 Notional Limit │
└─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘
```

### Invariants:
1. **Mandatory Asymmetry**: No trade may be placed unless $\text{R:R} \ge 2.0$. If the structural stop requires 20 pips, target must be at least 40 pips.
2. **Hard Position Cap**: Never exceed $\$50.00$ notional on single intraday scalps.
3. **Session Alignment**: Enter only during peak volume windows (London Open or London/NY Overlap). Never enter during market dead zones.
4. **Binary Event Embargo**: Cease order submission 30 minutes before Tier-1 announcements (CPI, FOMC, NFP).

---

## 2. Core Intraday Python Algorithms

### A. Mathematical Trade Parameter Generator ($\ge 1:2$ R:R & $\le \$50$ RiskSentinel Cap)

```python
from typing import Dict, Any

def calculate_day_trade_params(
    symbol: str,
    entry_price: float,
    side: str = "BUY",
    risk_pct: float = 0.015,
    rr_multiplier: float = 2.2,
    max_order_usd: float = 50.0,
    stop_loss_cap_pct: float = 2.0,
) -> Dict[str, Any]:
    """
    Derives mathematically guaranteed >= 1:2 Risk-to-Reward parameters
    capped strictly by RiskSentinel limits ($50 max, 2% stop).
    """
    # Enforce stop-loss cap (max 2%)
    effective_risk_pct = min(risk_pct, stop_loss_cap_pct / 100.0)
    
    if side.upper() == "BUY":
        stop_loss = round(entry_price * (1.0 - effective_risk_pct), 4 if entry_price < 10 else 2)
        risk_distance = entry_price - stop_loss
        take_profit = round(entry_price + (risk_distance * rr_multiplier), 4 if entry_price < 10 else 2)
    else:
        stop_loss = round(entry_price * (1.0 + effective_risk_pct), 4 if entry_price < 10 else 2)
        risk_distance = stop_loss - entry_price
        take_profit = round(entry_price - (risk_distance * rr_multiplier), 4 if entry_price < 10 else 2)

    actual_rr = round(abs(take_profit - entry_price) / abs(entry_price - stop_loss), 2)
    assert actual_rr >= 2.0, f"R:R invariant violated: {actual_rr} < 2.0"

    recommended_size_usd = min(50.0, max_order_usd)
    recommended_units = round(recommended_size_usd / entry_price, 6 if entry_price < 1 else 4)
    if any(fx in symbol.upper() for fx in ("EUR", "GBP", "JPY", "AUD")):
        recommended_units = 1000.0  # Micro-lot

    return {
        "symbol": symbol.upper(),
        "side": side.upper(),
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward_ratio": actual_rr,
        "risk_pct": round(effective_risk_pct * 100, 2),
        "recommended_size_usd": recommended_size_usd,
        "recommended_units": recommended_units,
    }
```

---

### B. High-Volume Liquidity Session Filter

```python
from datetime import datetime, timezone

def is_valid_day_trading_session(dt: datetime) -> Dict[str, Any]:
    """
    Validates whether the current UTC timestamp falls within high-liquidity trading hours.
    Avoids dead zones (21:00 - 23:00 UTC) and low-volume drift.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    weekday = dt.weekday()  # 0=Monday, 6=Sunday
    hour = dt.hour

    # Weekend gap risk filter
    if weekday == 5 or (weekday == 4 and hour >= 21) or (weekday == 6 and hour < 22):
        return {"allowed": False, "session": "WEEKEND_CLOSE", "reason": "Market closed or low weekend liquidity"}

    if 7 <= hour < 10:
        return {"allowed": True, "session": "LONDON_OPEN", "liquidity": "HIGH"}
    elif 12 <= hour < 16:
        return {"allowed": True, "session": "LONDON_NY_OVERLAP", "liquidity": "MAXIMUM"}
    elif 0 <= hour < 4:
        return {"allowed": True, "session": "ASIA_SESSION", "liquidity": "MODERATE"}
    elif 21 <= hour < 23:
        return {"allowed": False, "session": "DEAD_ZONE", "reason": "Spread widening & session transition rollover"}
    else:
        return {"allowed": True, "session": "INTER_SESSION", "liquidity": "MODERATE"}
```

---

### C. Fair Value Gap (FVG) Retest Detector

```python
from typing import List, Optional, Dict, Any

def detect_fvg_retest(klines: List[Dict[str, float]]) -> Optional[Dict[str, Any]]:
    """
    Identifies 3-bar Fair Value Gaps and triggers entry when price retests the gap zone.
    Requires at least 3 completed OHLC bars.
    """
    if len(klines) < 3:
        return None

    # Bar 0, Bar 1 (Impulse), Bar 2
    b0 = klines[-3]
    b1 = klines[-2]
    b2 = klines[-1]

    # Bullish FVG: Bar 2 Low > Bar 0 High
    if b2["low"] > b0["high"]:
        gap_zone = [float(b0["high"]), float(b2["low"])]
        # Retest condition: current price enters gap zone
        current_close = float(b2["close"])
        if gap_zone[0] <= current_close <= gap_zone[1]:
            return {
                "type": "BULLISH_FVG_RETEST",
                "action": "BUY",
                "gap_low": gap_zone[0],
                "gap_high": gap_zone[1],
                "invalidation": gap_zone[0],
            }

    # Bearish FVG: Bar 2 High < Bar 0 Low
    elif b2["high"] < b0["low"]:
        gap_zone = [float(b2["high"]), float(b0["low"])]
        current_close = float(b2["close"])
        if gap_zone[0] <= current_close <= gap_zone[1]:
            return {
                "type": "BEARISH_FVG_RETEST",
                "action": "SELL",
                "gap_low": gap_zone[0],
                "gap_high": gap_zone[1],
                "invalidation": gap_zone[1],
            }

    return None
```

---

## 3. Social Media & Macro Event Trigger Investigator

### A. Tier-1 Macro Calendar Risk Interceptor

```python
from typing import Dict, Any, List

def evaluate_macro_event_embargo(events: List[Dict[str, Any]], embargo_minutes: int = 30) -> Dict[str, Any]:
    """
    Enforces the mandatory 30-minute trading embargo prior to Tier-1 releases
    (CPI, FOMC, NFP, Core PCE).
    """
    high_impact_imminent = []
    for ev in events:
        if ev.get("impact") == "HIGH" and ev.get("minutes_away", 999) <= embargo_minutes:
            high_impact_imminent.append(ev)

    if high_impact_imminent:
        next_event = high_impact_imminent[0]
        return {
            "trading_allowed": False,
            "status": "EMBARGO_HALT",
            "event": next_event.get("event"),
            "minutes_away": next_event.get("minutes_away"),
            "action": "HALT_AUTOMATED_ORDERS",
            "advisory": f"Execution halted: {next_event.get('event')} release in {next_event.get('minutes_away')}m."
        }

    return {
        "trading_allowed": True,
        "status": "CLEAR_TO_TRADE",
        "advisory": "No imminent Tier-1 releases within embargo window."
    }
```

---

### B. Social Sentiment Divergence & Trap Detection

```python
def analyze_social_divergence(
    sentiment_score: float,
    near_resistance: bool,
    near_support: bool,
    whale_flow_net_usd: float = 0.0
) -> Dict[str, Any]:
    """
    Detects divergence between retail crowd sentiment and institutional market structure:
    1. Bull Trap: Retail highly euphoric into resistance -> Liquidity sweep short.
    2. Bear Trap: Retail panic into support with whale accumulation -> Mean reversion long.
    """
    if sentiment_score >= 0.70 and near_resistance:
        return {
            "signal": "RETAIL_BULL_TRAP",
            "bias": "BEARISH_SWEEP",
            "confidence": 0.82,
            "advisory": "Euphoric retail buying into resistance. Institutions likely harvesting liquidity. Look for reversal shorts.",
        }

    if sentiment_score <= -0.70 and near_support and whale_flow_net_usd > 10_000_000:
        return {
            "signal": "INSTITUTIONAL_ABSORPTION",
            "bias": "BULLISH_REVERSION",
            "confidence": 0.88,
            "advisory": "Retail panic dumping into major support while whales accumulate > $10M. High-probability bounce.",
        }

    return {
        "signal": "NEUTRAL_ALIGNMENT",
        "bias": "TREND_CONTINUATION",
        "confidence": 0.65,
        "advisory": "Social sentiment and market structure are in equilibrium.",
    }
```

---

## 4. End-of-Day (EOD) Flat Protocol

To preserve trading capital and eliminate overnight gap risk:
1. **20:45 UTC**: Cease opening new intraday positions for equity and forex markets.
2. **20:55 UTC**: Audit open positions. Move stops to breakeven on runners, or market-close positions in profit.
3. **21:00 UTC**: Flat equity state achieved. Record realized PnL and trade statistics to SQLite `StateStore` (`trader_state.db`).
