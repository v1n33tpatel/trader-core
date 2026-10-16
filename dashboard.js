const brokerNames = {
  t212: "Trading 212",
  etoro: "eToro Quant Hub",
  binance: "Binance Spot",
  kraken: "Kraken Spot",
  quantai: "QuantAI",
};

const selectedBroker = document.querySelector(".broker-tab.is-active");
let currentBroker = selectedBroker?.dataset.broker || "t212";
const portfolioTitle = document.querySelector("#portfolio-title");
const refreshButton = document.querySelector("#refresh-button");
const refreshStatus = document.querySelector("#refresh-status");
const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#symbol-query");
const searchResults = document.querySelector("#search-results");
const watchlist = document.querySelector("#watchlist");
const watchlistItems = document.querySelector("#watchlist-items");
const watchlistCount = document.querySelector("#watchlist-count");
const agentForm = document.querySelector("#agent-form");
const agentQuery = document.querySelector("#agent-query");
const agentResponse = document.querySelector("#agent-response");
const agentResponseText = document.querySelector("#agent-response-text");
const watchlistSymbols = new Map();
const brokerSearchPaths = {
  t212: "/api/search/t212",
  etoro: "/api/search/binance",
  binance: "/api/search/binance",
  kraken: "/api/search/kraken",
};
const backtestForm = document.querySelector("#backtest-form");
const priceFile = document.querySelector("#price-file");
const runBacktestButton = document.querySelector("#run-backtest");
const backtestStatus = document.querySelector("#backtest-status");
const backtestResults = document.querySelector("#backtest-results");
const equityChart = document.querySelector("#equity-chart");
let latestBacktest = null;
const marketForm = document.querySelector("#market-form");
const marketProvider = document.querySelector("#market-provider");
const marketSymbol = document.querySelector("#market-symbol");
const marketInterval = document.querySelector("#market-interval");
const marketPeriod = document.querySelector("#market-period");
const marketLoadButton = document.querySelector("#load-market-data");
const marketStatus = document.querySelector("#market-status");
const marketSummary = document.querySelector("#market-summary");
const marketChartFrame = document.querySelector("#market-chart-frame");
const marketChart = document.querySelector("#market-chart");
let loadedMarketData = null;
let marketSelectionDirty = false;

const apiStatusNames = {
  dashboard: "Dashboard API",
  t212: "Trading 212 API",
  etoro: "eToro API",
  yahoo: "Yahoo Finance API",
  binance: "Binance API",
  kraken: "Kraken API",
  ollama: "Ollama API",
};

const annualizationByInterval = {
  yahoo: { "1d": 252, "1wk": 52, "1mo": 12, "1h": 1638, "30m": 3276, "15m": 6552 },
  binance: { "1m": 525600, "5m": 105120, "15m": 35040, "1h": 8760, "4h": 2190, "1d": 365, "1w": 52, "1M": 12 },
};

function selectedPeriodsPerYear() {
  const selected = document.querySelector("#periods-per-year").value;
  return selected === "auto"
    ? annualizationByInterval[marketProvider.value]?.[marketInterval.value] || 252
    : Number(selected);
}

