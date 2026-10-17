import os, sys, uuid, time, base64, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from flask import Flask, jsonify, request, render_template_string, make_response
from quant_trading.flask_api import research_blueprint
from brokers.t212_adapter import Trading212Broker
try:
    from brokers.kraken_adapter import KrakenBroker
except ImportError:
    KrakenBroker = None

try:
    from brokers.binance_adapter import BinanceBroker
except ImportError:
    BinanceBroker = None

from quant_trading.admin_api import admin_blueprint
from quant_trading.agent_c_api import agent_c_blueprint
from quant_trading.orchestrator_api import orchestrator_blueprint
from quant_trading.ctrader_api import ctrader_blueprint
from quant_trading.workflow_api import workflow_blueprint
from quant_trading.pubsub_api import pubsub_blueprint
from quant_trading.resource_api import resource_blueprint

app = Flask(__name__)
app.register_blueprint(research_blueprint)
app.register_blueprint(admin_blueprint)
app.register_blueprint(agent_c_blueprint)
app.register_blueprint(orchestrator_blueprint)
app.register_blueprint(ctrader_blueprint)
app.register_blueprint(workflow_blueprint)
app.register_blueprint(pubsub_blueprint)
app.register_blueprint(resource_blueprint)
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://10.10.10.15:11434")

ETORO_PAIRS = {
    "ETH": {"id": 100002, "strategy": "1H RSI Mean Reversion"},
    "BTC": {"id": 100001, "strategy": "Macro Trend Swing"},
    "SOL": {"id": 100085, "strategy": "FVG Breakout Momentum"},
    "ADA": {"id": 100015, "strategy": "1H RSI Mean Reversion"},
    "XRP": {"id": 100003, "strategy": "Range Scalp"},
    "DOGE": {"id": 100067, "strategy": "Volatility Breakout"},
    "AVAX": {"id": 100095, "strategy": "1H RSI Mean Reversion"},
    "LTC": {"id": 100005, "strategy": "1H RSI Mean Reversion"}
}

