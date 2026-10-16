---
name: liquidity-analysis
description: >-
  Use this skill whenever researching, detecting, or trading CME gaps, Candle Market Imbalances (CMI/FVG),
  Volume Profile nodes (POC, VAH, VAL), or leveraged liquidation clusters across crypto and forex markets.
---

# CME/CMI Gaps & Liquidity Cluster Analysis Manual

Techniques, data formulas, and algorithms for finding and exploiting institutional liquidity pockets.

---

## 1. CME Gap Detection Algorithm

Detects price voids between Friday close (21:00 UTC) and Sunday open (22:00 UTC) on CME futures:

```python
import pandas as pd

def detect_cme_gaps(cme_bars: pd.DataFrame) -> list[dict]:
    """
    Identifies unfilled CME weekend gaps from daily or 4H CME futures bars.
    cme_bars must have a DatetimeIndex in UTC.
    """
    gaps = []
    for i in range(1, len(cme_bars)):
        prev_bar = cme_bars.iloc[i - 1]
        curr_bar = cme_bars.iloc[i]
        
        # Check if weekend gap occurred (Friday close -> Sunday open)
        if prev_bar.name.weekday() == 4 and curr_bar.name.weekday() == 6:
            # Bullish Gap (Price opened above Friday high)
            if curr_bar["low"] > prev_bar["high"]:
                gaps.append({
                    "type": "bullish_gap",
                    "gap_low": float(prev_bar["high"]),
                    "gap_high": float(curr_bar["low"]),
                    "date": curr_bar.name.isoformat(),
                    "filled": False
                })
            # Bearish Gap (Price opened below Friday low)
            elif curr_bar["high"] < prev_bar["low"]:
                gaps.append({
                    "type": "bearish_gap",
                    "gap_low": float(curr_bar["high"]),
                    "gap_high": float(prev_bar["low"]),
                    "date": curr_bar.name.isoformat(),
                    "filled": False
                })
    return gaps
```

---

## 2. Volume Profile & Market Profile (POC, VAH, VAL)

Calculates traded volume distribution across discrete price buckets:

```python
import numpy as np
import pandas as pd

def calculate_volume_profile(bars: pd.DataFrame, num_bins: int = 50) -> dict:
    """
    Computes Point of Control (POC), Value Area High (VAH), and Value Area Low (VAL).
    bars DataFrame requires 'high', 'low', 'close', 'volume'.
    """
    price_min = bars["low"].min()
    price_max = bars["high"].max()
    bins = np.linspace(price_min, price_max, num_bins + 1)
    bin_volumes = np.zeros(num_bins)

    for _, row in bars.iterrows():
        # Distribute bar volume across price bins it spanned
        idx_low = np.clip(np.digitize(row["low"], bins) - 1, 0, num_bins - 1)
        idx_high = np.clip(np.digitize(row["high"], bins) - 1, 0, num_bins - 1)
        span = max(1, idx_high - idx_low + 1)
        bin_volumes[idx_low:idx_high + 1] += row["volume"] / span

    poc_idx = int(np.argmax(bin_volumes))
    poc_price = float((bins[poc_idx] + bins[poc_idx + 1]) / 2)

    # 70% Value Area calculation
    total_volume = bin_volumes.sum()
    target_va_volume = total_volume * 0.70
    
    current_va_volume = bin_volumes[poc_idx]
    low_idx, high_idx = poc_idx, poc_idx
    
    while current_va_volume < target_va_volume and (low_idx > 0 or high_idx < num_bins - 1):
        vol_below = bin_volumes[low_idx - 1] if low_idx > 0 else 0
        vol_above = bin_volumes[high_idx + 1] if high_idx < num_bins - 1 else 0
        
        if vol_above >= vol_below and high_idx < num_bins - 1:
            high_idx += 1
            current_va_volume += vol_above
        elif low_idx > 0:
            low_idx -= 1
            current_va_volume += vol_below
        else:
            break

    val = float(bins[low_idx])
    vah = float(bins[high_idx + 1])

    return {
        "poc": poc_price,
        "vah": vah,
        "val": val,
        "price_min": float(price_min),
        "price_max": float(price_max),
    }
```

---

## 3. Liquidation Cluster Price Modeling

Estimates where liquidation clusters accumulate for standard retail leverage tiers ($10x, 25x, 50x, 100x$):

```python
def estimate_liquidation_clusters(entry_price: float, leverage_tiers: list[int] = None) -> dict:
    tiers = leverage_tiers or [10, 25, 50, 100]
    clusters = {"long_liquidations": [], "short_liquidations": []}

    for lev in tiers:
        # Maintenance margin approx: 0.5% (0.005)
        # Long liquidation: P_liq = Entry * (1 - 1/Lev + MaintMargin)
        long_liq = entry_price * (1.0 - (1.0 / lev) + 0.005)
        short_liq = entry_price * (1.0 + (1.0 / lev) - 0.005)
        clusters["long_liquidations"].append({"leverage": f"{lev}x", "price": round(long_liq, 2)})
        clusters["short_liquidations"].append({"leverage": f"{lev}x", "price": round(short_liq, 2)})

    return clusters
```

---

## 4. The Triple-Confluence Strategy (Execution Checklist)

1. **Identify Anchor Gap**: Mark an unfilled CME Gap or 4H Candle Market Imbalance (CMI/FVG).
2. **Locate Liquidity Target**: Check if a cluster of Equal Highs/Lows (EQH/EQL) or dense liquidation leverage rests inside the gap zone.
3. **Gauge Structural Volume**: Confirm whether the gap corresponds to a Low Volume Node (LVN) where price can accelerate freely into the Point of Control (POC).
4. **Execution Rule**: Wait for the liquidity pool to be swept with a pinbar rejection on lower timeframe (15m/1h) before executing a counter-trend reversal trade, targeting the opposite Value Area boundary.