async function refreshApiStatuses() {
  const updated = document.querySelector("#api-status-updated");
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) throw new Error("Status request failed");
    const statuses = await response.json();
    Object.entries(apiStatusNames).forEach(([key, label]) => {
      const indicator = document.querySelector(`[data-api-status="${key}"]`);
      const status = statuses[key]?.status || "offline";
      indicator.dataset.status = status;
      const stateLabel = status === "unconfigured" ? "not configured" : status;
      indicator.title = `${label}: ${stateLabel}`;
      indicator.setAttribute("aria-label", `${label}: ${stateLabel}`);
    });
    updated.textContent = `Checked ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  } catch {
    document.querySelectorAll("[data-api-status]").forEach((indicator) => {
      indicator.dataset.status = "offline";
      const label = apiStatusNames[indicator.dataset.apiStatus];
      indicator.title = `${label}: status unavailable`;
      indicator.setAttribute("aria-label", `${label}: status unavailable`);
    });
    updated.textContent = "Status unavailable";
  }
}

refreshApiStatuses();
window.setInterval(refreshApiStatuses, 60_000);

document.querySelectorAll(".broker-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    currentBroker = tab.dataset.broker;
    document.querySelectorAll(".broker-tab").forEach((item) => {
      const isActive = item === tab;
      item.classList.toggle("is-active", isActive);
      item.setAttribute("aria-selected", String(isActive));
    });

    const broker = brokerNames[currentBroker];
    portfolioTitle.textContent = `${broker} Portfolio`;
    document.querySelector(".button-refresh span:last-child").textContent = `Refresh ${broker.split(" ")[0]}`;
    document.querySelector("#search-title").textContent = currentBroker === "t212"
      ? "Search Stocks & ETFs"
      : currentBroker === "quantai" ? "Instrument Search" : `Search ${broker} Instruments`;
    document.querySelector("#search-button").innerHTML = `Search ${broker.split(" ")[0]} <span aria-hidden="true">→</span>`;
    document.querySelector("#agent-title").textContent = `${broker} Research Agent`;
    searchResults.hidden = true;
    loadPortfolio(currentBroker);
  });
});

refreshButton.addEventListener("click", () => {
  loadPortfolio(currentBroker);
});

async function loadPortfolio(broker) {
  if (broker === "quantai") {
    refreshStatus.textContent = "QuantAI is a research workspace and has no account portfolio.";
    renderPortfolio({ cash: 0, positions: [] }, broker);
    refreshButton.disabled = true;
    return;
  }

  const paths = {
    t212: "/api/t212/portfolio",
    etoro: "/api/etoro/portfolio",
    binance: "/api/binance/portfolio",
    kraken: "/api/kraken/portfolio",
  };
  refreshButton.disabled = false;
  refreshButton.classList.add("is-loading");
  refreshStatus.textContent = `Loading ${brokerNames[broker]} account snapshot...`;
  try {
    const response = await fetch(paths[broker]);
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || `Request failed (${response.status})`);
    renderPortfolio(data, broker);
    refreshStatus.textContent = `${brokerNames[broker]} account snapshot updated.`;
  } catch (error) {
    refreshStatus.textContent = error instanceof Error ? error.message : "Portfolio request failed.";
  } finally {
    refreshButton.classList.remove("is-loading");
  }
}

function renderPortfolio(data, broker) {
  const positions = Array.isArray(data.positions) ? data.positions : [];
  const cash = Number(data.cash ?? data.credit ?? 0);
  const invested = Number(data.total_invested ?? data.allocated ?? positions.reduce((sum, item) => sum + Number(item.invested ?? item.amount ?? 0), 0));
  const pnl = Number(data.unrealized_pnl ?? positions.reduce((sum, item) => sum + Number(item.ppl ?? item.netProfit ?? 0), 0));
  const equity = Number(data.total_equity ?? cash + invested + pnl);
  document.querySelector("#metric-cash").textContent = money(cash);
  document.querySelector("#metric-position-count").textContent = String(positions.length);
  document.querySelector("#metric-invested").textContent = money(invested);
  document.querySelector("#metric-pnl").textContent = signedMoney(pnl);
  document.querySelector("#metric-equity").textContent = money(equity);

  const tbody = document.querySelector(".holdings-table tbody");
  tbody.replaceChildren();
  if (positions.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 8;
    cell.className = "empty-cell";
    cell.textContent = "No active positions";
    row.append(cell);
    tbody.append(row);
    return;
  }

  positions.forEach((position) => {
    const symbol = position.ticker || position.symbol || position.display || "—";
    const openPrice = Number(position.open_price ?? position.openRate ?? 0);
    const amount = Number(position.invested ?? position.amount ?? (Number(position.units || 0) * openPrice));
    const positionPnl = Number(position.ppl ?? position.netProfit ?? 0);
    const pnlPercent = Number(position.ppl_pct ?? (amount > 0 ? positionPnl / amount * 100 : 0));
    const cells = [
      symbol,
      position.strategy || "—",
      Number(position.units || 0).toFixed(4),
      openPrice ? money(openPrice) : "—",
      amount ? money(amount) : "—",
      signedMoney(positionPnl),
      `${pnlPercent.toFixed(2)}%`,
      position.status || "ACTIVE",
    ];
    const row = document.createElement("tr");
    cells.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    tbody.append(row);
  });
  document.querySelector(".holdings-heading .eyebrow").innerHTML = `POSITIONS <span>·</span> ${String(positions.length).padStart(2, "0")}`;
  document.querySelector(".table-status").innerHTML = '<span class="status-dot"></span>ACCOUNT DATA';
}

function money(value) {
  return `$${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function signedMoney(value) {
  return `${value >= 0 ? "+" : "−"}${money(Math.abs(value))}`;
}

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await renderSearch(searchInput.value.trim());
});