def load_etoro_headers():
    api_key = os.getenv("ETORO_API_KEY", "").strip("\"' ")
    user_key = os.getenv("ETORO_USER_KEY", "").strip("\"' ")
    if not (api_key and user_key):
        root_dir = os.path.dirname(os.path.abspath(__file__))
        env_paths = [
            os.path.join(root_dir, ".env"),
            os.path.join(root_dir, "etoro.env"),
            os.path.join(root_dir, "config", "etoro.env"),
            "/home/vineet/feed-agent/etoro.env",
        ]
        for p in env_paths:
            if api_key and user_key:
                break
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        for line in f:
                            if "=" in line and not line.strip().startswith("#"):
                                k, v = line.strip().split("=", 1)
                                if k.strip() == "ETORO_API_KEY" and not api_key:
                                    api_key = v.strip().strip("\"' ")
                                if k.strip() == "ETORO_USER_KEY" and not user_key:
                                    user_key = v.strip().strip("\"' ")
                except OSError:
                    continue
    return {
        "x-api-key": api_key,
        "x-user-key": user_key,
        "x-request-id": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MoneyMakingMachine - QWERTY CORP</title>
    <style>
        :root {
            --bg: #0b0f19; --card: #151e32; --border: #24324f;
            --text: #f8fafc; --muted: #94a3b8; --green: #10b981;
            --red: #ef4444; --blue: #3b82f6; --purple: #8b5cf6; --amber: #f59e0b;
        }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 20px; }
        .tabs { display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 8px; overflow-x: auto; }
        .tab-btn { background: #1e293b; color: var(--muted); border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.9rem; transition: background 0.2s, color 0.2s; }
        .tab-btn:hover, .tab-btn.active { background: var(--blue); color: #fff; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 18px; margin-bottom: 20px; }
        .card-label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; }
        .card-val { font-size: 1.5rem; font-weight: 700; margin-top: 5px; }
        .btn { cursor: pointer; padding: 8px 14px; border: none; border-radius: 6px; font-weight: 600; font-size: 0.85rem; }
        .btn-blue { background: var(--blue); color: white; }
        .btn-purple { background: var(--purple); color: white; }
        .btn-red { background: var(--red); color: white; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--border); font-size: 0.88rem; }
        th { color: var(--muted); text-transform: uppercase; font-size: 0.75rem; }
        .badge { padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
        .badge-strat { background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3); }
        .search-container { display: flex; gap: 10px; margin-bottom: 15px; margin-top: 10px; }
        .search-input { flex: 1; background: #070d1e; border: 1px solid var(--border); color: #fff; padding: 10px 14px; border-radius: 6px; font-size: 0.9rem; outline: none; }
        .search-results { max-height: 250px; overflow-y: auto; background: #0c1326; border: 1px solid var(--border); border-radius: 6px; margin-bottom: 15px; display: none; }
        .ai-output { background: #070d1e; border: 1px solid #1e293b; border-radius: 6px; padding: 15px; font-size: 0.9rem; min-height: 60px; color: #38bdf8; white-space: pre-wrap; max-height: 250px; overflow-y: auto; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h1 style="margin:0; font-size: 1.5rem;">MoneyMakingMachine - QWERTY CORP</h1>
            <span class="badge" style="background: rgba(245,158,11,0.2); color: var(--amber); border: 1px solid var(--amber); margin-top: 5px; display:inline-block;">QUANT MULTI-BROKER</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--muted);">AI Inference Host: <strong style="color: #38bdf8;">10.10.10.15:11434</strong></div>
    </div>

    <!-- Top Navigation Tabs -->
    <div class="tabs">
        <button class="tab-btn active" onclick="openTab(event, 't212-tab')">Trading 212 (Invest)</button>
        <button class="tab-btn" onclick="openTab(event, 'etoro-tab')">eToro Quant Hub</button>
        <button class="tab-btn" onclick="openTab(event, 'binance-tab')">Binance Spot</button>
        <button class="tab-btn" onclick="openTab(event, 'kraken-tab')">Kraken Spot</button>
        <button class="tab-btn" onclick="openTab(event, 'quantai-tab')">QuantAI</button>
    </div>

    <!-- T212 TAB -->
    <div id="t212-tab" class="tab-content">
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h2 style="margin:0; font-size:1.2rem;">Trading 212 Practice Portfolio (-2.0% Auto Stop-Loss Active)</h2>
                <button class="btn btn-blue" onclick="fetchT212Portfolio()">Refresh T212</button>
            </div>
            <div class="grid" style="margin-top:15px;">
                <div class="card"><div class="card-label">Cash Available</div><div id="t212-cash" class="card-val">$0.00</div></div>
                <div class="card"><div class="card-label">Active Positions</div><div id="t212-pos-count" class="card-val">0</div></div>
                <div class="card"><div class="card-label">Total Invested</div><div id="t212-invested" class="card-val">$0.00</div></div>
                <div class="card"><div class="card-label">Unrealized P/L</div><div id="t212-pnl" class="card-val">$0.00</div></div>
                <div class="card"><div class="card-label">Total Equity</div><div id="t212-equity" class="card-val">$0.00</div></div>
            </div>
            <h3>Active Equity Holdings & Assigned Strategy</h3>
            <table>
                <thead>
                    <tr><th>Ticker</th><th>Strategy</th><th>Units</th><th>Open Price</th><th>Total Invested</th><th>P/L ($)</th><th>P/L (%)</th><th>Status</th></tr>
                </thead>
                <tbody id="t212-tbody"><tr><td colspan="8" style="text-align:center; color:var(--muted);">Loading positions...</td></tr></tbody>
            </table>
        </div>
        <div class="card">
            <h3 style="margin:0;">Search Stocks & ETFs on Trading 212</h3>
            <div class="search-container">
                <input type="text" id="t212-search-input" class="search-input" placeholder="Search by Ticker, ISIN, or Name (e.g. VUKE, SPY, Apple)..." onkeyup="if(event.key==='Enter') executeT212Search()">
                <button class="btn btn-blue" onclick="executeT212Search()">Search T212</button>
            </div>
            <div id="t212-search-results" class="search-results">
                <table><thead><tr><th>Ticker</th><th>Name</th><th>Type</th><th>Currency</th><th>Action</th></tr></thead><tbody id="t212-search-tbody"></tbody></table>
            </div>
        </div>
        <div class="card">
            <h3 style="margin:0 0 10px 0;">T212 Agent (Equities Macro & DCA Specialist)</h3>
            <div id="t212-ai-box" class="ai-output">Click below to query DeepSeek-R1 at 10.10.10.15 across vmbr1...</div>
            <div style="margin-top:12px;">
                <button class="btn btn-purple" onclick="runAgent('t212', 'SPY')">Analyze SPY 200 SMA</button>
                <button class="btn btn-purple" onclick="runAgent('t212', 'VUKE')">Analyze VUKE Dividend DCA</button>
                <button class="btn btn-purple" onclick="runAgent('t212', 'AAPL')">Analyze AAPL</button>
            </div>
        </div>
    </div>

    <!-- ETORO TAB -->
    <div id="etoro-tab" class="tab-content" style="display:none;">
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h2 style="margin:0; font-size:1.2rem;">eToro Quant Hub</h2>
                <button class="btn btn-blue" onclick="fetchEtoroPortfolio()">Refresh eToro</button>
            </div>
            <div class="grid" style="margin-top:15px;">
                <div class="card"><div class="card-label">Credit (Cash)</div><div id="etoro-cash" class="card-val">$0.00</div></div>
                <div class="card"><div class="card-label">Positions</div><div id="etoro-pos-count" class="card-val">0</div></div>
                <div class="card"><div class="card-label">Allocated</div><div id="etoro-allocated" class="card-val">$0.00</div></div>
                <div class="card"><div class="card-label">Unrealized P/L</div><div id="etoro-pnl" class="card-val">$0.00</div></div>
            </div>
            <h3>Active Positions & Strategy</h3>
            <table>
                <thead><tr><th>Position ID</th><th>Asset</th><th>Strategy</th><th>Type</th><th>Units</th><th>Open Rate</th><th>Amount</th><th>P/L ($)</th></tr></thead>
                <tbody id="etoro-tbody"><tr><td colspan="8" style="text-align:center; color:var(--muted);">Loading eToro positions...</td></tr></tbody>
            </table>
        </div>
        <div class="card">
            <h3 style="margin:0;">Search Crypto Pairs (eToro / Global)</h3>
            <div class="search-container">
                <input type="text" id="etoro-search-input" class="search-input" placeholder="Search Crypto Asset (e.g. BTC, ETH, SOL, ADA, XRP)..." onkeyup="if(event.key==='Enter') executeEtoroSearch()">
                <button class="btn btn-blue" onclick="executeEtoroSearch()">Search Crypto</button>
            </div>
            <div id="etoro-search-results" class="search-results">
                <table><thead><tr><th>Symbol</th><th>Price</th><th>24h Change</th><th>Action</th></tr></thead><tbody id="etoro-search-tbody"></tbody></table>
            </div>
        </div>
        <div class="card">
            <h3 style="margin:0 0 10px 0;">eToro Agent (1H RSI & FVG Specialist)</h3>
            <div id="etoro-ai-box" class="ai-output">eToro Agent Standby...</div>
            <div style="margin-top:12px;">
                <button class="btn btn-purple" onclick="runAgent('etoro', 'ETH')">Analyze ETH 1H Reversion</button>
                <button class="btn btn-purple" onclick="runAgent('etoro', 'SOL')">Analyze SOL FVG Zone</button>
            </div>
        </div>
    </div>

    <!-- BINANCE TAB -->
    <div id="binance-tab" class="tab-content" style="display:none;">
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h2 style="margin:0; font-size:1.2rem;">Binance Spot Account</h2>
                <button class="btn btn-blue" onclick="fetchBinancePortfolio()">Refresh Binance</button>
            </div>
            <div class="grid" style="margin-top:15px;">
                <div class="card"><div class="card-label">USDT / Free Cash</div><div id="binance-cash" class="card-val">$0.00</div></div>
                <div class="card"><div class="card-label">Active Holdings</div><div id="binance-pos-count" class="card-val">0</div></div>
                <div class="card"><div class="card-label">Total Equity</div><div id="binance-total" class="card-val">$0.00</div></div>
            </div>
            <h3>Spot Balances & Assigned Strategy</h3>
            <table>
                <thead><tr><th>Asset</th><th>Strategy</th><th>Units</th><th>Estimated Rate</th><th>Status</th></tr></thead>
                <tbody id="binance-tbody"><tr><td colspan="5" style="text-align:center; color:var(--muted);">Loading Binance balances...</td></tr></tbody>
            </table>
        </div>
        <div class="card">
            <h3 style="margin:0;">Search Binance Spot Crypto Pairs</h3>
            <div class="search-container">
                <input type="text" id="binance-search-input" class="search-input" placeholder="Search Crypto Pair (e.g. BTC, SOL, ETH, PEPE)..." onkeyup="if(event.key==='Enter') executeBinanceSearch()">
                <button class="btn btn-blue" onclick="executeBinanceSearch()">Search Pairs</button>
            </div>
            <div id="binance-search-results" class="search-results">
                <table><thead><tr><th>Symbol</th><th>Last Price</th><th>24h Change</th><th>Volume</th><th>Action</th></tr></thead><tbody id="binance-search-tbody"></tbody></table>
            </div>
        </div>
        <div class="card">
            <h3 style="margin:0 0 10px 0;">Binance Agent (5m High-Frequency Order-Flow Specialist)</h3>
            <div id="binance-ai-box" class="ai-output">Binance Agent Standby...</div>
            <div style="margin-top:12px;">
                <button class="btn btn-purple" onclick="runAgent('binance', 'ETHUSDT')">Analyze ETHUSDT 5m</button>
                <button class="btn btn-purple" onclick="runAgent('binance', 'SOLUSDT')">Analyze SOLUSDT 5m</button>
            </div>
        </div>
    </div>

    <!-- KRAKEN TAB -->
    <div id="kraken-tab" class="tab-content" style="display:none;">
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h2 style="margin:0; font-size:1.2rem;">Kraken Spot Account</h2>
                <button class="btn btn-blue" onclick="fetchKrakenPortfolio()">Refresh Kraken</button>
            </div>
            <div class="grid" style="margin-top:15px;">
                <div class="card"><div class="card-label">USD / Cash Balance</div><div id="kraken-cash" class="card-val">$0.00</div></div>
                <div class="card"><div class="card-label">Active Holdings</div><div id="kraken-pos-count" class="card-val">0</div></div>
            </div>
            <h3>Kraken Holdings & Assigned Strategy</h3>
            <table>
                <thead><tr><th>Asset</th><th>Strategy</th><th>Units</th><th>Status</th></tr></thead>
                <tbody id="kraken-tbody"><tr><td colspan="4" style="text-align:center; color:var(--muted);">Loading Kraken balances...</td></tr></tbody>
            </table>
        </div>
        <div class="card">
            <h3 style="margin:0;">Search Kraken Spot Pairs</h3>
            <div class="search-container">
                <input type="text" id="kraken-search-input" class="search-input" placeholder="Search Kraken Pair (e.g. ETH, USD, EUR, XBT)..." onkeyup="if(event.key==='Enter') executeKrakenSearch()">
                <button class="btn btn-blue" onclick="executeKrakenSearch()">Search Kraken</button>
            </div>
            <div id="kraken-search-results" class="search-results">
                <table><thead><tr><th>Pair Name</th><th>Base</th><th>Quote</th><th>Status</th><th>Action</th></tr></thead><tbody id="kraken-search-tbody"></tbody></table>
            </div>
        </div>
        <div class="card">
            <h3 style="margin:0 0 10px 0;">Kraken Agent (Multi-Currency Swing Specialist)</h3>
            <div id="kraken-ai-box" class="ai-output">Kraken Agent Standby...</div>
            <div style="margin-top:12px;">
                <button class="btn btn-purple" onclick="runAgent('kraken', 'ETHUSD')">Analyze ETHUSD Swing</button>
            </div>
        </div>
    </div>

    <!-- QUANTAI TAB -->
    <div id="quantai-tab" class="tab-content" style="display:none;">
        <div class="card">
            <h2 style="margin:0 0 10px 0; font-size:1.2rem;">QuantAI Multi-Agent Reasoner</h2>
            <div id="quantai-ai-box" class="ai-output">QuantAI System Online. Connected to DeepSeek-R1 at 10.10.10.15:11434 across vmbr1.</div>
            <div style="margin-top:12px;">
                <button class="btn btn-purple" onclick="runAgent('quantai', 'PORTFOLIO')">Run Cross-Broker Portfolio Synthesis</button>
            </div>
        </div>
    </div>
</div>

<script>
    function openTab(evt, tabId) {
        document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(tabId).style.display = 'block';
        evt.currentTarget.classList.add('active');
    }

    async function fetchT212Portfolio() {
        try {
            const r = await fetch('/api/t212/portfolio');
            const d = await r.json();
            document.getElementById('t212-cash').innerText = '$' + (d.cash || 0).toFixed(2);
            document.getElementById('t212-pos-count').innerText = d.active_positions || 0;
            document.getElementById('t212-invested').innerText = '$' + (d.total_invested || 0).toFixed(2);
            document.getElementById('t212-pnl').innerText = (d.unrealized_pnl >= 0 ? '+' : '') + '$' + (d.unrealized_pnl || 0).toFixed(2);
            document.getElementById('t212-equity').innerText = '$' + (d.total_equity || 0).toFixed(2);
            const tbody = document.getElementById('t212-tbody');
            tbody.innerHTML = '';
            if (!d.positions || d.positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--muted);">No active positions.</td></tr>';
                return;
            }
            d.positions.forEach(p => {
                const strat = p.strategy || "200-Day SMA Macro";
                let row = '<tr>';
                row += '<td><strong>' + p.ticker + '</strong></td>';
                row += '<td><span class="badge badge-strat">' + strat + '</span></td>';
                row += '<td>' + (p.units || 0).toFixed(4) + '</td>';
                row += '<td>$' + (p.open_price || 0).toFixed(2) + '</td>';
                row += '<td>$' + (p.invested || 0).toFixed(2) + '</td>';
                row += '<td style="color:' + (p.ppl >= 0 ? 'var(--green)' : 'var(--red)') + '">' + (p.ppl >= 0 ? '+' : '') + '$' + (p.ppl || 0).toFixed(2) + '</td>';
                row += '<td><span class="badge" style="color:' + (p.ppl_pct >= 0 ? 'var(--green)' : 'var(--red)') + '">' + p.ppl_pct + '%</span></td>';
                row += '<td><span class="badge" style="color:var(--green)">' + p.status + '</span></td>';
                row += '</tr>';
                tbody.innerHTML += row;
            });
        } catch(e) {}
    }

    async function fetchEtoroPortfolio() {
        try {
            const r = await fetch('/api/etoro/portfolio');
            const d = await r.json();
            document.getElementById('etoro-cash').innerText = '$' + (d.credit || 0).toFixed(2);
            document.getElementById('etoro-pos-count').innerText = (d.positions || []).length;
            document.getElementById('etoro-allocated').innerText = '$' + (d.allocated || 0).toFixed(2);
            document.getElementById('etoro-pnl').innerText = (d.unrealized_pnl >= 0 ? '+' : '') + '$' + (d.unrealized_pnl || 0).toFixed(2);
            const tbody = document.getElementById('etoro-tbody');
            tbody.innerHTML = '';
            if (!d.positions || d.positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--muted);">No active positions.</td></tr>';
                return;
            }
            d.positions.forEach(p => {
                let row = '<tr>';
                row += '<td>' + p.positionID + '</td>';
                row += '<td><strong>' + p.symbol + '</strong></td>';
                row += '<td><span class="badge badge-strat">' + p.strategy + '</span></td>';
                row += '<td>' + (p.isBuy ? 'BUY' : 'SELL') + '</td>';
                row += '<td>' + p.units + '</td>';
                row += '<td>$' + (p.openRate || 0).toFixed(2) + '</td>';
                row += '<td>$' + (p.amount || 0).toFixed(2) + '</td>';
                row += '<td style="color:' + (p.netProfit >= 0 ? 'var(--green)' : 'var(--red)') + '">$' + (p.netProfit || 0).toFixed(2) + '</td>';
                row += '</tr>';
                tbody.innerHTML += row;
            });
        } catch(e) {}
    }

    async function fetchBinancePortfolio() {
        try {
            const r = await fetch('/api/binance/portfolio');
            const d = await r.json();
            document.getElementById('binance-cash').innerText = '$' + (d.cash || 0).toFixed(2);
            document.getElementById('binance-pos-count').innerText = d.active_positions || 0;
            document.getElementById('binance-total').innerText = '$' + (d.total_equity || 0).toFixed(2);
            const tbody = document.getElementById('binance-tbody');
            tbody.innerHTML = '';
            if (!d.positions || d.positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--muted);">No balances held.</td></tr>';
                return;
            }
            d.positions.forEach(p => {
                let row = '<tr><td><strong>' + p.ticker + '</strong></td><td><span class="badge badge-strat">5m Kline Momentum</span></td><td>' + p.units + '</td><td>$' + (p.open_price || 0).toFixed(2) + '</td><td><span class="badge" style="color:var(--green)">' + p.status + '</span></td></tr>';
                tbody.innerHTML += row;
            });
        } catch(e) {}
    }

    async function fetchKrakenPortfolio() {
        try {
            const r = await fetch('/api/kraken/portfolio');
            const d = await r.json();
            document.getElementById('kraken-cash').innerText = '$' + (d.cash || 0).toFixed(2);
            document.getElementById('kraken-pos-count').innerText = d.active_positions || 0;
            const tbody = document.getElementById('kraken-tbody');
            tbody.innerHTML = '';
            if (!d.positions || d.positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--muted);">No balances held.</td></tr>';
                return;
            }
            d.positions.forEach(p => {
                let row = '<tr><td><strong>' + p.ticker + '</strong></td><td><span class="badge badge-strat">' + p.strategy + '</span></td><td>' + p.units + '</td><td><span class="badge" style="color:var(--green)">' + p.status + '</span></td></tr>';
                tbody.innerHTML += row;
            });
        } catch(e) {}
    }

    async function runAgent(broker, sym) {
        const box = document.getElementById(broker + '-ai-box');
        if (box) box.innerText = '[' + broker.toUpperCase() + ' AGENT] Querying DeepSeek-R1 at 10.10.10.15 for ' + sym + '...';
        try {
            const r = await fetch('/api/agent/query?broker=' + broker + '&symbol=' + sym);
            const d = await r.json();
            if (box) box.innerText = d.analysis || d.error;
        } catch(e) {
            if (box) box.innerText = 'Error: ' + e.message;
        }
    }

    async function executeT212Search() {
        const q = document.getElementById('t212-search-input').value.trim();
        if (!q) return;
        const box = document.getElementById('t212-search-results');
        const tbody = document.getElementById('t212-search-tbody');
        box.style.display = 'block';
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Searching...</td></tr>';
        const r = await fetch('/api/search/t212?q=' + encodeURIComponent(q));
        const data = await r.json();
        tbody.innerHTML = '';
        if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--muted);">No instruments found.</td></tr>'; return; }
        data.forEach(item => {
            tbody.innerHTML += '<tr><td><strong>' + item.ticker + '</strong></td><td>' + item.name + '</td><td>' + item.type + '</td><td>' + item.currency + '</td><td><button class="btn btn-purple" onclick="runAgent(\'t212\', \'' + item.ticker + '\')">AI Analyze</button></td></tr>';
        });
    }

    async function executeEtoroSearch() {
        const q = document.getElementById('etoro-search-input').value.trim();
        if (!q) return;
        const box = document.getElementById('etoro-search-results');
        const tbody = document.getElementById('etoro-search-tbody');
        box.style.display = 'block';
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Searching crypto feeds...</td></tr>';
        const r = await fetch('/api/search/binance?q=' + encodeURIComponent(q));
        const data = await r.json();
        tbody.innerHTML = '';
        if (!data.length) { tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--muted);">No pairs found.</td></tr>'; return; }
        data.forEach(item => {
            tbody.innerHTML += '<tr><td><strong>' + item.symbol + '</strong></td><td>$' + item.price.toFixed(4) + '</td><td>' + item.change.toFixed(2) + '%</td><td><button class="btn btn-purple" onclick="runAgent(\'etoro\', \'' + item.symbol + '\')">AI Check</button></td></tr>';
        });
    }

    async function executeBinanceSearch() {
        const q = document.getElementById('binance-search-input').value.trim();
        if (!q) return;
        const box = document.getElementById('binance-search-results');
        const tbody = document.getElementById('binance-search-tbody');
        box.style.display = 'block';
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Scanning Binance...</td></tr>';
        const r = await fetch('/api/search/binance?q=' + encodeURIComponent(q));
        const data = await r.json();
        tbody.innerHTML = '';
        if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--muted);">No pairs found.</td></tr>'; return; }
        data.forEach(item => {
            tbody.innerHTML += '<tr><td><strong>' + item.symbol + '</strong></td><td>$' + item.price.toFixed(4) + '</td><td>' + item.change.toFixed(2) + '%</td><td>' + item.volume.toFixed(0) + '</td><td><button class="btn btn-purple" onclick="runAgent(\'binance\', \'' + item.symbol + '\')">AI Check</button></td></tr>';
        });
    }

    async function executeKrakenSearch() {
        const q = document.getElementById('kraken-search-input').value.trim();
        if (!q) return;
        const box = document.getElementById('kraken-search-results');
        const tbody = document.getElementById('kraken-search-tbody');
        box.style.display = 'block';
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Querying Kraken...</td></tr>';
        const r = await fetch('/api/search/kraken?q=' + encodeURIComponent(q));
        const data = await r.json();
        tbody.innerHTML = '';
        if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--muted);">No pairs found.</td></tr>'; return; }
        data.forEach(item => {
            const pName = item.display || item.pair;
            tbody.innerHTML += '<tr><td><strong>' + pName + '</strong></td><td>' + item.base + '</td><td>' + item.quote + '</td><td>' + item.status + '</td><td><button class="btn btn-purple" onclick="runAgent(\'kraken\', \'' + pName + '\')">AI Analyze</button></td></tr>';
        });
    }

    fetchT212Portfolio();
    fetchEtoroPortfolio();
    fetchBinancePortfolio();
    fetchKrakenPortfolio();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(dashboard_path, encoding="utf-8") as dashboard_file:
        resp = make_response(dashboard_file.read())
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@app.route("/api/t212/portfolio")
def t212_portfolio():
    try:
        t212 = Trading212Broker(is_demo=True)
        cash, pos_objs = t212.get_portfolio()
        positions = []
        for p in pos_objs:
            if isinstance(p, dict):
                ticker = p.get("ticker", "UNKNOWN")
                units = float(p.get("units", 0.0))
                open_price = float(p.get("open_price", 0.0))
                invested = float(p.get("invested", units * open_price))
                ppl = float(p.get("ppl", 0.0))
                ppl_pct = float(p.get("ppl_pct", 0.0))
            else:
                ticker = getattr(p, "symbol", getattr(p, "ticker", "UNKNOWN"))
                units = float(getattr(p, "units", 0.0))
                open_price = float(getattr(p, "open_rate", 0.0))
                invested = float(getattr(p, "invested_amount", units * open_price))
                ppl = float(getattr(p, "netProfit", getattr(p, "unrealized_pnl", 0.0)))
                ppl_pct = round((ppl / invested * 100), 2) if invested > 0 else 0.0

            strat = "Dividend DCA Yield" if ("V" in ticker or "O" in ticker) else "200-Day SMA Macro"
            positions.append({
                "ticker": ticker,
                "strategy": strat,
                "units": units,
                "open_price": open_price,
                "invested": invested,
                "ppl": ppl,
                "ppl_pct": ppl_pct,
                "status": "ACTIVE"
            })
        total_invested = round(sum(p["invested"] for p in positions), 2)
        total_unrealized = round(sum(p["ppl"] for p in positions), 2)
        return jsonify({
            "cash": round(cash, 2), "active_positions": len(positions),
            "total_invested": total_invested, "unrealized_pnl": total_unrealized,
            "total_equity": round(cash + total_invested + total_unrealized, 2),
            "positions": positions
        })
    except Exception as e:
        return jsonify({"error": str(e), "cash": 0.0, "positions": []}), 500

