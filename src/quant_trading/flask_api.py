import csv
import json
import math
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from flask import Blueprint, jsonify, request, send_from_directory

from quant_trading.backtest import BacktestConfig, BacktestEngine
from quant_trading.data import validate_close_prices
from quant_trading.market_data import MarketDataError, MarketSnapshot, get_market_snapshot
from quant_trading.metrics import calculate_metrics
from quant_trading.strategy import TimeSeriesMomentum


research_blueprint = Blueprint("quant_research", __name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_PRICE_ROWS = 50_000
MAX_CHART_POINTS = 300
STATUS_TIMEOUT_SECONDS = 2.5


def _read_env_values(paths: list[str]) -> dict[str, str]:
    for path in paths:
        try:
            with open(path, encoding="utf-8") as env_file:
                values = {
                    key.strip(): value.strip().strip("\"' ")
                    for line in env_file
                    if "=" in line and not line.lstrip().startswith("#")
                    for key, value in [line.split("=", 1)]
                }
        except OSError:
            continue
        if values:
            return values
    return {}


def _probe_api(url: str, headers: dict[str, str] | None = None) -> dict[str, str]:
    try:
        response = requests.get(url, headers=headers, timeout=STATUS_TIMEOUT_SECONDS)
        response.raise_for_status()
        return {"status": "online", "detail": "API responded"}
    except requests.RequestException:
        return {"status": "offline", "detail": "No API response"}


def _t212_status() -> dict[str, str]:
    values = _read_env_values([str(PROJECT_ROOT / ".env")])
    if not values.get("T212_API_KEY") or not values.get("T212_API_SECRET"):
        fallback_values = _read_env_values(["/home/vineet/feed-agent/t212.env"])
        values = {**fallback_values, **values}
    api_key = os.getenv("T212_API_KEY", "").strip().strip("\"' ") or values.get("T212_API_KEY", "")
    api_secret = os.getenv("T212_API_SECRET", "").strip().strip("\"' ") or values.get("T212_API_SECRET", "")
    if not api_key or not api_secret:
        return {"status": "unconfigured", "detail": "Credentials unavailable"}
    import base64

    token = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    return _probe_api(
        "https://demo.trading212.com/api/v0/equity/account/cash",
        {"Authorization": f"Basic {token}"},
    )


def _etoro_status() -> dict[str, str]:
    paths = [
        "/home/vineet/trader-core/etoro.env",
        "/home/vineet/trader-core/config/etoro.env",
        "/home/vineet/feed-agent/etoro.env",
    ]
    values = _read_env_values(paths)
    api_key = values.get("ETORO_API_KEY", "")
    user_key = values.get("ETORO_USER_KEY", "")
    if not api_key or not user_key:
        return {"status": "unconfigured", "detail": "Credentials unavailable"}
    return _probe_api(
        "https://public-api.etoro.com/api/v1/trading/info/demo/portfolio",
        {
            "x-api-key": api_key,
            "x-user-key": user_key,
            "x-request-id": str(uuid.uuid4()),
        },
    )


def _ctrader_status() -> dict[str, str]:
    paths = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "ctrader.env",
        PROJECT_ROOT / "config" / "ctrader.env",
    ]
    values = _read_env_values(paths)
    client_id = values.get("CTRADER_CLIENT_ID", "")
    token = values.get("CTRADER_ACCESS_TOKEN", "")
    if not (client_id and token):
        return {"status": "unconfigured", "detail": "cTrader credentials not provided"}
    return {"status": "online", "detail": "cTrader configured"}


