from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, BaseEventStrategy, Bar, StrategySignal
from models.events import BarEvent, SignalEvent, SignalSide


class MacdRiskStrategy(BaseStrategy, BaseEventStrategy):
    """
    Moving Average Convergence Divergence (MACD) strategy with quantitative risk controls:
    - Fast EMA (12), Slow EMA (26), Signal EMA (9)
    - Anti-whipsaw minimum histogram threshold
    - 200 EMA macro trend filter
    - Volatility-adjusted stop loss (1.5x ATR), strictly capped at <= 2.0%
    - Guaranteed >= 1:2.0 Risk-to-Reward ratio (default 1:2.2)
    - Death-cross and stop/TP exit signals
    """

    def __init__(
        self,
        name: str = "MacdRiskStrategy",
        params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        defaults = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "risk_reward_ratio": 2.2,
            "sl_atr_mult": 1.5,
            "max_sl_pct": 2.0,
            "min_hist_threshold": 0.0002,
            "use_trend_filter": True,
            "trend_period": 200,
        }
        if params:
            defaults.update(params)
        if kwargs:
            defaults.update(kwargs)
        BaseStrategy.__init__(self, name=name, params=defaults)
        BaseEventStrategy.__init__(self, name=name, params=defaults)

    def _compute_indicators(
        self,
        closes: pd.Series,
        highs: pd.Series,
        lows: pd.Series,
    ) -> Dict[str, Any]:
        fast = int(self.params.get("fast_period", 12))
        slow = int(self.params.get("slow_period", 26))
        sig = int(self.params.get("signal_period", 9))

        ema_fast = closes.ewm(span=fast, adjust=False).mean()
        ema_slow = closes.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=sig, adjust=False).mean()
        histogram = macd_line - signal_line

        # ATR(14)
        n = len(closes)
        trs = []
        for i in range(1, n):
            h = float(highs.iloc[i])
            l = float(lows.iloc[i])
            prev_c = float(closes.iloc[i - 1])
            trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
        atr = float(np.mean(trs[-14:])) if trs else float(closes.iloc[-1] * 0.01)

        # Macro trend EMA
        trend_period = int(self.params.get("trend_period", 200))
        use_trend = bool(self.params.get("use_trend_filter", True))
        trend_val = None
        if use_trend and len(closes) >= trend_period:
            trend_val = float(closes.ewm(span=trend_period, adjust=False).mean().iloc[-1])

        return {
            "macd": macd_line,
            "signal": signal_line,
            "hist": histogram,
            "atr": atr,
            "trend_ema": trend_val,
        }

    def evaluate(
        self,
        symbol: str,
        bars: List[Bar],
        current_positions: List[Dict[str, Any]],
        macro_context: Optional[Dict[str, Any]] = None,
    ) -> StrategySignal:
        min_bars = max(
            int(self.params.get("slow_period", 26)) + int(self.params.get("signal_period", 9)),
            35,
        )
        if len(bars) < min_bars:
            return StrategySignal(symbol, "HOLD", 0.0, "Insufficient bars")

        closes = pd.Series([b.close for b in bars], dtype=float)
        highs = pd.Series([b.high for b in bars], dtype=float)
        lows = pd.Series([b.low for b in bars], dtype=float)
        current_price = float(bars[-1].close)

        ind = self._compute_indicators(closes, highs, lows)
        macd = ind["macd"]
        signal = ind["signal"]
        hist = ind["hist"]
        atr = ind["atr"]

        # Check existing positions for stop, TP, or death-cross exits
        for pos in current_positions:
            if pos.get("symbol") == symbol or pos.get("ticker") == symbol:
                sl = pos.get("stop_loss")
                tp = pos.get("take_profit")
                if sl is not None and current_price <= float(sl):
                    return StrategySignal(
                        symbol, "EXIT", 1.0, f"Stop-loss breached at {sl}"
                    )
                if tp is not None and current_price >= float(tp):
                    return StrategySignal(
                        symbol, "EXIT", 1.0, f"Take-profit reached at {tp}"
                    )
                # Death cross exit
                if macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
                    return StrategySignal(
                        symbol, "EXIT", 0.9, "MACD Death Cross exit"
                    )
                return StrategySignal(
                    symbol, "HOLD", 0.7, "Holding position in trend"
                )

        # Cross detection
        is_golden_cross = (
            macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]
        )
        if not is_golden_cross:
            return StrategySignal(symbol, "HOLD", 0.5, "No MACD crossover")

        # Anti-whipsaw threshold
        min_hist = float(self.params.get("min_hist_threshold", 0.0002))
        threshold_val = min_hist * current_price if min_hist < 0.01 else min_hist
        if abs(hist.iloc[-1]) < threshold_val:
            return StrategySignal(
                symbol,
                "HOLD",
                0.4,
                f"Histogram momentum below anti-whipsaw threshold ({abs(hist.iloc[-1]):.4f} < {threshold_val:.4f})",
            )

        # 200 EMA macro filter
        if ind["trend_ema"] is not None and current_price < ind["trend_ema"]:
            return StrategySignal(
                symbol,
                "HOLD",
                0.3,
                f"Price ({current_price:.2f}) below 200 EMA ({ind['trend_ema']:.2f}) macro filter",
            )

        # Dynamic risk sizing & R:R constraint
        atr_mult = float(self.params.get("sl_atr_mult", 1.5))
        raw_sl_dist = atr * atr_mult
        max_sl_pct = float(self.params.get("max_sl_pct", 2.0)) / 100.0
        max_sl_dist = current_price * max_sl_pct
        sl_dist = min(raw_sl_dist, max_sl_dist)
        sl_dist = max(sl_dist, current_price * 0.005)
        sl_dist = min(sl_dist, max_sl_dist)

        suggested_sl = round(
            current_price - sl_dist, 2 if current_price >= 10 else 4
        )
        rr_mult = max(float(self.params.get("risk_reward_ratio", 2.2)), 2.0)
        suggested_tp = round(
            current_price + (sl_dist * rr_mult), 2 if current_price >= 10 else 4
        )

        return StrategySignal(
            symbol=symbol,
            action="BUY",
            confidence=0.88,
            reason=f"MACD Golden Cross: Entry {current_price:.2f}, SL {suggested_sl:.2f}, TP {suggested_tp:.2f} (R:R 1:{rr_mult:.1f})",
            suggested_sl=suggested_sl,
            suggested_tp=suggested_tp,
            metadata={
                "macd": round(float(macd.iloc[-1]), 4),
                "signal": round(float(signal.iloc[-1]), 4),
                "histogram": round(float(hist.iloc[-1]), 4),
                "atr": round(float(atr), 4),
                "risk_reward_ratio": round(rr_mult, 1),
                "stop_loss_pct": round((sl_dist / current_price) * 100.0, 2),
            },
        )

    def on_bar(
        self, bar: BarEvent, history: List[BarEvent]
    ) -> Optional[SignalEvent]:
        min_bars = max(
            int(self.params.get("slow_period", 26)) + int(self.params.get("signal_period", 9)),
            35,
        )
        if len(history) < min_bars:
            return None

        # Build series including current bar if needed
        all_bars = list(history)
        if not all_bars or all_bars[-1].timestamp != bar.timestamp:
            all_bars.append(bar)

        closes = pd.Series([b.close for b in all_bars], dtype=float)
        highs = pd.Series([b.high for b in all_bars], dtype=float)
        lows = pd.Series([b.low for b in all_bars], dtype=float)
        current_price = float(bar.close)

        ind = self._compute_indicators(closes, highs, lows)
        macd = ind["macd"]
        signal = ind["signal"]
        hist = ind["hist"]
        atr = ind["atr"]

        # Golden Cross check
        if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
            min_hist = float(self.params.get("min_hist_threshold", 0.0002))
            threshold_val = (
                min_hist * current_price if min_hist < 0.01 else min_hist
            )
            if abs(hist.iloc[-1]) < threshold_val:
                return None

            if ind["trend_ema"] is not None and current_price < ind["trend_ema"]:
                return None

            atr_mult = float(self.params.get("sl_atr_mult", 1.5))
            raw_sl_dist = atr * atr_mult
            max_sl_pct = float(self.params.get("max_sl_pct", 2.0)) / 100.0
            max_sl_dist = current_price * max_sl_pct
            sl_dist = min(raw_sl_dist, max_sl_dist)
            sl_dist = max(sl_dist, current_price * 0.005)
            sl_dist = min(sl_dist, max_sl_dist)

            suggested_sl = round(
                current_price - sl_dist, 2 if current_price >= 10 else 4
            )
            rr_mult = max(float(self.params.get("risk_reward_ratio", 2.2)), 2.0)
            suggested_tp = round(
                current_price + (sl_dist * rr_mult), 2 if current_price >= 10 else 4
            )

            return SignalEvent(
                strategy_id=self.name,
                symbol=bar.symbol,
                side=SignalSide.BUY,
                confidence=0.88,
                stop_loss=suggested_sl,
                take_profit=suggested_tp,
                metadata={
                    "macd": round(float(macd.iloc[-1]), 4),
                    "signal": round(float(signal.iloc[-1]), 4),
                    "histogram": round(float(hist.iloc[-1]), 4),
                    "atr": round(float(atr), 4),
                    "risk_reward_ratio": round(rr_mult, 1),
                },
            )

        # Death Cross check
        if macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
            return SignalEvent(
                strategy_id=self.name,
                symbol=bar.symbol,
                side=SignalSide.CLOSE,
                confidence=0.80,
                metadata={"reason": "MACD Death Cross exit"},
            )

        return None