@app.route("/api/etoro/portfolio")
def etoro_portfolio():
    headers = load_etoro_headers()
    try:
        r = requests.get("https://public-api.etoro.com/api/v1/trading/info/demo/portfolio", headers=headers, timeout=5)
        raw_pos = r.json().get("clientPortfolio", {}).get("positions", []) if r.status_code == 200 else []
        r_pnl = requests.get("https://public-api.etoro.com/api/v1/trading/info/demo/pnl", headers=headers, timeout=5)
        pnl_map = {}
        if r_pnl.status_code == 200:
            for p in r_pnl.json().get("clientPortfolio", {}).get("positions", []):
                pnl_map[p.get("positionID")] = float(p.get("unrealizedPnL", {}).get("pnL", 0.0))
        positions = []
        for p in raw_pos:
            pid = p.get("positionID")
            iid = p.get("instrumentID")
            sym = "CRYPTO"
            strat = "1H RSI Mean Reversion"
            for s, meta in ETORO_PAIRS.items():
                if meta["id"] == iid:
                    sym = s
                    strat = meta["strategy"]
                    break
            positions.append({
                "positionID": pid, "instrumentID": iid, "symbol": sym, "strategy": strat,
                "isBuy": p.get("isBuy", True), "units": float(p.get("units", 0.0)),
                "openRate": float(p.get("openRate", 0.0)), "amount": float(p.get("amount", 0.0)),
                "netProfit": pnl_map.get(pid, 0.0)
            })
        credit = float(r.json().get("clientPortfolio", {}).get("credit", 0.0)) if r.status_code == 200 else 0.0
        return jsonify({
            "credit": credit, "allocated": sum(p["amount"] for p in positions),
            "unrealized_pnl": sum(p["netProfit"] for p in positions), "positions": positions
        })
    except Exception as e:
        return jsonify({"error": str(e), "credit": 0.0, "positions": []}), 500

