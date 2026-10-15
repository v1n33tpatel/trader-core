from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, Bar, StrategySignal

class RsiMeanReversionStrategy(BaseStrategy):
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1: return 50.0
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(max(-diff, 0.0))
        avg_gain, avg_loss = sum(gains[-period:]) / period, sum(losses[-period:]) / period
        if avg_loss == 0: return 100.0
        return round(100.0 - (100.0 / (1.0 + (avg_gain / avg_loss))), 2)

    def evaluate(self, symbol: str, bars: List[Bar], current_positions: List[Dict[str, Any]], macro_context: Optional[Dict[str, Any]] = None) -> StrategySignal:
        if len(bars) < 20: return StrategySignal(symbol, "HOLD", 0.0, "Insufficient bars")
        closes = [b.close for b in bars]
        current_price = closes[-1]
        rsi = self._calculate_rsi(closes, period=self.params.get("rsi_period", 14))

        for pos in current_positions:
            if pos.get("symbol") == symbol or pos.get("ticker") == symbol:
                open_rate = float(pos.get("open_price", pos.get("openRate", current_price)))
                pnl_pct = ((current_price - open_rate) / open_rate) * 100.0
                if pnl_pct >= self.params.get("tp_pct", 3.0): return StrategySignal(symbol, "EXIT", 1.0, f"TP Hit (+{pnl_pct:.2f}%)")
                if pnl_pct <= -self.params.get("sl_pct", 2.0): return StrategySignal(symbol, "EXIT", 1.0, f"SL Hit ({pnl_pct:.2f}%)")
                if rsi >= self.params.get("rsi_sell", 70.0): return StrategySignal(symbol, "EXIT", 0.85, f"RSI Overbought ({rsi})")

        rsi_buy = self.params.get("rsi_buy", 30.0)
        if rsi <= rsi_buy:
            sl = round(current_price * (1.0 - (self.params.get("sl_pct", 2.0) / 100.0)), 2)
            tp = round(current_price * (1.0 + (self.params.get("tp_pct", 3.0) / 100.0)), 2)
            return StrategySignal(symbol, "BUY", min(1.0, round((rsi_buy - rsi + 10) / 20.0, 2)), f"RSI oversold ({rsi} <= {rsi_buy})", suggested_sl=sl, suggested_tp=tp, metadata={"rsi": rsi})

        return StrategySignal(symbol, "HOLD", 0.5, f"RSI neutral ({rsi})")
