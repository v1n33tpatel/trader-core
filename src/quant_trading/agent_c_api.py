from flask import Blueprint, jsonify, request
from feeds.agent_c import AgentCSentinel

agent_c_blueprint = Blueprint("agent_c_api", __name__)


@agent_c_blueprint.get("/api/agent-c/intel")
def get_market_intel():
    symbol = request.args.get("symbol", "ETH").upper()
    agent = AgentCSentinel()
    intel = agent.synthesize_intel(symbol=symbol)
    return jsonify(intel)


@agent_c_blueprint.get("/api/agent-c/social")
def get_social_sentiment():
    symbol = request.args.get("symbol", "ETH").upper()
    agent = AgentCSentinel()
    return jsonify(agent.fetch_social_sentiment(symbol=symbol))


@agent_c_blueprint.get("/api/agent-c/news")
def get_market_news():
    symbol = request.args.get("symbol")
    agent = AgentCSentinel()
    return jsonify({"news": agent.fetch_market_news(symbol=symbol)})


@agent_c_blueprint.get("/api/agent-c/calendar")
def get_economic_calendar():
    agent = AgentCSentinel()
    return jsonify(agent.fetch_economic_calendar())


@agent_c_blueprint.get("/api/agent-c/company")
def get_company_data():
    symbol = request.args.get("symbol", "SPY").upper()
    agent = AgentCSentinel()
    return jsonify(agent.fetch_company_fundamentals(symbol=symbol))


@agent_c_blueprint.post("/api/agent-c/query")
def query_agent_c():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "ETH").upper()
    question = payload.get("question", "")
    agent = AgentCSentinel()
    res = agent.synthesize_intel(symbol=symbol, question=question)
    return jsonify(res)