@app.route("/api/binance/portfolio")
def binance_portfolio():
    if not BinanceBroker: return jsonify({"cash": 0.0, "active_positions": 0, "positions": []})
    try:
        b = BinanceBroker(is_demo=False)
        cash, positions = b.get_portfolio()
        pos_list = [{
            "ticker": p.symbol, "strategy": "5m Kline Momentum", "units": p.units,
            "open_price": p.open_rate, "invested": p.invested_amount, "status": "ACTIVE"
        } for p in positions]
        return jsonify({"cash": round(cash, 2), "active_positions": len(pos_list), "total_equity": round(cash, 2), "positions": pos_list})
    except Exception as e:
        return jsonify({"error": str(e), "cash": 0.0, "positions": []}), 500

@app.route("/api/kraken/portfolio")
def kraken_portfolio():
    try:
        k = KrakenBroker()
        cash, positions = k.get_portfolio()
        return jsonify({"cash": round(cash, 2), "active_positions": len(positions), "total_equity": round(cash, 2), "positions": positions})
    except Exception as e:
        return jsonify({"error": str(e), "cash": 0.0, "positions": []}), 500

_t212_cache = {"ts": 0, "data": []}
@app.route("/api/search/t212")
def search_t212():
    q = request.args.get("q", "").strip().upper()
    if not q: return jsonify([])
    try:
        t212 = Trading212Broker(is_demo=True)
        now = time.time()
        if now - _t212_cache["ts"] > 600 or not _t212_cache["data"]:
            r = requests.get(f"{t212.base_url}/equity/metadata/instruments", headers=t212._headers(), timeout=10)
            if r.status_code == 200:
                _t212_cache["data"] = r.json()
                _t212_cache["ts"] = now
        matches = []
        for item in _t212_cache["data"]:
            if q in item.get("ticker", "").upper() or q in item.get("name", "").upper():
                matches.append({"ticker": item.get("ticker"), "name": item.get("name"), "currency": item.get("currencyCode", "USD"), "type": item.get("type", "EQUITY")})
                if len(matches) >= 10: break
        return jsonify(matches)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/search/binance")
