from typing import List, Dict, Any, Optional, Tuple
from models.events import BarEvent, SignalEvent, SignalSide
from strategies.base import BaseStrategy, BaseEventStrategy, Bar, StrategySignal


class PriceActionStrategy(BaseStrategy, BaseEventStrategy):
    """
    Institutional Price Action (PA) Strategy.
    Identifies:
    1. Swing Highs & Swing Lows (Structural Pivots)
    2. Liquidity Sweeps & Rejection Pinbars (False Breakouts / Wick Rejections)
    3. Market Structure Shifts / Break of Structure (BOS)
    """

    def __init__(self, name: str = "PriceActionStrategy", params: Optional[Dict[str, Any]] = None, **kwargs):
        default_params = {
            "pivot_window": 5,
            "min_wick_ratio": 0.50,
            "risk_reward_ratio": 2.0,
            "max_sl_pct": 3.5,
            "min_sl_pct": 0.5,
        }
        if params:
            default_params.update(params)
        if kwargs:
            default_params.update(kwargs)
        self.params = default_params
        self.pivot_window = default_params["pivot_window"]
        BaseStrategy.__init__(self, name=name, params=default_params)
        BaseEventStrategy.__init__(self, name=name, params=default_params)

    @staticmethod
    def _bar_val(bar: Any, key: str) -> float:
        if isinstance(bar, dict):
            return float(bar.get(key, 0.0))
        return float(getattr(bar, key, 0.0))

    def detect_swing_pivots(self, bars: List[Any], window: Optional[int] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        w = window or self.params.get("pivot_window", 5)
        n = len(bars)
        if n < (w * 2 + 1):
            w = max(2, n // 4)
        if n < (w * 2 + 1):
            return [], []

        swing_highs = []
        swing_lows = []

        for i in range(w, n - w):
            h_curr = self._bar_val(bars[i], "high")
            l_curr = self._bar_val(bars[i], "low")

            is_high = all(h_curr >= self._bar_val(bars[j], "high") for j in range(i - w, i + w + 1) if j != i)
            is_low = all(l_curr <= self._bar_val(bars[j], "low") for j in range(i - w, i + w + 1) if j != i)

            if is_high:
                swing_highs.append({"index": i, "price": h_curr})
            if is_low:
                swing_lows.append({"index": i, "price": l_curr})

        return swing_highs, swing_lows

    def analyze_market_structure(self, bars: List[Any]) -> Dict[str, Any]:
        """Extract comprehensive Price Action telemetry for AI reasoning and execution."""
        if len(bars) < 5:
            return {
                "structure": "INSUFFICIENT_BARS",
                "trend": "INSUFFICIENT_BARS",
                "swing_highs": [],
                "swing_lows": [],
                "recent_pattern": None,
                "bias": "NEUTRAL",
                "sweep_detected": False,
                "bos_detected": False,
            }

        swing_highs, swing_lows = self.detect_swing_pivots(bars)
        curr = bars[-1]
        c_open = self._bar_val(curr, "open")
        c_high = self._bar_val(curr, "high")
        c_low = self._bar_val(curr, "low")
        c_close = self._bar_val(curr, "close")

        total_range = c_high - c_low
        lower_wick = min(c_open, c_close) - c_low
        upper_wick = c_high - max(c_open, c_close)
        lower_wick_ratio = (lower_wick / total_range) if total_range > 0 else 0.0
        upper_wick_ratio = (upper_wick / total_range) if total_range > 0 else 0.0

        last_swing_high = swing_highs[-1]["price"] if swing_highs else None
        last_swing_low = swing_lows[-1]["price"] if swing_lows else None

        min_wick = self.params.get("min_wick_ratio", 0.50)
        pattern = None
        bias = "NEUTRAL"
        signal_type = "HOLD"
        sl = None
        tp = None
        confidence = 0.50
        sweep_detected = False
        sweep_type = None
        sweep_level = None
        bos_detected = False
        bos_type = None
        bos_level = None

        # 1. Check Bullish Liquidity Sweep & Pinbar Rejection
        if last_swing_low is not None and c_low < last_swing_low and c_close > last_swing_low:
            if lower_wick_ratio >= min_wick:
                pattern = "BULLISH_LIQUIDITY_SWEEP_PINBAR"
                bias = "BULLISH"
                signal_type = "BUY"
                confidence = 0.88
                sweep_detected = True
                sweep_type = "bullish"
                sweep_level = last_swing_low
                sl = round(c_low * 0.998, 4)
                risk = max(c_close - sl, c_close * 0.005)
                tp = round(c_close + (risk * self.params.get("risk_reward_ratio", 2.0)), 4)
        # 2. Check Bearish Liquidity Sweep & Pinbar Rejection
        elif last_swing_high is not None and c_high > last_swing_high and c_close < last_swing_high:
            if upper_wick_ratio >= min_wick:
                pattern = "BEARISH_LIQUIDITY_SWEEP_PINBAR"
                bias = "BEARISH"
                signal_type = "SELL"
                confidence = 0.88
                sweep_detected = True
                sweep_type = "bearish"
                sweep_level = last_swing_high
                sl = round(c_high * 1.002, 4)
                risk = max(sl - c_close, c_close * 0.005)
                tp = round(c_close - (risk * self.params.get("risk_reward_ratio", 2.0)), 4)
        # 3. Check Bullish Break of Structure (BOS)
        elif last_swing_high is not None and c_close > last_swing_high:
            prev = bars[-2]
            if self._bar_val(prev, "close") <= last_swing_high:
                pattern = "BULLISH_BREAK_OF_STRUCTURE"
                bias = "BULLISH"
                signal_type = "BUY"
                confidence = 0.82
                bos_detected = True
                bos_type = "bullish"
                bos_level = last_swing_high
                sl = round(last_swing_high * (1.0 - (self.params.get("min_sl_pct", 1.0) / 100.0)), 4)
                risk = max(c_close - sl, c_close * 0.005)
                tp = round(c_close + (risk * self.params.get("risk_reward_ratio", 2.0)), 4)
        # 4. Check Bearish Break of Structure (BOS)
        elif last_swing_low is not None and c_close < last_swing_low:
            prev = bars[-2]
            if self._bar_val(prev, "close") >= last_swing_low:
                pattern = "BEARISH_BREAK_OF_STRUCTURE"
                bias = "BEARISH"
                signal_type = "SELL"
                confidence = 0.82
                bos_detected = True
                bos_type = "bearish"
                bos_level = last_swing_low
                sl = round(last_swing_low * (1.0 + (self.params.get("min_sl_pct", 1.0) / 100.0)), 4)
                risk = max(sl - c_close, c_close * 0.005)
                tp = round(c_close - (risk * self.params.get("risk_reward_ratio", 2.0)), 4)
        # 5. General Rejection Hammer/Shooting Star (Independent of prior swing level)
        elif lower_wick_ratio >= 0.60:
            pattern = "BULLISH_REJECTION_HAMMER"
            bias = "BULLISH_LEAN"
        elif upper_wick_ratio >= 0.60:
            pattern = "BEARISH_REJECTION_SHOOTING_STAR"
            bias = "BEARISH_LEAN"

        # Determine overall trend structure
        trend = "RANGING"
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            if swing_highs[-1]["price"] > swing_highs[-2]["price"] and swing_lows[-1]["price"] > swing_lows[-2]["price"]:
                trend = "UPTREND_HIGHER_HIGHS_HIGHER_LOWS"
            elif swing_highs[-1]["price"] < swing_highs[-2]["price"] and swing_lows[-1]["price"] < swing_lows[-2]["price"]:
                trend = "DOWNTREND_LOWER_HIGHS_LOWER_LOWS"

        return {
            "structure": trend,
            "trend": trend,
            "last_swing_high": last_swing_high,
            "last_swing_low": last_swing_low,
            "swing_high": last_swing_high,
            "swing_low": last_swing_low,
            "swing_highs_count": len(swing_highs),
            "swing_lows_count": len(swing_lows),
            "lower_wick_ratio": round(lower_wick_ratio, 2),
            "upper_wick_ratio": round(upper_wick_ratio, 2),
            "recent_pattern": pattern,
            "bias": bias,
            "signal_type": signal_type,
            "confidence": confidence,
            "suggested_sl": sl,
            "suggested_tp": tp,
            "current_price": c_close,
            "sweep_detected": sweep_detected,
            "sweep_type": sweep_type,
            "sweep_level": sweep_level,
            "bos_detected": bos_detected,
            "bos_type": bos_type,
            "bos_level": bos_level,
        }

    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        analysis = self.analyze_market_structure(bars)
        signal_type = analysis["signal_type"]
        pattern = analysis.get("recent_pattern") or "Consolidation"

        if signal_type == "BUY":
            return StrategySignal(
                symbol=symbol,
                action="BUY",
                confidence=analysis["confidence"],
                reason=f"Price Action: {pattern} detected (Trend: {analysis['structure']})",
                suggested_sl=analysis["suggested_sl"],
                suggested_tp=analysis["suggested_tp"],
                metadata=analysis,
            )
        elif signal_type == "SELL":
            # If we hold a position, signal an EXIT; otherwise SELL / SHORT
            has_pos = any(p.get("symbol") == symbol or p.get("ticker") == symbol for p in current_positions)
            action = "EXIT" if has_pos else "HOLD"
            return StrategySignal(
                symbol=symbol,
                action=action,
                confidence=analysis["confidence"],
                reason=f"Price Action: {pattern} detected (Trend: {analysis['structure']})",
                suggested_sl=analysis["suggested_sl"],
                suggested_tp=analysis["suggested_tp"],
                metadata=analysis,
            )

        return StrategySignal(
            symbol=symbol,
            action="HOLD",
            confidence=0.50,
            reason=f"Price Action: {analysis['structure']}, no actionable sweep or break of structure",
            metadata=analysis,
        )

    def on_bar(self, bar: Any, history: List[Any]) -> Optional[SignalEvent]:
        if len(history) < 5:
            return None

        analysis = self.analyze_market_structure(history)
        action = analysis.get("signal_type")
        symbol = getattr(bar, "symbol", analysis.get("symbol", "UNKNOWN"))

        if action == "BUY":
            return SignalEvent(
                strategy_id=self.name,
                symbol=symbol,
                side=SignalSide.BUY,
                confidence=analysis["confidence"],
                stop_loss=analysis["suggested_sl"],
                take_profit=analysis["suggested_tp"],
                metadata=analysis,
            )
        elif action == "SELL":
            return SignalEvent(
                strategy_id=self.name,
                symbol=symbol,
                side=SignalSide.SELL,
                confidence=analysis["confidence"],
                stop_loss=analysis["suggested_sl"],
                take_profit=analysis["suggested_tp"],
                metadata=analysis,
            )

        return None
