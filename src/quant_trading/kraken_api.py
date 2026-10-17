"""
Kraken Institutional Crypto REST API.

Exposes:
- GET  /api/kraken/pairs: Spot crypto trading pairs filtered by quote currency (USD, EUR, GBP, USDT, BTC).
- GET  /api/kraken/ticker: Real-time 24h ticker summary (volume, high, low, VWAP).
- GET  /api/kraken/ohlc: Candlestick klines for Volume Profile and FVG imbalance detection.
- POST /api/kraken/order: Dual-mode order dispatch (Paper Sandbox simulation vs signed Live Real Capital).
"""

from typing import Any, Dict
from flask import Blueprint, jsonify, request

from brokers.kraken_adapter import KrakenBroker

kraken_blueprint = Blueprint("kraken_api", __name__)


@kraken_blueprint.get("/api/kraken/pairs")
def list_kraken_pairs():
    quote_filter = request.args.get("quote", "USD").strip().upper()
    force = request.args.get("force_refresh", "false").lower() in ("true", "1")

    try:
        broker = KrakenBroker()
        all_pairs = broker.fetch_asset_pairs(force_refresh=force)
        
        filtered = []
        for p, d in all_pairs.items():
            if quote_filter == "ALL" or d.get("quote") == quote_filter:
                filtered.append(d)

        # Sort by popularity / base currency
        filtered.sort(key=lambda x: (x.get("base") not in ("BTC", "ETH", "SOL"), x.get("wsname", "")))

        return jsonify({
            "status": "success",
            "count": len(filtered),
            "quote": quote_filter,
            "quotes_available": ["USD", "EUR", "GBP", "USDT", "BTC"],
            "pairs": filtered,
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "pairs": []}), 500


@kraken_blueprint.get("/api/kraken/ticker")
def get_kraken_ticker():
    pair = request.args.get("pair", "XBTUSD").strip().upper()
    try:
        broker = KrakenBroker()
        ticker_data = broker.fetch_ticker(pair)
        return jsonify({
            "status": "success",
            "pair": pair,
            "ticker": ticker_data,
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 400


@kraken_blueprint.get("/api/kraken/ohlc")
def get_kraken_ohlc():
    pair = request.args.get("pair", "XBTUSD").strip().upper()
    interval = int(request.args.get("interval", 15))
    try:
        broker = KrakenBroker()
        bars = broker.fetch_ohlc(pair, interval=interval)
        return jsonify({
            "status": "success",
            "pair": pair,
            "interval": interval,
            "count": len(bars),
            "bars": bars,
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "bars": []}), 400


@kraken_blueprint.post("/api/kraken/order")
def execute_kraken_order():
    payload = request.get_json(silent=True) or {}
    pair = str(payload.get("pair", "XBTUSD")).strip().upper()
    side = str(payload.get("side", "buy")).strip().lower()
    ordertype = str(payload.get("ordertype", "limit")).strip().lower()
    volume = float(payload.get("volume", 0.001))
    price = float(payload.get("price")) if payload.get("price") is not None else None
    mode = str(payload.get("mode", "DEMO")).strip().upper()

    is_demo = mode != "REAL"
    try:
        broker = KrakenBroker(is_demo=is_demo)
        result = broker.place_order(pair=pair, side=side, ordertype=ordertype, volume=volume, price=price)
        return jsonify({
            "status": "success",
            "mode": mode,
            "result": result,
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
