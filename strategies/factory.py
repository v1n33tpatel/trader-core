from typing import Optional
from strategies.base import BaseStrategy
from strategies.registry import STRATEGY_CATALOG
from strategies.crypto.rsi_reversion import RsiMeanReversionStrategy
from strategies.crypto.fvg_breakout import FvgBreakoutStrategy
from strategies.crypto.atr_trailing_breakout import AtrTrailingBreakoutStrategy
from strategies.crypto.macd_risk import MacdRiskStrategy
from strategies.etf.sma_macro_regime import SmaMacroRegimeStrategy
from strategies.etf.dynamic_dca import DynamicDcaStrategy
from strategies.forex.london_ny_overlap import LondonNyOverlapStrategy
from strategies.forex.carry_rsi_swing import CarryRsiSwingStrategy
from strategies.price_action import PriceActionStrategy

STRATEGY_MAP = {
    "rsi_reversion": RsiMeanReversionStrategy,
    "fvg_breakout": FvgBreakoutStrategy,
    "atr_trailing_breakout": AtrTrailingBreakoutStrategy,
    "macd_risk": MacdRiskStrategy,
    "sma_macro_regime": SmaMacroRegimeStrategy,
    "dividend_dca": DynamicDcaStrategy,
    "dynamic_dca": DynamicDcaStrategy,
    "london_ny_overlap": LondonNyOverlapStrategy,
    "forex_rsi_swing": CarryRsiSwingStrategy,
    "price_action": PriceActionStrategy,
}

def get_strategy_instance(strategy_key: str, category: str = "crypto") -> Optional[BaseStrategy]:
    cls = STRATEGY_MAP.get(strategy_key)
    if not cls: return None
    meta = STRATEGY_CATALOG.get(category, {}).get(strategy_key, {})
    return cls(name=meta.get("name", strategy_key), params=meta.get("params", {}))
