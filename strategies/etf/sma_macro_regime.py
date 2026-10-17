from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, Bar, StrategySignal

class SmaMacroRegimeStrategy(BaseStrategy):
    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        period = min(self.params.get("trend_sma", 200), len(bars) - 1)
        if period < 15: return StrategySignal(symbol, "HOLD", 0.0, "Insufficient bars")
        closes = [b.close for b in bars]
        current_price = closes[-1]
        sma = sum(closes[-period:]) / period
        
        diffs = [closes[i] - closes[i - 1] for i in range(len(closes) - 14, len(closes))]
        gain, loss = sum(max(d, 0.0) for d in diffs) / 14.0, sum(max(-d, 0.0) for d in diffs) / 14.0
        rsi = 100.0 if loss == 0 else 100.0 - (100.0 / (1.0 + (gain / loss)))

        sl_pct = self.params.get("sl_pct", 2.0)
        tp_multiplier = self.params.get("tp_multiplier", 2.2)  # Guaranteed >= 1:2.0 R:R

        val_support = None
        if macro_context and "value_area_low" in macro_context:
            val_support = float(macro_context["value_area_low"])

        # Bullish accumulation condition: Above 200 SMA AND (RSI dip or testing VAL)
        is_val_dip = val_support is not None and current_price <= (val_support * 1.005)
        is_rsi_pullback = rsi <= self.params.get("pullback_rsi", 45.0)

        if current_price >= sma and (is_rsi_pullback or is_val_dip):
            sl = round(current_price * (1.0 - (sl_pct / 100.0)), 2)
            risk_dist = current_price - sl
            tp = round(current_price + (risk_dist * tp_multiplier), 2)
            reason = f"Bullish regime (Price >= 200 SMA {sma:.2f}) + "
            reason += f"VAL support test ({val_support:.2f})" if is_val_dip else f"Pullback RSI ({rsi:.1f})"
            return StrategySignal(
                symbol,
                "BUY",
                0.85,
                f"{reason} (SL: {sl:.2f}, TP: {tp:.2f}, R:R 1:{tp_multiplier})",
                suggested_sl=sl,
                suggested_tp=tp,
                metadata={"sma200": round(sma, 2), "rsi": round(rsi, 1), "val": val_support}
            )

        if current_price < sma:
            return StrategySignal(
                symbol,
                "HOLD",
                0.90,
                f"Defensive posture: Price ({current_price:.2f}) below 200 SMA ({sma:.2f}); accumulation paused",
                metadata={"sma200": round(sma, 2), "regime": "BEARISH_DEFENSIVE"}
            )

        return StrategySignal(
            symbol,
            "HOLD",
            0.50,
            f"Bullish trend healthy above 200 SMA ({sma:.2f}); awaiting VAL or RSI pullback",
            metadata={"sma200": round(sma, 2), "regime": "BULLISH_TRENDING"}
        )
