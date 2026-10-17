from typing import Dict, Any

STRATEGY_CATALOG = {
    "crypto": {
        "dynamic_dca": {
            "name": "Dynamic Regime-Aware DCA",
            "description": "Accumulates target basket weights with dynamic scaling on RSI dips.",
            "params": {"batch_budget": 50.0, "cash_floor": 50.0, "rsi_boost_threshold": 35.0}
        },
        "atr_trailing_breakout": {
            "name": "ATR Trailing-Stop Breakout",
            "description": "Enters on 20-period price breakouts with volatility-adjusted trailing stop (2.5x ATR).",
            "params": {
                "lookback_period": 20,
                "atr_period": 14,
                "atr_multiplier": 2.5,
                "min_volume_mult": 1.5,
                "tp_atr_mult": 4.0
            }
        },
        "rsi_reversion": {
            "name": "RSI Mean Reversion (1H)",
            "description": "Buys oversold RSI (<=30) with 3% TP and 2% SL.",
            "params": {"rsi_buy": 30.0, "rsi_sell": 70.0, "tp_pct": 3.0, "sl_pct": 2.0}
        },
        "fvg_breakout": {
            "name": "Fair Value Gap (FVG) Breakout",
            "description": "Trades 3-candle imbalance retests with ATR stops.",
            "params": {"fvg_threshold_pct": 1.5, "tp_pct": 4.5, "sl_pct": 2.0}
        },
        "price_action": {
            "name": "Institutional Price Action & Market Structure",
            "description": "Trades swing pivots, liquidity sweeps, pinbar rejections, and break of structure (BOS).",
            "params": {"pivot_window": 5, "min_wick_ratio": 0.50, "risk_reward_ratio": 2.0, "max_sl_pct": 3.5}
        },
        "macd_risk": {
            "name": "MACD Trend & Volatility Sentinel",
            "description": "Momentum crossover with 200 EMA trend filter, ATR volatility stops, and mandatory 1:2.0+ R:R.",
            "params": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "risk_reward_ratio": 2.2,
                "max_sl_pct": 2.0,
                "sl_atr_mult": 1.5,
                "min_hist_threshold": 0.0002,
                "use_trend_filter": True,
                "trend_period": 200,
            }
        }
    },
    "etf": {
        "sma_macro_regime": {
            "name": "200-Day SMA Macro Filter",
            "description": "Accumulates on dips only when market is above 200 SMA (SPY/VUKE).",
            "params": {"trend_sma": 200, "pullback_rsi": 42.0, "tp_pct": 6.0, "sl_pct": 3.5}
        },
        "dividend_dca": {
            "name": "Target-Weight Dividend DCA",
            "description": "Rebalances capital into distributing ETFs and monthly income stocks.",
            "params": {"min_yield_pct": 3.5, "dca_step_usd": 50.0}
        }
    },
    "forex": {
        "london_ny_overlap": {
            "name": "London/NY Overlap Momentum",
            "description": "Trades EUR/USD and GBP/USD breakouts exclusively between 13:00-17:00 UTC.",
            "params": {"active_hours": "13:00-17:00 UTC", "rsi_trigger": 55.0, "sl_pips": 25}
        },
        "forex_rsi_swing": {
            "name": "1H Multi-Hour RSI Swing",
            "description": "Counter-trend swing entries on extreme currency deviations.",
            "params": {"rsi_oversold": 28.0, "rsi_overbought": 72.0, "tp_pips": 40, "sl_pips": 20}
        }
    }
}

ACTIVE_STRATEGIES = {
    "crypto": "atr_trailing_breakout",
    "etf": "sma_macro_regime",
    "forex": "london_ny_overlap"
}

def get_strategy_info(category: str, key: str) -> Dict[str, Any]:
    return STRATEGY_CATALOG.get(category, {}).get(key, {})
