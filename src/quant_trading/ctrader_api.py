from flask import Blueprint, jsonify, request
from brokers.ctrader_adapter import CTraderBroker, CTRADER_INSTRUMENTS
from core.state_store import StateStore

ctrader_blueprint = Blueprint("ctrader_api", __name__)

_ctrader_broker = CTraderBroker(is_demo=True)


def get_ctrader_broker() -> CTraderBroker:
    global _ctrader_broker
    store = StateStore()
    demo = store.get_setting("environment", "demo").lower() == "demo"
    if _ctrader_broker.is_demo != demo:
        _ctrader_broker = CTraderBroker(is_demo=demo)
    return _ctrader_broker


@ctrader_blueprint.get("/api/ctrader/portfolio")
def ctrader_portfolio():
    broker = get_ctrader_broker()
    cash, positions = broker.get_portfolio()
    invested = sum(float(p.get("invested", 0.0)) for p in positions)
    ppl = sum(float(p.get("ppl", 0.0)) for p in positions)
    equity = round(cash + invested + ppl, 2)

    return jsonify({
        "cash": round(float(cash), 2),
        "active_positions": len(positions),
        "total_invested": round(invested, 2),
        "unrealized_pnl": round(ppl, 2),
        "total_equity": equity,
        "is_demo": broker.is_demo,
        "is_configured": broker.is_configured(),
        "positions": positions,
    })


@ctrader_blueprint.post("/api/ctrader/order")
def ctrader_order():
    payload = request.get_json(silent=True) or {}
    symbol = str(payload.get("symbol", "EURUSD")).upper()
    side = str(payload.get("side", "BUY")).upper()
    units = float(payload.get("units", 1000.0))
    stop_loss = payload.get("stop_loss")
    take_profit = payload.get("take_profit")

    broker = get_ctrader_broker()
    is_buy = (side == "BUY")

    # RiskSentinel Guardrail check
    store = StateStore()
    max_order_usd = float(store.get_setting("max_order_usd", "50.0"))
    # In Forex, margin is approximately 1% of notional
    margin_required = units * 0.01
    if margin_required > max_order_usd and not broker.is_demo:
        return jsonify({
            "error": f"RiskSentinel rejected order: Margin ${margin_required:.2f} exceeds max order limit ${max_order_usd:.2f}"
        }), 400

    order_res = broker.place_order(symbol, is_buy, units, stop_loss, take_profit)

    # Record into StateStore
    if order_res.get("status") in ("FILLED", "SUBMITTED"):
        store.record_trade(
            position_id=order_res.get("order_id", f"CT-{symbol}"),
            symbol=symbol,
            broker="ctrader",
            side=side,
            units=units,
            price=1.0850 if "EUR" in symbol else 1.2750,
        )

    return jsonify(order_res)


@ctrader_blueprint.get("/api/ctrader/status")
def ctrader_status():
    broker = get_ctrader_broker()
    return jsonify({
        "status": "online" if broker.is_configured() else "unconfigured",
        "demo": broker.is_demo,
        "host": broker.host,
        "account_id": broker.account_id if broker.is_configured() else None,
    })


@ctrader_blueprint.get("/api/search/ctrader")
def search_ctrader():
    q = request.args.get("q", "").strip().upper()
    matches = []
    for sym, meta in CTRADER_INSTRUMENTS.items():
        if not q or q in sym or q in meta.get("base", "") or q in meta.get("quote", ""):
            matches.append({
                "symbol": sym,
                "base": meta["base"],
                "quote": meta["quote"],
                "type": "FOREX" if sym not in ("XAUUSD", "USOIL") else "COMMODITY",
                "digits": meta["digits"],
            })
            if len(matches) >= 10:
                break
    return jsonify(matches)