async function renderSearch(query) {
  searchResults.replaceChildren();
  searchResults.hidden = false;

  if (!query) {
    renderSearchMessage("Enter a ticker or company name to search the local demo catalog.");
    return;
  }

  const endpoint = brokerSearchPaths[currentBroker];
  if (!endpoint) {
    renderSearchMessage("Choose a broker workspace to search its instrument catalog.");
    return;
  }

  let matches;
  try {
    const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`);
    matches = await response.json();
    if (!response.ok || !Array.isArray(matches)) throw new Error(matches.error || "Search request failed.");
  } catch (error) {
    renderSearchMessage(error instanceof Error ? error.message : "Instrument search failed.");
    return;
  }

  if (matches.length === 0) {
    renderSearchMessage(`No match for “${query}” in the local demo catalog.`);
    return;
  }

  matches.forEach((item) => {
    const tickerValue = item.ticker || item.symbol || item.display || item.pair || "—";
    const nameValue = item.name || item.display || item.pair || tickerValue;
    const row = document.createElement("div");
    row.className = "result-row";

    const ticker = document.createElement("span");
    ticker.className = "result-symbol";
    ticker.textContent = tickerValue;

    const name = document.createElement("span");
    name.className = "result-name";
    name.textContent = nameValue;

    const type = document.createElement("span");
    type.className = "result-type";
    type.textContent = item.type || item.currency || item.quote || (item.price ? money(item.price) : "INSTRUMENT");

    const addButton = document.createElement("button");
    addButton.type = "button";
    addButton.className = "watchlist-add";
    addButton.textContent = watchlistSymbols.has(tickerValue) ? "Added" : "Analyze";
    addButton.disabled = watchlistSymbols.has(tickerValue);
    addButton.addEventListener("click", () => {
      agentQuery.value = tickerValue;
      agentForm.requestSubmit();
    });

    row.append(ticker, name, type, addButton);
    searchResults.append(row);
  });
}

function renderSearchMessage(message) {
  const empty = document.createElement("p");
  empty.className = "search-empty";
  empty.textContent = message;
  searchResults.append(empty);
}

function renderWatchlist() {
  watchlistItems.replaceChildren();
  watchlist.hidden = watchlistSymbols.size === 0;
  watchlistCount.textContent = `${String(watchlistSymbols.size).padStart(2, "0")} ${watchlistSymbols.size === 1 ? "ITEM" : "ITEMS"}`;

  watchlistSymbols.forEach((item, ticker) => {
    const entry = document.createElement("div");
    entry.className = "watchlist-item";

    const symbol = document.createElement("span");
    symbol.className = "watchlist-symbol";
    symbol.textContent = ticker;

    const name = document.createElement("span");
    name.className = "watchlist-name";
    name.textContent = item.name;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "watchlist-remove";
    remove.setAttribute("aria-label", `Remove ${ticker} from watchlist`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      watchlistSymbols.delete(ticker);
      renderWatchlist();
      if (!searchResults.hidden && searchInput.value.trim()) renderSearch(searchInput.value.trim());
    });

    entry.append(symbol, name, remove);
    watchlistItems.append(entry);
  });
}

agentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = agentQuery.value.trim();
  if (!query) {
    agentQuery.focus();
    return;
  }

  agentResponse.hidden = false;
  const candidates = document.querySelector("#optimization-candidates");
  candidates.replaceChildren();
  agentResponseText.textContent = /optim|tune|parameter search/i.test(query)
    ? "Comparing settings on historical bars with a chronological validation segment..."
    : "Loading market data and requesting analysis...";
  const context = {
    provider: marketProvider.value,
    symbol: marketSymbol.value.trim().toUpperCase(),
    interval: marketInterval.value,
    period: marketPeriod.value,
    settings: currentStrategySettings(),
  };
  context.settings.periods_per_year = selectedPeriodsPerYear();
  try {
    const optimizing = /optim|tune|parameter search/i.test(query);
    const response = await fetch(optimizing ? "/api/research/optimize" : "/api/research/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(optimizing ? context : { ...context, question: query }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Research request failed (${response.status})`);
    if (optimizing) {
      renderOptimization(data);
    } else {
      let text = data.analysis || "The model returned an empty response.";
      if (data.price_action && data.price_action.trend) {
        const pa = data.price_action;
        const sh = pa.swing_high ? `$${Number(pa.swing_high).toFixed(2)}` : "—";
        const sl = pa.swing_low ? `$${Number(pa.swing_low).toFixed(2)}` : "—";
        const setup = pa.recent_pattern || (pa.sweep_detected ? `${pa.sweep_type} SWEEP` : "CONSOLIDATION");
        const inv = pa.suggested_sl ? `$${Number(pa.suggested_sl).toFixed(2)}` : "N/A";
        const tp = pa.suggested_tp ? `$${Number(pa.suggested_tp).toFixed(2)}` : "N/A";
        text = `[PRICE ACTION | TREND: ${String(pa.trend).toUpperCase()} | SETUP: ${setup} | INVALIDATION (SL): ${inv} | TARGET (TP): ${tp}]\n\n` + text;
      }
      agentResponseText.textContent = text;
    }
  } catch (error) {
    agentResponseText.textContent = error instanceof Error ? error.message : "Agent request failed.";
  }
});

function currentStrategySettings() {
  return {
    lookback: Number(document.querySelector("#lookback").value),
    volatility_window: Number(document.querySelector("#volatility-window").value),
    target_annual_volatility: Number(document.querySelector("#target-volatility").value),
    max_leverage: Number(document.querySelector("#max-leverage").value),
    one_way_cost_bps: Number(document.querySelector("#cost-bps").value),
    periods_per_year: selectedPeriodsPerYear(),
  };
}

