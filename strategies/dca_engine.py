"""
Dynamic Regime-Aware DCA Strategy Engine
Handles automated accumulation across Trading 212 (ETFs) and eToro (Crypto).
"""
from typing import Dict, List, Any, Optional

DEFAULT_DCA_CONFIG = {
    "etf": {
        "cash_reserve_floor": 100.0,   # Keep at least £100/€100 liquid
        "batch_budget": 50.0,          # Base capital allocated per cycle
        "baskets": {
            "VUKE.L": {"target_weight": 0.30, "broker": "trading212"},  # FTSE 100 UCITS ETF
            "VHYL.L": {"target_weight": 0.30, "broker": "trading212"},  # All-World High Dividend
            "O":      {"target_weight": 0.20, "broker": "trading212"},  # Realty Income (Monthly)
            "SGLN.L": {"target_weight": 0.20, "broker": "trading212"}   # Physical Gold ETC
        }
    },
    "crypto": {
        "cash_reserve_floor": 50.0,    # USD
        "batch_budget": 50.0,
        "baskets": {
            "ETH": {"target_weight": 0.40, "broker": "etoro", "instrument_id": 100002},
            "SOL": {"target_weight": 0.35, "broker": "etoro", "instrument_id": 100085},
            "BTC": {"target_weight": 0.25, "broker": "etoro", "instrument_id": 100001}
        }
    }
}

class DynamicDCAEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or DEFAULT_DCA_CONFIG

    def calculate_dip_multiplier(self, rsi: Optional[float]) -> float:
        """
        Dynamically scale DCA batch size based on indicator momentum:
        RSI <= 30 (Oversold): Accumulate 1.5x normal size
        RSI 30-45 (Pullback): Accumulate 1.2x normal size
        RSI 45-65 (Neutral):  Standard 1.0x allocation
        RSI >= 70 (Overbought): Reduce to 0.5x or defer allocation
        """
        if rsi is None:
            return 1.0
        if rsi <= 30.0:
            return 1.50
        elif rsi <= 45.0:
            return 1.20
        elif rsi >= 70.0:
            return 0.50
        return 1.0

    def plan_dca_orders(
        self,
        category: str,
        available_cash: float,
        current_holdings: Dict[str, float],
        market_telemetry: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Computes rebalanced DCA order payloads.
        :param category: "etf" or "crypto"
        :param available_cash: Free cash balance from broker
        :param current_holdings: {ticker: current_usd_value}
        :param market_telemetry: {ticker: {"price": float, "rsi": float}}
        """
        basket_rules = self.config.get(category, {})
        if not basket_rules:
            return {"error": f"Unknown category: {category}", "orders": []}

        cash_floor = basket_rules.get("cash_reserve_floor", 50.0)
        base_budget = basket_rules.get("batch_budget", 50.0)

        # 1. Cash Reserve Check
        spendable_cash = available_cash - cash_floor
        if spendable_cash < 10.0:
            return {
                "status": "SKIPPED",
                "reason": f"Free cash ({available_cash:.2f}) below safety reserve floor ({cash_floor:.2f})",
                "orders": []
            }

        # Sizing cap
        allocatable_amount = min(spendable_cash, base_budget)
        orders = []

        total_portfolio_val = sum(current_holdings.values()) + allocatable_amount
        baskets = basket_rules.get("baskets", {})

        for ticker, meta in baskets.items():
            target_weight = meta["target_weight"]
            current_val = current_holdings.get(ticker, 0.0)
            target_val = total_portfolio_val * target_weight
            
            # Allocation needed to approach target weight
            weight_deficit = max(0.0, target_val - current_val)
            
            # Base order allocation
            raw_order_size = allocatable_amount * target_weight

            # Dynamic dip multiplier from RSI
            telemetry = market_telemetry.get(ticker, {})
            rsi = telemetry.get("rsi")
            price = telemetry.get("price", 0.0)
            dip_mult = self.calculate_dip_multiplier(rsi)
            
            adjusted_order_size = round(raw_order_size * dip_mult, 2)
            
            # Ensure order does not exceed remaining spendable cash
            adjusted_order_size = min(adjusted_order_size, spendable_cash)

            if adjusted_order_size >= 1.0 and price > 0:
                shares = round(adjusted_order_size / price, 6)
                orders.append({
                    "ticker": ticker,
                    "broker": meta["broker"],
                    "instrument_id": meta.get("instrument_id"),
                    "amount_fiat": adjusted_order_size,
                    "shares_est": shares,
                    "price_snapshot": price,
                    "rsi": rsi,
                    "dip_mult": dip_mult,
                    "rationale": f"DCA weight target ({target_weight*100:.0f}%) with {dip_mult}x RSI dip boost"
                })

        return {
            "status": "READY",
            "category": category,
            "available_cash": available_cash,
            "total_dca_spend": round(sum(o["amount_fiat"] for o in orders), 2),
            "orders": orders
        }