def _api_statuses() -> dict[str, dict[str, str]]:
    checks = {
        "t212": _t212_status,
        "etoro": _etoro_status,
        "ctrader": _ctrader_status,
        "yahoo": lambda: _probe_api("https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1d&interval=1d", {"User-Agent": "MoneyMakingMachineResearch/1.0 (market-data; read-only)"}),
        "binance": lambda: _probe_api("https://api.binance.com/api/v3/ping"),
        "kraken": lambda: _probe_api("https://api.kraken.com/0/public/Time"),
        "ollama": lambda: _probe_api(f"{os.getenv('OLLAMA_HOST', 'http://10.10.10.15:11434').rstrip('/')}/api/tags"),
    }
    with ThreadPoolExecutor(max_workers=len(checks)) as executor:
        futures = {name: executor.submit(check) for name, check in checks.items()}
        statuses = {}
        for name, future in futures.items():
            try:
                statuses[name] = future.result(timeout=STATUS_TIMEOUT_SECONDS + 0.5)
            except Exception:
                statuses[name] = {"status": "offline", "detail": "No API response"}
    statuses["dashboard"] = {"status": "online", "detail": "Dashboard API is serving"}
    return statuses


@research_blueprint.get("/dashboard.css")
def dashboard_css():
    resp = send_from_directory(PROJECT_ROOT, "dashboard.css", mimetype="text/css")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@research_blueprint.get("/dashboard.js")
def dashboard_js():
    resp = send_from_directory(PROJECT_ROOT, "dashboard.js", mimetype="text/javascript")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@research_blueprint.get("/logo/MonetMakingMachine-logo.jpg")
def dashboard_logo():
    return send_from_directory(
        PROJECT_ROOT / "logo",
        "MonetMakingMachine-logo.jpg",
        mimetype="image/jpeg",
    )


@research_blueprint.get("/api/research/demo-prices")
def demo_prices_route():
    return jsonify({"prices": demo_prices(), "source": "synthetic demo data"})


@research_blueprint.get("/api/status")
def api_status_route():
    return jsonify(_api_statuses())


@research_blueprint.get("/api/market/data")
def market_data_route():
    try:
        snapshot = _request_market_snapshot(request.args)
    except MarketDataError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(_snapshot_payload(snapshot))