def search_binance():
    q = request.args.get("q", "").strip().upper()
    if not q: return jsonify([])
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=5)
        matches = []
        for t in r.json():
            if q in t.get("symbol", ""):
                matches.append({"symbol": t.get("symbol"), "price": float(t.get("lastPrice", 0)), "change": float(t.get("priceChangePercent", 0)), "volume": float(t.get("volume", 0))})
                if len(matches) >= 10: break
        return jsonify(matches)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/search/kraken")
def search_kraken():
    q = request.args.get("q", "").strip().upper()
    if not q: return jsonify([])
    try:
        r = requests.get("https://api.kraken.com/0/public/AssetPairs", timeout=5)
        matches = []
        for p, data in r.json().get("result", {}).items():
            ws = data.get("wsname", p)
            if q in ws.upper() or q in p.upper():
                matches.append({"pair": p, "display": ws, "base": data.get("base"), "quote": data.get("quote"), "status": data.get("status", "online")})
                if len(matches) >= 10: break
        return jsonify(matches)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agent/query")
def agent_query():
    broker = request.args.get("broker", "t212").lower()
    symbol = request.args.get("symbol", "ETH").upper()
    prompts = {
        "t212": f"You are the Trading 212 Equities & ETF Agent. Evaluate {symbol} under the 200-day SMA macro regime and Dividend DCA rules. Hard stop-loss is -2.0%. Give action: BUY, SELL, or HOLD.",
        "etoro": f"You are the eToro Crypto Agent. Evaluate {symbol} using 1H RSI mean-reversion and FVG structures. Risk limit is $50 max allocation. Give action: BUY, SELL, or HOLD.",
        "binance": f"You are the Binance Spot Scalping Agent. Evaluate {symbol} using 5m high-frequency candlestick momentum and order book depth. Give action: BUY, SELL, or HOLD.",
        "kraken": f"You are the Kraken Spot Agent. Evaluate {symbol} for multi-currency swing spot accumulation. Give action: BUY, SELL, or HOLD.",
        "quantai": "You are QuantAI for MoneyMakingMachine - QWERTY CORP. Provide a concise cross-broker executive summary for Equities (T212) and Crypto (Binance/Kraken/eToro).",
        "price_action": f"You are the Institutional Price Action & Market Structure Agent. Evaluate {symbol} using swing pivot levels, liquidity sweeps, pinbar rejections, and break of structure (BOS). Identify key invalidation levels and 1:2 Risk/Reward targets. Give action: BUY, SELL, or HOLD."
    }
    timeout_val = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json={"model": "deepseek-r1:7b", "prompt": prompts.get(broker, prompts["t212"]), "stream": False}, timeout=timeout_val)
        return jsonify({"analysis": r.json().get("response", "")}) if r.status_code == 200 else jsonify({"error": f"Ollama HTTP {r.status_code}"}), 500
    except requests.exceptions.Timeout:
        return jsonify({"error": f"Ollama connection timed out (>{timeout_val}s) at {OLLAMA_URL}. Check Proxmox vmbr1 bridge or GPU queue."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 502

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
