"""
Trading 212 Invest & Stocks and Shares ISA REST API.

Exposes:
- GET  /api/t212/instruments: Filtered screener across 14,200+ traditional investments.
- GET  /api/t212/etf/breakdown: Deep dive into ETF Top 10 Holdings Pie, Sector Donut, and Historical Performance.
- GET  /api/t212/pies: Retrieves custom investment pies and target allocations.
- POST /api/t212/pies: Creates or updates a custom pie on Trading 212.
"""

from typing import Any, Dict
from flask import Blueprint, jsonify, request

from brokers.t212_adapter import Trading212Broker
from quant_trading.etf_analyzer import get_etf_profile
from quant_trading.t212_instruments import t212_catalog

t212_blueprint = Blueprint("t212_api", __name__)


@t212_blueprint.get("/api/t212/instruments")
def list_t212_instruments():
    q = request.args.get("q", "").strip()
    pillar = request.args.get("pillar", "ALL").strip()
    etf_type = request.args.get("etf_type", "ALL").strip()
    dividend_only = request.args.get("dividend_only", "false").lower() in ("true", "1")
    native_only = request.args.get("native_only", "false").lower() in ("true", "1")
    limit = max(1, min(int(request.args.get("limit", 50)), 500))
    offset = max(0, int(request.args.get("offset", 0)))
    force_refresh = request.args.get("force_refresh", "false").lower() in ("true", "1")

    if force_refresh:
        try:
            broker = Trading212Broker()
            live_items = broker.fetch_instruments(force_refresh=True)
            if live_items and len(live_items) > 0:
                t212_catalog.save_cache(live_items)
        except Exception:
            pass

    results, total = t212_catalog.search(
        query=q,
        pillar=pillar,
        etf_type=etf_type,
        dividend_only=dividend_only,
        native_only=native_only,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "status": "success",
        "results": [inst.to_dict() for inst in results],
        "total": total,
        "offset": offset,
        "limit": limit,
        "stats": t212_catalog.get_summary_stats(),
    })


@t212_blueprint.get("/api/t212/etf/breakdown")
def etf_breakdown():
    ticker = request.args.get("ticker") or request.args.get("symbol") or "VUSA.L"
    try:
        profile = get_etf_profile(ticker)
        return jsonify({
            "status": "success",
            "profile": profile.to_dict(),
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 400


@t212_blueprint.get("/api/t212/pies")
def get_user_pies():
    try:
        broker = Trading212Broker()
        pies = broker.fetch_pies()
        return jsonify({
            "status": "success",
            "count": len(pies),
            "pies": pies,
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "pies": []}), 500


@t212_blueprint.post("/api/t212/pies")
def create_user_pie():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "My Quantitative Pie")).strip()
    shares = payload.get("instrumentShares", {})
    action = str(payload.get("dividendCashAction", "REINVEST")).strip()
    goal = float(payload.get("goal", 1000.0))

    if not shares:
        return jsonify({"status": "error", "error": "instrumentShares dictionary is required"}), 400

    try:
        broker = Trading212Broker()
        res = broker.create_pie(name=name, instrument_shares=shares, dividend_action=action, goal=goal)
        return jsonify({"status": "success", "result": res})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
