from flask import Blueprint, jsonify, request
from core.event_bus import get_event_bus, CH_SIGNALS, CH_ORDERS, CH_MARKET, CH_TELEMETRY

pubsub_blueprint = Blueprint("pubsub_api", __name__)


@pubsub_blueprint.get("/api/pubsub/status")
def pubsub_status():
    bus = get_event_bus()
    return jsonify(bus.get_status())


@pubsub_blueprint.get("/api/pubsub/events")
def pubsub_events():
    channel = request.args.get("channel")
    limit = int(request.args.get("limit", 50))
    bus = get_event_bus()
    events = bus.get_recent_events(channel=channel, limit=limit)
    return jsonify({
        "channel": channel or "all",
        "count": len(events),
        "events": events,
    })


@pubsub_blueprint.post("/api/pubsub/publish")
def pubsub_publish():
    payload = request.get_json(silent=True) or {}
    channel = payload.get("channel", CH_SIGNALS)
    message = payload.get("message", {})

    bus = get_event_bus()
    success = bus.publish(channel, message)
    return jsonify({
        "status": "success" if success else "failed",
        "channel": channel,
        "backend": bus.backend,
    })