@research_blueprint.post("/api/research/analyze")
def analyze_market_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    question = str(payload.get("question", "Analyze the latest market structure and risks."))[:2000]
    try:
        snapshot = _request_market_snapshot(payload)
        settings = _settings_payload(payload)
        market_summary = _market_summary(snapshot)
    except (MarketDataError, ValueError) as error:
        return jsonify({"error": str(error)}), 400

    pa_structure = {}
    try:
        from strategies.price_action import PriceActionStrategy
        pa_strat = PriceActionStrategy()
        pa_structure = pa_strat.analyze_market_structure(snapshot.bars)
    except Exception:
        pa_structure = {}

    liquidity_telemetry = {}
    try:
        from quant_trading.liquidity import calculate_volume_profile, estimate_liquidation_clusters
        last_close = float(snapshot.bars[-1]["close"]) if snapshot.bars else 0.0
        vp = calculate_volume_profile(snapshot.bars)
        liq = estimate_liquidation_clusters(last_close)
        liquidity_telemetry = {
            "volume_profile": vp,
            "liquidation_clusters": liq,
        }
    except Exception:
        liquidity_telemetry = {}

    context = {
        "provider": snapshot.provider,
        "symbol": snapshot.symbol,
        "interval": snapshot.interval,
        "quote": snapshot.quote,
        "history": market_summary,
        "price_action_structure": pa_structure,
        "liquidity_profile": liquidity_telemetry,
        "recent_ohlcv": snapshot.bars[-40:],
        "active_strategy": "volatility-scaled time-series momentum & institutional price action",
        "strategy_settings": settings,
    }
    prompt = (
        "You are an institutional Price Action quantitative analyst operating under a strict NON-PREDICTIVE mandate. "
        "Never attempt to forecast or predict future price direction. Evaluate the current market structure objectively based ONLY on confirmed Price Action triggers: "
        "swing pivots (higher highs, lower lows), liquidity sweeps, rejection wicks, Breaks of Structure (BOS), Change of Character (ChoCH), and Volume Profile boundaries (POC, VAH, VAL). "
        "Separate observed structural facts from hypotheses, state that prices may be delayed, discuss risks, anchor stop losses strictly to structural wick levels with a minimum 1:2 Risk/Reward ratio, "
        "and if no confirmed structural setup is printing, recommend HOLD. "
        "If asked to optimize, suggest parameter candidates and say they must be backtested out of sample; do not claim to have optimized unless results are supplied. "
        f"User question: {question}\nMarket context JSON: {json.dumps(context, separators=(',', ':'))}"
    )
    from core.state_store import StateStore
    store = StateStore()
    stored_url = store.get_setting("orchestrator_url", "")
    stored_model = store.get_setting("orchestrator_model", "")

    ollama_url = (stored_url or os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434")).rstrip("/")
    model_name = stored_model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": model_name, "prompt": prompt, "stream": False},
            timeout=45,
        )
        if getattr(response, "status_code", 200) == 404:
            # Model not found on Ollama, try finding an available model from tags
            try:
                tags_resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
                if tags_resp.status_code == 200:
                    tags_data = tags_resp.json()
                    avail_models = [m.get("name") for m in tags_data.get("models", [])]
                    if avail_models:
                        model_name = avail_models[0]
                        response = requests.post(
                            f"{ollama_url}/api/generate",
                            json={"model": model_name, "prompt": prompt, "stream": False},
                            timeout=45,
                        )
            except Exception:
                pass
        response.raise_for_status()
        analysis = response.json().get("response", "")
        if not analysis:
            return jsonify({"error": "The analysis model returned an empty response"}), 502
    except requests.RequestException as e:
        err_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                err_json = e.response.json()
                if "error" in err_json:
                    err_msg = err_json["error"]
            except Exception:
                err_msg = e.response.text or str(e)
        return jsonify({"error": f"Analysis model is unavailable: {err_msg}"}), 502
    except (ValueError, AttributeError) as e:
        return jsonify({"error": f"Analysis model returned an invalid response: {str(e)}"}), 502

    return jsonify({
        "analysis": analysis,
        "symbol": snapshot.symbol,
        "provider": snapshot.provider,
        "quote": snapshot.quote,
        "summary": market_summary,
        "settings": settings,
        "price_action": pa_structure,
        "liquidity": liquidity_telemetry,
    })


