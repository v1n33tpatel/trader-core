import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Union


def detect_cme_gaps(bars: Union[pd.DataFrame, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Identifies unfilled CME weekend gaps between Friday close and Sunday open.
    Accepts a DataFrame with DatetimeIndex or a list of candle dicts containing 'time'/'timestamp'.
    """
    if isinstance(bars, list):
        if not bars:
            return []
        times = [b.get("time") or b.get("timestamp") for b in bars]
        df = pd.DataFrame(bars, index=pd.to_datetime(times, utc=True))
    else:
        df = bars.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True)

    if len(df) < 2:
        return []

    gaps = []
    for i in range(1, len(df)):
        prev_bar = df.iloc[i - 1]
        curr_bar = df.iloc[i]

        # Check for weekend jump: Friday (4) -> Sunday (6) or Monday (0)
        p_day = prev_bar.name.weekday()
        c_day = curr_bar.name.weekday()

        if p_day == 4 and (c_day in (6, 0)):
            p_high = float(prev_bar["high"])
            p_low = float(prev_bar["low"])
            c_high = float(curr_bar["high"])
            c_low = float(curr_bar["low"])

            # Bullish Gap: Price opened above Friday high
            if c_low > p_high:
                gaps.append({
                    "type": "bullish_gap",
                    "direction": "UP",
                    "gap_low": p_high,
                    "gap_high": c_low,
                    "gap_size": round(c_low - p_high, 4),
                    "timestamp": curr_bar.name.isoformat(),
                    "filled": False,
                })
            # Bearish Gap: Price opened below Friday low
            elif c_high < p_low:
                gaps.append({
                    "type": "bearish_gap",
                    "direction": "DOWN",
                    "gap_low": c_high,
                    "gap_high": p_low,
                    "gap_size": round(p_low - c_high, 4),
                    "timestamp": curr_bar.name.isoformat(),
                    "filled": False,
                })

    return gaps


def calculate_volume_profile(
    bars: Union[pd.DataFrame, List[Dict[str, Any]]],
    num_bins: int = 50,
) -> Dict[str, Any]:
    """
    Computes Point of Control (POC), Value Area High (VAH), Value Area Low (VAL),
    and identifies Low Volume Nodes (LVNs).
    """
    if isinstance(bars, list):
        if not bars:
            return {"poc": 0.0, "vah": 0.0, "val": 0.0, "bins": []}
        df = pd.DataFrame(bars)
    else:
        df = bars

    if df.empty or "high" not in df or "low" not in df or "volume" not in df:
        return {"poc": 0.0, "vah": 0.0, "val": 0.0, "bins": []}

    highs = df["high"].astype(float).to_numpy()
    lows = df["low"].astype(float).to_numpy()
    volumes = df["volume"].astype(float).to_numpy()

    price_min = float(np.min(lows))
    price_max = float(np.max(highs))

    if price_min >= price_max or not np.isfinite(price_min) or not np.isfinite(price_max):
        p = float(df["close"].iloc[-1]) if "close" in df else 0.0
        return {"poc": p, "vah": p, "val": p, "bins": []}

    bins = np.linspace(price_min, price_max, num_bins + 1)
    bin_volumes = np.zeros(num_bins, dtype=float)

    for i in range(len(df)):
        h = highs[i]
        l = lows[i]
        v = volumes[i]
        idx_low = int(np.clip(np.digitize(l, bins) - 1, 0, num_bins - 1))
        idx_high = int(np.clip(np.digitize(h, bins) - 1, 0, num_bins - 1))
        span = max(1, idx_high - idx_low + 1)
        bin_volumes[idx_low:idx_high + 1] += v / span

    poc_idx = int(np.argmax(bin_volumes))
    poc_price = float((bins[poc_idx] + bins[poc_idx + 1]) / 2.0)

    total_volume = float(np.sum(bin_volumes))
    target_va_volume = total_volume * 0.70

    current_va_volume = float(bin_volumes[poc_idx])
    low_idx, high_idx = poc_idx, poc_idx

    while current_va_volume < target_va_volume and (low_idx > 0 or high_idx < num_bins - 1):
        vol_below = float(bin_volumes[low_idx - 1]) if low_idx > 0 else 0.0
        vol_above = float(bin_volumes[high_idx + 1]) if high_idx < num_bins - 1 else 0.0

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

    # Find Low Volume Nodes (nodes with < 30% of average bin volume)
    mean_vol = np.mean(bin_volumes)
    lvns = []
    for b_i in range(num_bins):
        if bin_volumes[b_i] < (mean_vol * 0.30):
            lvns.append(round(float((bins[b_i] + bins[b_i + 1]) / 2.0), 2))

    return {
        "poc": round(poc_price, 2),
        "vah": round(vah, 2),
        "val": round(val, 2),
        "price_min": round(price_min, 2),
        "price_max": round(price_max, 2),
        "low_volume_nodes": lvns[:5],
    }


def estimate_liquidation_clusters(
    entry_price: float,
    leverage_tiers: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Estimates estimated liquidation cluster prices for standard retail leverage tiers.
    """
    tiers = leverage_tiers or [10, 25, 50, 100]
    clusters: Dict[str, Any] = {"long_liquidations": [], "short_liquidations": []}

    if entry_price <= 0:
        return clusters

    for lev in tiers:
        # Maintenance margin approx: 0.5% (0.005)
        long_liq = entry_price * (1.0 - (1.0 / lev) + 0.005)
        short_liq = entry_price * (1.0 + (1.0 / lev) - 0.005)
        clusters["long_liquidations"].append({
            "leverage": f"{lev}x",
            "price": round(float(long_liq), 2),
        })
        clusters["short_liquidations"].append({
            "leverage": f"{lev}x",
            "price": round(float(short_liq), 2),
        })

    return clusters