function renderOptimization(result) {
  const baseline = result.baseline.validation;
  const candidates = document.querySelector("#optimization-candidates");
  agentResponseText.textContent = `${result.symbol} · ${result.observations} bars\n${result.objective}\nBaseline validation: return ${formatPercent(baseline.total_return)}, Sharpe ${formatNumber(baseline.sharpe_ratio)}, max drawdown ${formatPercent(baseline.max_drawdown)}.\nTop candidate settings (ranked on training data):`;
  result.candidates.forEach((candidate) => {
    const settings = candidate.settings;
    const validation = candidate.validation;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "candidate-button";
    button.textContent = `Load ${settings.lookback}/${settings.volatility_window} · OOS Sharpe ${formatNumber(validation.sharpe_ratio)}`;
    button.title = `Validation return ${formatPercent(validation.total_return)}, max drawdown ${formatPercent(validation.max_drawdown)}. Loads fields only; run a backtest to inspect.`;
    button.addEventListener("click", () => {
      document.querySelector("#lookback").value = String(settings.lookback);
      document.querySelector("#volatility-window").value = String(settings.volatility_window);
      document.querySelector("#target-volatility").value = String(settings.target_annual_volatility);
      backtestStatus.textContent = "Candidate settings loaded. Run a backtest to review them; no order was placed.";
      document.querySelector("#backtest-form").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    candidates.append(button);
  });
}

document.querySelectorAll(".prompt-button").forEach((button) => {
  button.addEventListener("click", () => {
    agentQuery.value = button.dataset.prompt;
    agentForm.requestSubmit();
  });
});

marketProvider.addEventListener("change", () => {
  invalidateMarketSnapshot();
  const intervals = marketProvider.value === "binance"
    ? [["1h", "1 hour"], ["4h", "4 hours"], ["1d", "1 day"], ["15m", "15 minutes"], ["5m", "5 minutes"]]
    : [["1d", "1 day"], ["1wk", "1 week"], ["1mo", "1 month"], ["1h", "1 hour"], ["30m", "30 minutes"], ["15m", "15 minutes"]];
  marketInterval.replaceChildren(...intervals.map(([value, label]) => new Option(label, value)));
  marketInterval.value = marketProvider.value === "binance" ? "1h" : "1d";
  marketSymbol.value = marketProvider.value === "binance" ? "BTCUSDT" : "SPY";
  updatePeriodOptions();
  loadedMarketData = null;
});

marketInterval.addEventListener("change", updatePeriodOptions);

function invalidateMarketSnapshot() {
  if (!loadedMarketData) return;
  loadedMarketData = null;
  marketSelectionDirty = true;
  marketStatus.textContent = "Market selection changed. Reload data before using it for analysis or backtesting.";
}

marketSymbol.addEventListener("input", invalidateMarketSnapshot);
marketInterval.addEventListener("change", invalidateMarketSnapshot);
marketPeriod.addEventListener("change", invalidateMarketSnapshot);

function updatePeriodOptions() {
  const daysByPeriod = { "3d": 3, "1w": 7, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825 };
  const minutesByInterval = { "1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1wk": 10080, "1mo": 43800 };
  const interval = marketInterval.value;
  const yahooIntraday = marketProvider.value === "yahoo" && ["15m", "30m", "1h"].includes(interval);
  const weeklyOrMonthly = (marketProvider.value === "yahoo" && ["1wk", "1mo"].includes(interval))
    || (marketProvider.value === "binance" && ["1w", "1M"].includes(interval));
  const minimumHistoryDays = interval === "1mo" || interval === "1M" ? 90 : weeklyOrMonthly ? 14 : 3;
  [...marketPeriod.options].forEach((option) => {
    const tooManyBars = marketProvider.value === "binance"
      && daysByPeriod[option.value] * 1440 / minutesByInterval[interval] > 5000;
    const yahooRangeTooLong = yahooIntraday && daysByPeriod[option.value] > 60;
    const tooShortForInterval = daysByPeriod[option.value] < minimumHistoryDays;
    option.disabled = yahooRangeTooLong || tooManyBars || tooShortForInterval;
  });
  if (marketPeriod.selectedOptions[0]?.disabled) {
    const available = [...marketPeriod.options]
      .filter((option) => !option.disabled)
      .sort((left, right) => daysByPeriod[right.value] - daysByPeriod[left.value])[0];
    if (available) marketPeriod.value = available.value;
  }
}

marketForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const symbol = marketSymbol.value.trim().toUpperCase();
  if (!symbol) return;
  marketLoadButton.disabled = true;
  marketStatus.textContent = `Fetching ${symbol} quote and historical bars...`;
  const params = new URLSearchParams({
    provider: marketProvider.value,
    symbol,
    interval: marketInterval.value,
    period: marketPeriod.value,
  });
  try {
    const response = await fetch(`/api/market/data?${params}`, { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Market-data request failed");
    loadedMarketData = result;
    marketSelectionDirty = false;
    renderMarketData(result);
    marketStatus.textContent = `Loaded ${result.bars.length.toLocaleString()} ${result.interval} bars from ${result.provider}.`;
  } catch (error) {
    marketStatus.textContent = error instanceof Error ? error.message : "Market-data request failed.";
  } finally {
    marketLoadButton.disabled = false;
  }
});

let binanceWebSocket = null;

function disconnectBinanceWebSocket() {
  if (binanceWebSocket) {
    try {
      binanceWebSocket.onclose = null;
      binanceWebSocket.onerror = null;
      binanceWebSocket.close();
    } catch (_) {}
    binanceWebSocket = null;
  }
  const badge = document.querySelector("#live-ws-badge");
  if (badge) badge.hidden = true;
}

function connectBinanceWebSocket(symbol, interval) {
  disconnectBinanceWebSocket();
  const badge = document.querySelector("#live-ws-badge");
  if (!badge) return;

  const rawSym = symbol.toUpperCase();
  const pair = rawSym.endsWith("USDT") ? rawSym.toLowerCase() : `${rawSym.toLowerCase()}usdt`;
  const klineInterval = interval || "1h";
  const wsUrl = `wss://stream.binance.com:9443/ws/${pair}@kline_${klineInterval}`;

  try {
    binanceWebSocket = new WebSocket(wsUrl);
    binanceWebSocket.onopen = () => {
      badge.hidden = false;
      badge.title = `Live WebSocket stream active: ${pair}@kline_${klineInterval}`;
    };
    binanceWebSocket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg && msg.k) {
          const k = msg.k;
          const currentPrice = Number(k.c);
          const quoteEl = document.querySelector("#market-quote");
          if (quoteEl && Number.isFinite(currentPrice)) {
            const oldPrice = parseFloat(quoteEl.textContent.replace(/[^0-9.]/g, ""));
            quoteEl.textContent = `${currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })} USDT`;
            if (oldPrice && currentPrice > oldPrice) {
              quoteEl.classList.remove("price-down");
              quoteEl.classList.add("price-up");
            } else if (oldPrice && currentPrice < oldPrice) {
              quoteEl.classList.remove("price-up");
              quoteEl.classList.add("price-down");
            }
          }
          if (loadedMarketData && loadedMarketData.bars && loadedMarketData.bars.length) {
            const lastBar = loadedMarketData.bars[loadedMarketData.bars.length - 1];
            lastBar.close = currentPrice;
            lastBar.high = Math.max(lastBar.high, Number(k.h));
            lastBar.low = Math.min(lastBar.low, Number(k.l));
            drawMarketChart(loadedMarketData.bars, loadedMarketData.liquidity);
          }
        }
      } catch (e) {
        console.error("Binance WS stream message error", e);
      }
    };
    binanceWebSocket.onerror = () => {
      badge.hidden = true;
    };
    binanceWebSocket.onclose = () => {
      badge.hidden = true;
    };
  } catch (e) {
    console.error("Binance WS stream connection error", e);
    badge.hidden = true;
  }
}

