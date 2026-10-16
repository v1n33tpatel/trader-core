# Quant Trading Algos

A small Python framework for repeatable, offline strategy research. The initial implementation includes validated close-price input, a pluggable strategy protocol, a one-bar-lagged backtest engine, transaction-cost accounting, performance metrics, and a time-series momentum baseline.

The backtesting package is offline research software, not investment advice or a live trading system. It does not place orders or model market impact. The existing Flask dashboard retains its broker-data and Ollama integrations; those actions are separate from the backtester. Backtest output depends on data quality, execution assumptions, and parameter selection, and is not evidence of future performance.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows, activate the environment with `.venv\\Scripts\\activate`.

## Run the example

```bash
python examples/momentum_demo.py
```

The example uses deterministic synthetic prices to demonstrate the API. Replace them with a documented, point-in-time dataset before drawing any conclusions about a real market.

## Run tests

```bash
python -m pytest
```

## Minimal API

Pass a positive-valued `pandas.Series` indexed by unique, increasing timestamps to `BacktestEngine.run`. A strategy implements `target_positions(close)` and returns a `pandas.Series` of target exposures on the same index. By default, the engine assumes a signal is known at a close, fills at the next close, and starts earning the subsequent close-to-close return. It charges one-way costs on changes in exposure, including liquidation of any final open position, and reports net returns and metrics.

```python
from quant_trading import BacktestConfig, BacktestEngine, TimeSeriesMomentum

result = BacktestEngine(BacktestConfig(one_way_cost_bps=2.0)).run(
    close_prices,
    TimeSeriesMomentum(lookback=20, volatility_window=20),
)
print(result.metrics)
```

`periods_per_year` defaults to 252 and must be chosen to match the input frequency. The default Sharpe ratio uses a zero risk-free rate. `execution_delay_bars` defaults to 1 and cannot be set below 1 for close-only data. This timing convention is not a fill simulator. Configure costs for the instrument and venue being studied, and include spread, slippage, financing, borrow, or funding externally where relevant.

For the research workflow, data cautions, validation design, and known limitations, see [quant-trading-algos.md](quant-trading-algos.md).

## Dashboard

Run the existing Flask dashboard from the project root, bound to loopback:

```bash
python -m flask --app main run --host 127.0.0.1 --port 5000
```

Then open <http://127.0.0.1:5000>. The strategy panel calls the Python backtest engine using deterministic synthetic prices or an uploaded CSV with `date,close` columns. Broker refresh and agent actions use the existing Flask API routes. The dashboard does not submit orders.

The header checks dashboard, Trading 212, eToro, Yahoo Finance, Binance, Kraken, and Ollama API connectivity when the page opens and every 60 seconds. Checks are read-only; T212/eToro show `unconfigured` until their credential files are mounted in the container. The status response exposes only `online`, `offline`, or `unconfigured`, never credentials.

## Market Research Workflow

The Strategy Research panel can fetch Yahoo Finance equity/ETF history or Binance Spot crypto candles, display the provider's latest quote and timestamp, chart historical closes, and run the existing backtest against those bars. Yahoo Finance supports daily, weekly, and monthly history; intraday requests are limited to 60 days. Binance history is paginated and capped at 5,000 candles per request. The dashboard disables ranges that exceed these limits. Provider availability, symbol coverage, and quote delays vary; always check the displayed `DATA AS OF` time. This feature does not query Trading 212/eToro for historical bars.

The agent receives the selected symbol, provider, interval, quote, historical summary, recent OHLCV bars, and current strategy settings as context. “Optimize settings” compares a bounded time-series-momentum parameter grid, ranks candidates on the first 70% of history, and reports the remaining period separately as a chronological holdout validation. This is a single split, not repeated walk-forward validation. Selecting a candidate only fills the research controls; run a backtest and review results yourself. It never changes a live broker configuration or submits orders.

## Podman Deployment

The rootful system Quadlet definition is [`deploy/trader-dashboard-podman.container`](deploy/trader-dashboard-podman.container). Before rebuilding, sync the updated app from LGRAM to the LXC. Run this on LGRAM, not inside the SSH session:

```bash
cd /home/vineet/mnt/trader-core
scp main.py dashboard.html dashboard.css dashboard.js README.md Containerfile pyproject.toml trader:/home/vineet/trader-core/
scp -r src/quant_trading logo trader:/home/vineet/trader-core/
scp brokers/t212_adapter.py trader:/home/vineet/trader-core/brokers/
```

Then, inside the Arch Linux LXC, build into rootful Podman's image store and install the Quadlet:

```bash
sudo podman build --network=host -f Containerfile -t localhost/trader-core-dashboard:latest .
sudo install -D -m 0644 deploy/trader-dashboard-podman.container /etc/containers/systemd/trader-dashboard-podman.container
sudo systemctl daemon-reload
sudo systemctl cat trader-dashboard-podman.service
```

The `--network=host` build option avoids Podman's default `pasta` tap setup, which can fail inside an LXC without `/dev/net/tun`. Confirm the generated unit is present with `systemctl cat` before switching services. Quadlet-generated units cannot be enabled with `systemctl enable`; the `[Install]` section creates their boot dependency during `daemon-reload`, and the unit is started explicitly below.

The existing system service `trader-dashboard.service` owns port 5000. Stop and disable it before starting the container unit so the port is released and the old service does not reclaim it at boot:

```bash
sudo systemctl disable --now trader-dashboard.service
sudo systemctl start trader-dashboard-podman.service
```

The Quadlet has a distinct unit name and runs `python main.py`. After startup, open <http://192.168.2.220:5000>. To roll back, stop `trader-dashboard-podman.service`, then enable and start `trader-dashboard.service` again.

When syncing this workspace to the LXC, copy the `logo/` directory as well. From LGRAM, run `scp -r logo trader:/home/vineet/trader-core/`; the container image includes `logo/MonetMakingMachine-logo.jpg` and serves it through the dashboard app.

No credentials are copied into the image. The Quadlet mounts `/home/vineet/trader-core/.env` read-only at `/app/.env`; keep that host file restricted to the service owner. The T212 adapter reads only `T212_API_KEY` and `T212_API_SECRET` from it. To pass Binance/Kraken environment credentials, add an `EnvironmentFile=` entry pointing to a protected host file. `OLLAMA_HOST` defaults to `http://10.10.10.15:11434`.

The web server listens on all container interfaces, and the Quadlet publishes host port 5000 on all LXC interfaces so the existing LAN URL works. Restrict access with your network firewall; this is a Flask development server, not a hardened public-facing deployment. If startup fails in Proxmox, check that nesting is enabled for the LXC and inspect `sudo journalctl -u trader-dashboard-podman.service -b`.