@research_blueprint.post("/api/research/optimize")
def optimize_market_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    try:
        snapshot = _request_market_snapshot(payload)
        result = _optimize_settings(snapshot, payload)
    except (MarketDataError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(result)


def _request_market_snapshot(values: Any) -> MarketSnapshot:
    symbol = str(values.get("symbol", "")).strip()
    provider = str(values.get("provider", "yahoo")).lower()
    interval = str(values.get("interval", "1d" if provider == "yahoo" else "1h"))
    period = str(values.get("period", "1y"))
    return get_market_snapshot(provider, symbol, interval, period)


def _snapshot_payload(snapshot: MarketSnapshot) -> dict[str, Any]:
    liquidity: dict[str, Any] = {}
    try:
        from quant_trading.liquidity import calculate_volume_profile, estimate_liquidation_clusters, detect_cme_gaps
        vp = calculate_volume_profile(snapshot.bars)
        last_close = float(snapshot.bars[-1]["close"]) if snapshot.bars else 0.0
        liq = estimate_liquidation_clusters(last_close)
        gaps = detect_cme_gaps(snapshot.bars)
        liquidity = {
            "volume_profile": vp,
            "liquidation_clusters": liq,
            "cme_gaps": gaps,
        }
    except Exception:
        liquidity = {}

    return {
        "provider": snapshot.provider,
        "symbol": snapshot.symbol,
        "interval": snapshot.interval,
        "quote": snapshot.quote,
        "bars": snapshot.bars,
        "summary": _market_summary(snapshot),
        "liquidity": liquidity,
    }


def _market_summary(snapshot: MarketSnapshot) -> dict[str, Any]:
    if not snapshot.bars:
        raise MarketDataError("No historical price bars are available")
    close = pd.Series([bar["close"] for bar in snapshot.bars], dtype=float)
    returns = close.pct_change().dropna()
    latest = float(close.iloc[-1])
    periods_per_year = _periods_per_year(snapshot)
    summary: dict[str, Any] = {
        "bars": len(close),
        "start": snapshot.bars[0]["time"],
        "end": snapshot.bars[-1]["time"],
        "first_close": float(close.iloc[0]),
        "latest_close": latest,
        "period_return_pct": float((latest / close.iloc[0] - 1) * 100),
        "periods_per_year": periods_per_year,
        "annualized_volatility_pct": float(returns.std(ddof=1) * np.sqrt(periods_per_year) * 100) if len(returns) > 1 else None,
        "high": float(close.max()),
        "low": float(close.min()),
    }
    for window in (20, 50, 200):
        if len(close) >= window:
            average = float(close.rolling(window).mean().iloc[-1])
            summary[f"sma_{window}"] = average
            summary[f"vs_sma_{window}_pct"] = float((latest / average - 1) * 100)
    return summary


def _periods_per_year(snapshot: MarketSnapshot) -> int:
    annualized = {
        "yahoo": {"1d": 252, "1wk": 52, "1mo": 12, "1h": 1638, "30m": 3276, "15m": 6552},
        "binance": {"1m": 525600, "5m": 105120, "15m": 35040, "1h": 8760, "4h": 2190, "1d": 365, "1w": 52, "1M": 12},
    }
    return annualized.get(snapshot.provider, {}).get(snapshot.interval, 252)


def _settings_payload(payload: dict[str, Any]) -> dict[str, int | float]:
    settings = payload.get("settings", payload)
    if not isinstance(settings, dict):
        raise ValueError("settings must be a JSON object")
    normalized = {
        "lookback": _int_parameter(settings, "lookback", 40),
        "volatility_window": _int_parameter(settings, "volatility_window", 20),
        "target_annual_volatility": _float_parameter(settings, "target_annual_volatility", 0.15),
        "max_leverage": _float_parameter(settings, "max_leverage", 1.0),
        "one_way_cost_bps": _float_parameter(settings, "one_way_cost_bps", 2.0),
        "periods_per_year": _int_parameter(settings, "periods_per_year", 252),
    }
    if not 1 <= normalized["lookback"] <= 500:
        raise ValueError("lookback must be between 1 and 500")
    if not 2 <= normalized["volatility_window"] <= 500:
        raise ValueError("volatility_window must be between 2 and 500")
    if not 0.01 <= normalized["target_annual_volatility"] <= 1.0:
        raise ValueError("target_annual_volatility must be between 0.01 and 1.0")
    if not 0.01 <= normalized["max_leverage"] <= 10.0:
        raise ValueError("max_leverage must be between 0.01 and 10")
    if not 0 <= normalized["one_way_cost_bps"] <= 1000:
        raise ValueError("one_way_cost_bps must be between 0 and 1000")
    allowed_periods = {12, 52, 252, 365, 1638, 2190, 3276, 6552, 8760, 35040, 105120, 525600}
    if normalized["periods_per_year"] not in allowed_periods:
        raise ValueError("periods_per_year must match a supported market-data frequency")
    return normalized


def _finite_metrics(metrics: Any) -> dict[str, float | None]:
    return {
        name: float(value) if math.isfinite(value) else None
        for name, value in asdict(metrics).items()
    }


def _optimize_settings(snapshot: MarketSnapshot, payload: dict[str, Any]) -> dict[str, Any]:
    if len(snapshot.bars) < 120:
        raise ValueError("At least 120 historical bars are required for walk-forward comparison")
    settings = _settings_payload(payload)
    dates = pd.DatetimeIndex(pd.to_datetime([bar["time"] for bar in snapshot.bars], utc=True))
    close = validate_close_prices(pd.Series([bar["close"] for bar in snapshot.bars], index=dates, name="close"))
    split = int(len(close) * 0.7)
    if split < 60 or len(close) - split < 30:
        raise ValueError("History is too short for separate train and validation periods")

    config = BacktestConfig(
        periods_per_year=settings["periods_per_year"],
        one_way_cost_bps=settings["one_way_cost_bps"],
    )
    candidate_rows = []
    lookbacks = [10, 20, 40, 60]
    volatility_windows = [10, 20, 40]
    target_volatilities = sorted({
        round(max(0.03, min(0.5, settings["target_annual_volatility"] * multiplier)), 4)
        for multiplier in (0.75, 1.0, 1.25)
    })
    for lookback in lookbacks:
        for volatility_window in volatility_windows:
            if lookback >= split or volatility_window >= split:
                continue
            for target_volatility in target_volatilities:
                strategy = TimeSeriesMomentum(
                    lookback=lookback,
                    volatility_window=volatility_window,
                    target_annual_volatility=target_volatility,
                    max_leverage=settings["max_leverage"],
                    periods_per_year=settings["periods_per_year"],
                )
                result = BacktestEngine(config).run(close, strategy)
                train_metrics = calculate_metrics(result.net_returns.iloc[:split], settings["periods_per_year"])
                validation_metrics = calculate_metrics(result.net_returns.iloc[split:], settings["periods_per_year"])
                candidate_rows.append({
                    "settings": {
                        "lookback": lookback,
                        "volatility_window": volatility_window,
                        "target_annual_volatility": target_volatility,
                    },
                    "train": _finite_metrics(train_metrics),
                    "validation": _finite_metrics(validation_metrics),
                })

    candidate_rows.sort(
        key=lambda row: row["train"]["sharpe_ratio"] if row["train"]["sharpe_ratio"] is not None else -math.inf,
        reverse=True,
    )
    baseline_strategy = TimeSeriesMomentum(
        lookback=settings["lookback"],
        volatility_window=settings["volatility_window"],
        target_annual_volatility=settings["target_annual_volatility"],
        max_leverage=settings["max_leverage"],
        periods_per_year=settings["periods_per_year"],
    )
    baseline_result = BacktestEngine(config).run(close, baseline_strategy)
    baseline_validation = _finite_metrics(
        calculate_metrics(baseline_result.net_returns.iloc[split:], settings["periods_per_year"])
    )
    return {
        "provider": snapshot.provider,
        "symbol": snapshot.symbol,
        "interval": snapshot.interval,
        "observations": len(close),
        "train_end": close.index[split - 1].isoformat(),
        "validation_start": close.index[split].isoformat(),
        "objective": "Training-period Sharpe ratio; validation is reported separately and is not used for ranking.",
        "baseline": {"settings": settings, "validation": baseline_validation},
        "candidates": candidate_rows[:3],
    }


@research_blueprint.post("/api/research/backtest")
def backtest_route():
    if request.content_length and request.content_length > 2_000_000:
        return jsonify({"error": "Request body exceeds the 2 MB limit"}), 413
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    try:
        return jsonify(build_backtest_response(payload))
    except (TypeError, ValueError, OverflowError) as error:
        return jsonify({"error": str(error)}), 400


def _prices_from_csv(content: str) -> pd.Series:
    reader = csv.DictReader(StringIO(content))
    if reader.fieldnames is None:
        raise ValueError("CSV must have date and close columns")

    columns = {name.strip().lower(): name for name in reader.fieldnames if name}
    if "date" not in columns or "close" not in columns:
        raise ValueError("CSV must have columns named date and close")

    dates: list[str] = []
    values: list[float] = []
    for row in reader:
        if len(dates) >= MAX_PRICE_ROWS:
            raise ValueError(f"CSV cannot exceed {MAX_PRICE_ROWS} rows")
        try:
            dates.append(row[columns["date"]].strip())
            values.append(float(row[columns["close"]]))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("CSV date and close values must be present and valid") from error

    try:
        index = pd.DatetimeIndex(pd.to_datetime(dates, utc=True, errors="raise"))
    except (TypeError, ValueError) as error:
        raise ValueError("CSV date values must be valid timestamps") from error
    return validate_close_prices(pd.Series(values, index=index, name="close"))


def _prices_from_rows(rows: Any) -> pd.Series:
    if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_PRICE_ROWS:
        raise ValueError(f"prices must contain between 2 and {MAX_PRICE_ROWS} rows")
    try:
        dates = [row["date"] for row in rows]
        values = [float(row["close"]) for row in rows]
        index = pd.DatetimeIndex(pd.to_datetime(dates, utc=True, errors="raise"))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("each price row must contain a valid date and close") from error
    return validate_close_prices(pd.Series(values, index=index, name="close"))


def _load_prices(payload: dict[str, Any]) -> pd.Series:
    if "csv" in payload:
        if not isinstance(payload["csv"], str):
            raise ValueError("csv must be text")
        return _prices_from_csv(payload["csv"])
    return _prices_from_rows(payload.get("prices"))


def _int_parameter(payload: dict[str, Any], name: str, default: int) -> int:
    value = payload.get(name, default)
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        converted = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be an integer") from error
    if converted != value:
        raise ValueError(f"{name} must be an integer")
    return converted


def _float_parameter(payload: dict[str, Any], name: str, default: float) -> float:
    value = payload.get(name, default)
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    try:
        converted = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a number") from error
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def build_backtest_response(payload: dict[str, Any]) -> dict[str, Any]:
    close = _load_prices(payload)
    periods_per_year = _int_parameter(payload, "periods_per_year", 252)
    strategy = TimeSeriesMomentum(
        lookback=_int_parameter(payload, "lookback", 40),
        volatility_window=_int_parameter(payload, "volatility_window", 20),
        target_annual_volatility=_float_parameter(payload, "target_annual_volatility", 0.15),
        max_leverage=_float_parameter(payload, "max_leverage", 1.0),
        periods_per_year=periods_per_year,
    )
    config = BacktestConfig(
        periods_per_year=periods_per_year,
        one_way_cost_bps=_float_parameter(payload, "one_way_cost_bps", 2.0),
    )
    result = BacktestEngine(config).run(close, strategy)

    metrics = {
        name: value if math.isfinite(value) else None
        for name, value in asdict(result.metrics).items()
    }
    step = max(1, math.ceil(len(result.equity) / MAX_CHART_POINTS))
    sample_indices = list(range(0, len(result.equity), step))
    if sample_indices[-1] != len(result.equity) - 1:
        sample_indices.append(len(result.equity) - 1)
    curve = [
        {
            "date": result.equity.index[index].isoformat(),
            "equity": float(result.equity.iloc[index]),
            "position": float(result.positions.iloc[index]),
        }
        for index in sample_indices
    ]
    return {
        "strategy": "Time-series momentum",
        "observations": len(close),
        "start_date": close.index[0].isoformat(),
        "end_date": close.index[-1].isoformat(),
        "metrics": metrics,
        "curve": curve,
    }


def demo_prices() -> list[dict[str, float | str]]:
    random = np.random.default_rng(17)
    periods = 750
    dates = pd.date_range("2023-01-02", periods=periods, freq="B")
    drift = np.resize(np.array([0.00045, -0.0002, 0.00065, -0.00035]), periods)
    returns = random.normal(loc=drift, scale=0.009, size=periods)
    close = 100.0 * np.cumprod(1.0 + returns)
    return [
        {"date": date.strftime("%Y-%m-%d"), "close": float(value)}
        for date, value in zip(dates, close, strict=True)
    ]