function renderMarketData(data) {
  const currency = data.quote.currency ? ` ${data.quote.currency}` : "";
  document.querySelector("#market-quote").textContent = `${Number(data.quote.price).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:6})}${currency}`;
  document.querySelector("#market-return").textContent = `${data.summary.period_return_pct >= 0 ? "+" : ""}${data.summary.period_return_pct.toFixed(2)}%`;
  document.querySelector("#market-as-of").textContent = new Date(data.quote.as_of).toLocaleString();
  document.querySelector("#market-source").textContent = `${data.symbol} · ${data.provider.toUpperCase()} · ${data.interval}`;
  document.querySelector("#market-chart-count").textContent = `${data.bars.length.toLocaleString()} BARS`;
  marketSummary.hidden = false;
  marketChartFrame.hidden = false;

  // Render Liquidity bar if available
  const liqBar = document.querySelector("#liquidity-bar");
  if (data.liquidity && data.liquidity.volume_profile && data.liquidity.volume_profile.poc) {
    const vp = data.liquidity.volume_profile;
    document.querySelector("#liq-poc").textContent = `$${Number(vp.poc).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.querySelector("#liq-vah").textContent = `$${Number(vp.vah).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.querySelector("#liq-val").textContent = `$${Number(vp.val).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

    const liqs = data.liquidity.liquidation_clusters?.short_liquidations || [];
    const firstLiq = liqs.length ? liqs[0] : null;
    document.querySelector("#liq-cluster").textContent = firstLiq ? `${firstLiq.leverage} @ $${Number(firstLiq.price).toFixed(1)}` : "None in range";

    const cmeGaps = data.liquidity.cme_gaps || [];
    const openGaps = cmeGaps.filter((g) => !g.filled);
    document.querySelector("#liq-cme").textContent = openGaps.length ? `${openGaps[0].direction} ($${openGaps[0].gap_size.toFixed(0)})` : "None";
    liqBar.hidden = false;
  } else {
    liqBar.hidden = true;
  }

  drawMarketChart(data.bars, data.liquidity);

  if (data.provider === "binance") {
    connectBinanceWebSocket(data.symbol, data.interval);
  } else {
    disconnectBinanceWebSocket();
  }
}

function drawMarketChart(bars, liquidity = null) {
  const bounds = marketChart.getBoundingClientRect();
  if (!bounds.width || !bars.length) return;
  const ratio = window.devicePixelRatio || 1;
  const width = bounds.width;
  const height = 150;
  marketChart.width = Math.round(width * ratio);
  marketChart.height = Math.round(height * ratio);
  const context = marketChart.getContext("2d");
  context.scale(ratio, ratio);
  context.clearRect(0, 0, width, height);

  const left = 56;
  const right = width - 12;
  const top = 10;
  const bottom = height - 22;
  const values = bars.map((bar) => Number(bar.close));
  let minimum = Math.min(...values);
  let maximum = Math.max(...values);
  if (minimum === maximum) { minimum -= 0.01; maximum += 0.01; }
  const padding = (maximum - minimum) * 0.1;
  minimum -= padding;
  maximum += padding;
  const xAt = (index) => left + (right - left) * index / Math.max(1, bars.length - 1);
  const yAt = (value) => bottom - (value - minimum) / (maximum - minimum) * (bottom - top);

  context.font = '9px "IBM Plex Mono", monospace';
  context.textAlign = "right";
  context.textBaseline = "middle";
  for (let line = 0; line <= 2; line += 1) {
    const y = top + (bottom - top) * line / 2;
    const value = maximum - (maximum - minimum) * line / 2;
    context.strokeStyle = "rgba(117, 139, 169, 0.18)";
    context.beginPath();
    context.moveTo(left, Math.round(y) + 0.5);
    context.lineTo(right, Math.round(y) + 0.5);
    context.stroke();
    context.fillStyle = "#8494ab";
    context.fillText(value.toFixed(2), left - 8, y);
  }

  // Draw Volume Profile levels if present
  const vp = liquidity?.volume_profile;
  if (vp && vp.poc >= minimum && vp.poc <= maximum) {
    // POC Line (Amber / Gold)
    const yPoc = Math.round(yAt(vp.poc)) + 0.5;
    context.strokeStyle = "rgba(240, 173, 61, 0.85)";
    context.lineWidth = 1.2;
    context.setLineDash([4, 4]);
    context.beginPath();
    context.moveTo(left, yPoc);
    context.lineTo(right, yPoc);
    context.stroke();
    context.fillStyle = "#f0ad3d";
    context.textAlign = "right";
    context.fillText(`POC $${vp.poc.toFixed(1)}`, right - 4, yPoc - 4);

    // VAH Line (Cyan)
    if (vp.vah >= minimum && vp.vah <= maximum) {
      const yVah = Math.round(yAt(vp.vah)) + 0.5;
      context.strokeStyle = "rgba(50, 214, 237, 0.65)";
      context.beginPath();
      context.moveTo(left, yVah);
      context.lineTo(right, yVah);
      context.stroke();
      context.fillStyle = "#32d6ed";
      context.fillText(`VAH $${vp.vah.toFixed(1)}`, right - 4, yVah - 4);
    }

    // VAL Line (Cyan)
    if (vp.val >= minimum && vp.val <= maximum) {
      const yVal = Math.round(yAt(vp.val)) + 0.5;
      context.strokeStyle = "rgba(50, 214, 237, 0.65)";
      context.beginPath();
      context.moveTo(left, yVal);
      context.lineTo(right, yVal);
      context.stroke();
      context.fillStyle = "#32d6ed";
      context.fillText(`VAL $${vp.val.toFixed(1)}`, right - 4, yVal + 10);
    }
    context.setLineDash([]);
  }

  context.beginPath();
  values.forEach((value, index) => {
    if (index === 0) context.moveTo(xAt(index), yAt(value));
    else context.lineTo(xAt(index), yAt(value));
  });
  context.strokeStyle = "#45d6e8";
  context.lineWidth = 1.7;
  context.lineJoin = "round";
  context.stroke();
  context.textAlign = "left";
  context.textBaseline = "alphabetic";
  context.fillStyle = "#8494ab";
  context.fillText(bars[0].time.slice(0, 10), left, height - 3);
  context.textAlign = "right";
  context.fillText(bars[bars.length - 1].time.slice(0, 10), right, height - 3);
}

priceFile.addEventListener("change", () => {
  const file = priceFile.files[0];
  backtestStatus.textContent = file
    ? `CSV selected · ${file.name}`
    : "Ready · uses synthetic demo prices unless a CSV is selected.";
});

backtestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  runBacktestButton.disabled = true;
  runBacktestButton.innerHTML = '<span aria-hidden="true">…</span> Running';
  backtestStatus.textContent = "Running the Python backtest...";

  try {
    const payload = {
      lookback: Number(document.querySelector("#lookback").value),
      volatility_window: Number(document.querySelector("#volatility-window").value),
      target_annual_volatility: Number(document.querySelector("#target-volatility").value),
      max_leverage: Number(document.querySelector("#max-leverage").value),
      one_way_cost_bps: Number(document.querySelector("#cost-bps").value),
      periods_per_year: selectedPeriodsPerYear(),
    };
    const file = priceFile.files[0];
    let sourceLabel = "SYNTHETIC SAMPLE";
    if (file) {
      payload.csv = await file.text();
      sourceLabel = "UPLOADED CSV";
    } else if (loadedMarketData) {
      payload.prices = loadedMarketData.bars.map((bar) => ({ date: bar.time, close: bar.close }));
      sourceLabel = `${loadedMarketData.symbol} · ${loadedMarketData.provider.toUpperCase()}`;
    } else if (marketSelectionDirty) {
      throw new Error("Market selection changed. Reload market data or choose a CSV before backtesting.");
    } else {
      const demoResponse = await fetch("/api/research/demo-prices");
      if (!demoResponse.ok) throw new Error("Unable to load synthetic demo prices");
      payload.prices = (await demoResponse.json()).prices;
    }

    const response = await fetch("/api/research/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Backtest request failed");

    latestBacktest = result;
    renderBacktest(result, sourceLabel);
    backtestStatus.textContent = `Completed · ${result.observations.toLocaleString()} observations · ${result.strategy}`;
  } catch (error) {
    backtestStatus.textContent = error instanceof Error
      ? error.message
      : "Backtest failed. Check the input and try again.";
  } finally {
    runBacktestButton.disabled = false;
    runBacktestButton.innerHTML = '<span aria-hidden="true">▶</span> Run backtest';
  }
});

function formatPercent(value) {
  return value === null || !Number.isFinite(value) ? "—" : `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value, digits = 2) {
  return value === null || !Number.isFinite(value) ? "—" : value.toFixed(digits);
}

function renderBacktest(result, sourceLabel) {
  const metrics = result.metrics;
  document.querySelector("#metric-total-return").textContent = formatPercent(metrics.total_return);
  document.querySelector("#metric-annualized-return").textContent = formatPercent(metrics.annualized_return);
  document.querySelector("#metric-sharpe").textContent = formatNumber(metrics.sharpe_ratio);
  document.querySelector("#metric-sortino").textContent = formatNumber(metrics.sortino_ratio);
  document.querySelector("#metric-calmar").textContent = formatNumber(metrics.calmar_ratio);
  document.querySelector("#metric-max-drawdown").textContent = formatPercent(metrics.max_drawdown);
  document.querySelector("#metric-volatility").textContent = formatPercent(metrics.annualized_volatility);
  document.querySelector("#result-period").textContent = `${result.start_date.slice(0, 10)} — ${result.end_date.slice(0, 10)}`;
  document.querySelector("#result-source").textContent = sourceLabel;
  document.querySelector("#result-observations").textContent = `${result.observations.toLocaleString()} BARS · ${result.curve.length} PLOT POINTS`;
  backtestResults.hidden = false;
  drawEquityCurve(result.curve);
}

function drawEquityCurve(points) {
  const bounds = equityChart.getBoundingClientRect();
  if (bounds.width === 0 || points.length === 0) return;

  const ratio = window.devicePixelRatio || 1;
  const width = bounds.width;
  const height = 218;
  equityChart.width = Math.round(width * ratio);
  equityChart.height = Math.round(height * ratio);
  const context = equityChart.getContext("2d");
  context.scale(ratio, ratio);
  context.clearRect(0, 0, width, height);

  const left = 54;
  const right = width - 12;
  const top = 12;
  const bottom = height - 25;
  const values = points.map((point) => point.equity);
  let minimum = Math.min(...values);
  let maximum = Math.max(...values);
  if (minimum === maximum) {
    minimum -= 0.01;
    maximum += 0.01;
  }
  const padding = (maximum - minimum) * 0.12;
  minimum -= padding;
  maximum += padding;
  const xAt = (index) => left + (right - left) * index / Math.max(1, points.length - 1);
  const yAt = (value) => bottom - (value - minimum) / (maximum - minimum) * (bottom - top);

  context.font = '9px "IBM Plex Mono", monospace';
  context.textAlign = "right";
  context.textBaseline = "middle";
  for (let line = 0; line <= 3; line += 1) {
    const y = top + (bottom - top) * line / 3;
    const value = maximum - (maximum - minimum) * line / 3;
    context.strokeStyle = "rgba(117, 139, 169, 0.18)";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(left, Math.round(y) + 0.5);
    context.lineTo(right, Math.round(y) + 0.5);
    context.stroke();
    context.fillStyle = "#8494ab";
    context.fillText(value.toFixed(2), left - 9, y);
  }

  context.beginPath();
  values.forEach((value, index) => {
    const x = xAt(index);
    const y = yAt(value);
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  });
  context.lineTo(right, bottom);
  context.lineTo(left, bottom);
  context.closePath();
  const fill = context.createLinearGradient(0, top, 0, bottom);
  fill.addColorStop(0, "rgba(50, 214, 237, 0.19)");
  fill.addColorStop(1, "rgba(50, 214, 237, 0.005)");
  context.fillStyle = fill;
  context.fill();

  context.beginPath();
  values.forEach((value, index) => {
    const x = xAt(index);
    const y = yAt(value);
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  });
  context.strokeStyle = "#45d6e8";
  context.lineWidth = 1.8;
  context.lineJoin = "round";
  context.lineCap = "round";
  context.stroke();

  context.textAlign = "left";
  context.textBaseline = "alphabetic";
  context.fillStyle = "#8494ab";
  context.fillText(points[0].date.slice(0, 10), left, height - 5);
  context.textAlign = "right";
  context.fillText(points[points.length - 1].date.slice(0, 10), right, height - 5);
}

window.addEventListener("resize", () => {
  if (latestBacktest) drawEquityCurve(latestBacktest.curve);
});

if (selectedBroker) {
  portfolioTitle.textContent = `${brokerNames[selectedBroker.dataset.broker]} Portfolio`;
}

loadPortfolio(currentBroker);

// --- Position Sizing & Kelly Calculator ---
function updateKellyCalculator() {
  const winRateEl = document.querySelector("#calc-win-rate");
  const winLossEl = document.querySelector("#calc-win-loss");
  const equityEl = document.querySelector("#calc-equity");
  const riskPctEl = document.querySelector("#calc-risk-pct");
  if (!winRateEl || !winLossEl || !equityEl || !riskPctEl) return;

  const winRate = Number(winRateEl.value) / 100.0;
  const winLoss = Number(winLossEl.value);
  const equity = Number(equityEl.value);
  const riskPct = Number(riskPctEl.value) / 100.0;

  // Kelly formula: f* = p - (1-p)/b
  let fStar = 0.0;
  if (winLoss > 0 && winRate > 0 && winRate < 1.0) {
    fStar = winRate - ((1.0 - winRate) / winLoss);
  }
  const fClamped = Math.max(0.0, Math.min(1.0, fStar));
  const halfKelly = fClamped * 0.5;

  const halfKellyUsd = equity * halfKelly;
  const fullKellyUsd = equity * fClamped;
  const maxRiskLoss = equity * riskPct;
  const expectancyR = (winRate * winLoss) - (1.0 - winRate);

  const halfEl = document.querySelector("#out-half-kelly");
  const halfUsdEl = document.querySelector("#out-half-kelly-usd");
  const fullEl = document.querySelector("#out-full-kelly");
  const fullUsdEl = document.querySelector("#out-full-kelly-usd");
  const riskEl = document.querySelector("#out-risk-loss");
  const expEl = document.querySelector("#out-expectancy");
  const edgeEl = document.querySelector("#out-edge-status");

  if (halfEl) halfEl.textContent = `${(halfKelly * 100).toFixed(1)}%`;
  if (halfUsdEl) halfUsdEl.textContent = `$${halfKellyUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (fullEl) fullEl.textContent = `${(fClamped * 100).toFixed(1)}%`;
  if (fullUsdEl) fullUsdEl.textContent = `$${fullKellyUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (riskEl) riskEl.textContent = `$${maxRiskLoss.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (expEl) expEl.textContent = `${expectancyR >= 0 ? "+" : ""}${expectancyR.toFixed(2)} R`;

  if (edgeEl) {
    if (expectancyR > 0) {
      edgeEl.textContent = "POSITIVE EDGE";
      edgeEl.className = "output-sub edge-positive";
    } else {
      edgeEl.textContent = "NEGATIVE EDGE";
      edgeEl.className = "output-sub edge-negative";
    }
  }
}

["#calc-win-rate", "#calc-win-loss", "#calc-equity", "#calc-risk-pct"].forEach((selector) => {
  const el = document.querySelector(selector);
  if (el) el.addEventListener("input", updateKellyCalculator);
});

const syncEquityBtn = document.querySelector("#calc-sync-equity");
if (syncEquityBtn) {
  syncEquityBtn.addEventListener("click", () => {
    const eqText = document.querySelector("#metric-equity")?.textContent || "";
    const parsed = parseFloat(eqText.replace(/[^0-9.]/g, ""));
    if (parsed && Number.isFinite(parsed) && parsed > 0) {
      const eqInput = document.querySelector("#calc-equity");
      if (eqInput) {
        eqInput.value = Math.round(parsed);
        updateKellyCalculator();
      }
    }
  });
}

updateKellyCalculator();