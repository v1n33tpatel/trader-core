const brokerNames = {
  t212: "Trading 212",
  etoro: "eToro Quant Hub",
  binance: "Binance Spot",
  kraken: "Kraken Spot",
  ctrader: "cTrader (Forex)",
  quantai: "QuantAI",
  admin: "Admin & Control",
  intel: "Market Intel (Agent C)",
  resources: "Resource Hub & RAG",
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

/* =========================================================================
   FLOATING TOAST HUD NOTIFICATION SYSTEM
   ========================================================================= */
function showToast(message, type = "info", durationMs = 3500) {
  const container = document.querySelector("#toast-hud");
  if (!container) return;

  const item = document.createElement("div");
  item.className = `toast-item is-${type}`;

  const iconMap = {
    success: "✓",
    warning: "⚠️",
    error: "✕",
    info: "⚡",
  };
  const icon = iconMap[type] || "ℹ️";

  item.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <div class="toast-content">${message}</div>
    <button type="button" class="toast-close" title="Dismiss">✕</button>
  `;

  item.querySelector(".toast-close")?.addEventListener("click", () => {
    item.classList.add("is-hiding");
    setTimeout(() => item.remove(), 200);
  });

  container.appendChild(item);

  setTimeout(() => {
    if (item.isConnected) {
      item.classList.add("is-hiding");
      setTimeout(() => item.remove(), 200);
    }
  }, durationMs);
}

/* =========================================================================
   WORKSPACE VIEW SWITCHER (FOCUS MODES)
   ========================================================================= */
let currentViewMode = localStorage.getItem("mmm_view_mode") || "workflow";

function applyWorkspaceViewMode(viewMode = currentViewMode) {
  currentViewMode = viewMode;
  try { localStorage.setItem("mmm_view_mode", viewMode); } catch (_) {}

  // Update switcher buttons active state
  document.querySelectorAll(".view-btn").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.view === viewMode);
  });

  // If in admin or intel mode, don't override special tabs
  if (currentBroker === "admin" || currentBroker === "intel") return;

  const portfolioPanel = document.querySelector(".portfolio-panel");
  const backtestPanel = document.querySelector(".backtest-panel");
  const sizingPanel = document.querySelector(".sizing-panel");
  const searchPanel = document.querySelector(".search-panel");
  const agentPanel = document.querySelector(".agent-panel");
  const wfCard = document.querySelector("#trade-workflow-card");
  const autoCard = document.querySelector("#automation-card");
  const metricsGrid = document.querySelector(".metrics-grid");
  const holdingsHeading = document.querySelector(".holdings-heading");
  const tableScroll = document.querySelector(".portfolio-panel .table-scroll");
  const footnote = document.querySelector("#refresh-status");

  // Form controls inside backtest panel
  const marketForm = document.querySelector("#market-form");
  const backtestForm = document.querySelector("#backtest-form");
  const backtestStatus = document.querySelector("#backtest-status");
  const backtestResults = document.querySelector("#backtest-results");
  const marketChartFrame = document.querySelector("#market-chart-frame");

  if (viewMode === "workflow") {
    // 🎯 WORKFLOW FOCUS:
    // Focus solely on the 8-Step Dual-Engine Workflow + Chart Preview
    if (portfolioPanel) {
      portfolioPanel.hidden = false;
      if (wfCard) wfCard.hidden = false;
      if (autoCard) autoCard.hidden = true;
      if (metricsGrid) metricsGrid.hidden = true;
      if (holdingsHeading) holdingsHeading.hidden = true;
      if (tableScroll) tableScroll.hidden = true;
      if (footnote) footnote.hidden = true;
    }

    if (backtestPanel) {
      backtestPanel.hidden = false;
      if (marketForm) marketForm.hidden = true;
      if (backtestForm) backtestForm.hidden = true;
      if (backtestStatus) backtestStatus.hidden = true;
      if (backtestResults) backtestResults.hidden = true;
      if (marketChartFrame) marketChartFrame.hidden = false;
    }

    if (sizingPanel) sizingPanel.hidden = true;
    if (searchPanel) searchPanel.hidden = true;
    if (agentPanel) agentPanel.hidden = true;

  } else if (viewMode === "portfolio") {
    // 📊 PORTFOLIO & EXECUTION:
    // Show portfolio panel (metrics, holdings, automation card), hide workflow & research forms
    if (portfolioPanel) {
      portfolioPanel.hidden = false;
      if (wfCard) wfCard.hidden = true;
      if (autoCard) autoCard.hidden = false;
      if (metricsGrid) metricsGrid.hidden = false;
      if (holdingsHeading) holdingsHeading.hidden = false;
      if (tableScroll) tableScroll.hidden = false;
      if (footnote) footnote.hidden = false;
    }

    if (backtestPanel) backtestPanel.hidden = true;
    if (sizingPanel) sizingPanel.hidden = true;
    if (searchPanel) searchPanel.hidden = true;
    if (agentPanel) agentPanel.hidden = true;

  } else if (viewMode === "quantlab") {
    // 🔬 QUANT LAB & CHARTS:
    // Show full backtest panel, chart, volume profile, equity curve, and Kelly calculator
    if (portfolioPanel) portfolioPanel.hidden = true;

    if (backtestPanel) {
      backtestPanel.hidden = false;
      if (marketForm) marketForm.hidden = false;
      if (backtestForm) backtestForm.hidden = false;
      if (backtestStatus) backtestStatus.hidden = false;
      if (marketChartFrame) marketChartFrame.hidden = false;
    }
    if (sizingPanel) sizingPanel.hidden = false;
    if (searchPanel) searchPanel.hidden = true;
    if (agentPanel) agentPanel.hidden = true;

  } else {
    // 🌐 ALL PANELS (Continuous layout)
    if (portfolioPanel) {
      portfolioPanel.hidden = false;
      if (wfCard) wfCard.hidden = false;
      if (autoCard) autoCard.hidden = false;
      if (metricsGrid) metricsGrid.hidden = false;
      if (holdingsHeading) holdingsHeading.hidden = false;
      if (tableScroll) tableScroll.hidden = false;
      if (footnote) footnote.hidden = false;
    }
    if (backtestPanel) {
      backtestPanel.hidden = false;
      if (marketForm) marketForm.hidden = false;
      if (backtestForm) backtestForm.hidden = false;
      if (backtestStatus) backtestStatus.hidden = false;
      if (marketChartFrame) marketChartFrame.hidden = false;
    }
    if (sizingPanel) sizingPanel.hidden = false;
    if (searchPanel) searchPanel.hidden = false;
    if (agentPanel) agentPanel.hidden = false;
  }
}

// Bind workspace view switcher buttons
document.querySelectorAll(".view-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    applyWorkspaceViewMode(btn.dataset.view);
    const modeLabels = {
      workflow: "🎯 8-Step Workflow Focus",
      portfolio: "📊 Portfolio Hub",
      quantlab: "🔬 Quant Lab & Charts",
      all: "🌐 Continuous Layout (All Panels)",
    };
    showToast(`View mode: ${modeLabels[btn.dataset.view] || btn.dataset.view}`, "info", 1500);
  });
});

const BROKER_WATCHLIST_DEFAULTS = {
  t212: [
    { symbol: "AAPL", name: "Apple Inc.", type: "STOCK", sentiment: "+0.45", bias: "BULLISH" },
    { symbol: "NVDA", name: "NVIDIA Corp.", type: "STOCK", sentiment: "+0.65", bias: "BULLISH" },
    { symbol: "MSFT", name: "Microsoft Corp.", type: "STOCK", sentiment: "+0.32", bias: "BULLISH" },
    { symbol: "SPY", name: "SPDR S&P 500 ETF", type: "ETF", sentiment: "+0.35", bias: "BULLISH" },
    { symbol: "QQQ", name: "Invesco QQQ Trust", type: "ETF", sentiment: "+0.40", bias: "BULLISH" },
    { symbol: "VUKE", name: "Vanguard FTSE 100 ETF", type: "ETF", sentiment: "+0.15", bias: "NEUTRAL" },
    { symbol: "VUSA", name: "Vanguard S&P 500 ETF", type: "ETF", sentiment: "+0.38", bias: "BULLISH" },
  ],
  binance: [
    { symbol: "BTCUSDT", name: "Bitcoin / USDT", type: "CRYPTO", sentiment: "+0.55", bias: "BULLISH" },
    { symbol: "ETHUSDT", name: "Ethereum / USDT", type: "CRYPTO", sentiment: "+0.35", bias: "BULLISH" },
    { symbol: "SOLUSDT", name: "Solana / USDT", type: "CRYPTO", sentiment: "+0.48", bias: "BULLISH" },
    { symbol: "BNBUSDT", name: "BNB / USDT", type: "CRYPTO", sentiment: "+0.20", bias: "NEUTRAL" },
    { symbol: "DOGEUSDT", name: "Dogecoin / USDT", type: "CRYPTO", sentiment: "-0.10", bias: "NEUTRAL" },
    { symbol: "AVAXUSDT", name: "Avalanche / USDT", type: "CRYPTO", sentiment: "+0.25", bias: "BULLISH" },
  ],
  ctrader: [
    { symbol: "EURUSD", name: "Euro / US Dollar", type: "FOREX", sentiment: "+0.18", bias: "BULLISH" },
    { symbol: "GBPUSD", name: "British Pound / USD", type: "FOREX", sentiment: "+0.22", bias: "BULLISH" },
    { symbol: "USDJPY", name: "US Dollar / Japanese Yen", type: "FOREX", sentiment: "-0.25", bias: "BEARISH" },
    { symbol: "AUDUSD", name: "Australian Dollar / USD", type: "FOREX", sentiment: "+0.10", bias: "NEUTRAL" },
    { symbol: "XAUUSD", name: "Gold / US Dollar", type: "COMMODITY", sentiment: "+0.60", bias: "BULLISH" },
    { symbol: "USOIL", name: "WTI Crude Oil", type: "COMMODITY", sentiment: "+0.05", bias: "NEUTRAL" },
  ],
  etoro: [
    { symbol: "ETH", name: "Ethereum", type: "CRYPTO", sentiment: "+0.35", bias: "BULLISH" },
    { symbol: "BTC", name: "Bitcoin", type: "CRYPTO", sentiment: "+0.55", bias: "BULLISH" },
    { symbol: "SPY", name: "S&P 500 ETF", type: "ETF", sentiment: "+0.35", bias: "BULLISH" },
  ],
  kraken: [
    { symbol: "BTCUSD", name: "Bitcoin / USD", type: "CRYPTO", sentiment: "+0.55", bias: "BULLISH" },
    { symbol: "ETHUSD", name: "Ethereum / USD", type: "CRYPTO", sentiment: "+0.35", bias: "BULLISH" },
    { symbol: "SOLUSD", name: "Solana / USD", type: "CRYPTO", sentiment: "+0.48", bias: "BULLISH" },
  ],
};

function getBrokerWatchlist(broker) {
  try {
    const raw = localStorage.getItem(`mmm_watchlist_${broker}`);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  return BROKER_WATCHLIST_DEFAULTS[broker] || BROKER_WATCHLIST_DEFAULTS.t212;
}

function saveBrokerWatchlist(broker, items) {
  try {
    localStorage.setItem(`mmm_watchlist_${broker}`, JSON.stringify(items));
  } catch (_) {}
}

function addToBrokerWatchlist(broker, item) {
  const list = getBrokerWatchlist(broker);
  if (!list.some((x) => x.symbol === item.symbol)) {
    list.unshift(item);
    saveBrokerWatchlist(broker, list);
  }
}

function removeFromBrokerWatchlist(broker, symbol) {
  const list = getBrokerWatchlist(broker).filter((x) => x.symbol !== symbol);
  saveBrokerWatchlist(broker, list);
}

function isSymbolInBrokerWatchlist(broker, symbol) {
  return getBrokerWatchlist(broker).some((x) => x.symbol === symbol);
}

const brokerSearchPaths = {
  t212: "/api/search/t212",
  etoro: "/api/search/binance",
  binance: "/api/search/binance",
  kraken: "/api/search/kraken",
  ctrader: "/api/search/ctrader",
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
  ctrader: "cTrader API",
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

    const adminPanel = document.querySelector("#admin-panel");
    const intelPanel = document.querySelector("#intel-panel");
    const resourcesPanel = document.querySelector("#panel-resources");
    const standardPanels = document.querySelectorAll(
      ".portfolio-panel, .backtest-panel, .sizing-panel, .search-panel, .agent-panel"
    );

    if (currentBroker === "admin") {
      standardPanels.forEach((p) => (p.hidden = true));
      if (intelPanel) intelPanel.hidden = true;
      if (resourcesPanel) resourcesPanel.hidden = true;
      if (adminPanel) {
        adminPanel.hidden = false;
        loadAdminData();
        if (typeof loadAuditLedger === "function") loadAuditLedger();
      }
      return;
    }

    if (currentBroker === "intel") {
      standardPanels.forEach((p) => (p.hidden = true));
      if (adminPanel) adminPanel.hidden = true;
      if (resourcesPanel) resourcesPanel.hidden = true;
      if (intelPanel) {
        intelPanel.hidden = false;
        loadMarketIntel(currentIntelSymbol);
      }
      return;
    }

    if (currentBroker === "resources") {
      standardPanels.forEach((p) => (p.hidden = true));
      if (adminPanel) adminPanel.hidden = true;
      if (intelPanel) intelPanel.hidden = true;
      if (resourcesPanel) {
        resourcesPanel.hidden = false;
        loadResourcesHub();
      }
      return;
    }

    if (adminPanel) adminPanel.hidden = true;
    if (intelPanel) intelPanel.hidden = true;
    if (resourcesPanel) resourcesPanel.hidden = true;
    applyWorkspaceViewMode();

    const broker = brokerNames[currentBroker];
    portfolioTitle.textContent = `${broker} Portfolio`;
    document.querySelector(".button-refresh span:last-child").textContent = `Refresh ${broker.split(" ")[0]}`;
    // Tailored Search Headings & Placeholders
    if (currentBroker === "t212") {
      document.querySelector("#search-title").innerHTML = "Search Stocks <span class='heading-amp'>&amp;</span> ETFs · Equities";
      searchInput.placeholder = "Search stocks & ETFs (e.g. VUKE, VUSA, AAPL, NVDA, SPY, Apple)...";
      document.querySelector("#search-button").innerHTML = "Search T212 Stocks <span aria-hidden='true'>→</span>";
    } else if (currentBroker === "binance") {
      document.querySelector("#search-title").innerHTML = "Search Crypto Assets · Binance Spot &amp; Alts";
      searchInput.placeholder = "Search crypto pairs (e.g. BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT)...";
      document.querySelector("#search-button").innerHTML = "Search Binance Crypto <span aria-hidden='true'>→</span>";
    } else if (currentBroker === "ctrader") {
      document.querySelector("#search-title").innerHTML = "Search Forex Pairs <span class='heading-amp'>&amp;</span> Commodities";
      searchInput.placeholder = "Search currency pairs & metals (e.g. EURUSD, GBPUSD, USDJPY, XAUUSD)...";
      document.querySelector("#search-button").innerHTML = "Search cTrader Forex <span aria-hidden='true'>→</span>";
    } else {
      document.querySelector("#search-title").textContent = `Search ${broker} Instruments`;
      searchInput.placeholder = "Search by ticker or name...";
      document.querySelector("#search-button").innerHTML = `Search ${broker.split(" ")[0]} <span aria-hidden="true">→</span>`;
    }

    document.querySelector("#agent-title").textContent = `${broker} Research Agent`;
    searchResults.hidden = true;
    renderWatchlist();
    if (typeof renderWorkflowChips === "function") renderWorkflowChips(currentBroker);
    loadPortfolio(currentBroker);
    showToast(`Switched to ${broker}`, "info", 1800);
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
    ctrader: "/api/ctrader/portfolio",
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

    const actions = document.createElement("div");
    actions.className = "result-actions";

    // 1. Add to Watchlist Button
    const inWatchlist = isSymbolInBrokerWatchlist(currentBroker, tickerValue);
    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "btn-add-watchlist";
    addBtn.textContent = inWatchlist ? "✓ Added" : "+ Watchlist";
    addBtn.disabled = inWatchlist;
    addBtn.addEventListener("click", () => {
      let inferredType = "STOCK";
      if (currentBroker === "binance" || currentBroker === "kraken") inferredType = "CRYPTO";
      else if (currentBroker === "ctrader") inferredType = tickerValue.includes("XAU") ? "COMMODITY" : "FOREX";
      else if (tickerValue.includes("ETF") || ["SPY", "QQQ", "VUKE", "VUSA"].includes(tickerValue)) inferredType = "ETF";

      addToBrokerWatchlist(currentBroker, {
        symbol: tickerValue,
        name: nameValue,
        type: item.type || inferredType,
        sentiment: "+0.35",
        bias: "BULLISH",
      });
      addBtn.textContent = "✓ Added";
      addBtn.disabled = true;
      renderWatchlist();
    });

    // 2. Step Into 8-Step Workflow Button
    const wfBtn = document.createElement("button");
    wfBtn.type = "button";
    wfBtn.className = "btn-step-workflow";
    wfBtn.innerHTML = "<span>⚡ Step into Workflow</span>";
    wfBtn.title = `Launch 8-Step Quantitative Pipeline for ${tickerValue}`;
    wfBtn.addEventListener("click", () => {
      loadWorkflowRecommendation(tickerValue);
      document.querySelector("#trade-workflow-card")?.scrollIntoView({ behavior: "smooth" });
    });

    actions.append(addBtn, wfBtn);
    row.append(ticker, name, type, actions);
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
  if (!watchlistItems) return;
  watchlistItems.replaceChildren();

  const titleEl = document.querySelector("#watchlist-heading-title");
  if (titleEl) {
    if (currentBroker === "t212") titleEl.textContent = "STOCKS & ETFS WATCHLIST";
    else if (currentBroker === "binance") titleEl.textContent = "CRYPTO ASSETS WATCHLIST";
    else if (currentBroker === "ctrader") titleEl.textContent = "FOREX & COMMODITIES WATCHLIST";
    else if (currentBroker === "kraken") titleEl.textContent = "KRAKEN CRYPTO WATCHLIST";
    else titleEl.textContent = `${(brokerNames[currentBroker] || "BROKER").toUpperCase()} WATCHLIST`;
  }

  const items = getBrokerWatchlist(currentBroker);
  if (watchlist) watchlist.hidden = false;
  if (watchlistCount) {
    watchlistCount.textContent = `${String(items.length).padStart(2, "0")} ${items.length === 1 ? "ITEM" : "ITEMS"}`;
  }

  if (!items.length) {
    const emptyP = document.createElement("p");
    emptyP.className = "search-empty";
    emptyP.textContent = "Your watchlist is empty. Search instruments above and click '+ Watchlist' to pin them.";
    watchlistItems.append(emptyP);
    return;
  }

  items.forEach((item) => {
    const entry = document.createElement("div");
    entry.className = "watchlist-item";

    const symbolSpan = document.createElement("span");
    symbolSpan.className = "watchlist-symbol";
    symbolSpan.textContent = item.symbol;

    const nameSpan = document.createElement("span");
    nameSpan.className = "watchlist-name";
    nameSpan.textContent = `${item.name} · ${item.type || "ASSET"}`;

    const sentPill = document.createElement("span");
    const isBull = (item.sentiment || "").startsWith("+") || item.bias === "BULLISH";
    sentPill.className = `badge ${isBull ? "badge-strat" : "badge-bear"}`;
    sentPill.textContent = `${item.sentiment || "+0.35"} ${item.bias || "BULL"}`;

    const actionsDiv = document.createElement("div");
    actionsDiv.className = "watchlist-row-actions";

    // 1-Click Workflow Button
    const btnWf = document.createElement("button");
    btnWf.type = "button";
    btnWf.className = "btn-step-workflow-mini";
    btnWf.innerHTML = "<span>⚡ Workflow</span>";
    btnWf.title = `Step ${item.symbol} into the 8-Step Quantitative Pipeline`;
    btnWf.addEventListener("click", () => {
      loadWorkflowRecommendation(item.symbol);
      document.querySelector("#trade-workflow-card")?.scrollIntoView({ behavior: "smooth" });
    });

    // Analyze Button
    const btnAnalyze = document.createElement("button");
    btnAnalyze.type = "button";
    btnAnalyze.className = "watchlist-analyze";
    btnAnalyze.textContent = "Analyze";
    btnAnalyze.title = `Analyze ${item.symbol} with AI Research Agent`;
    btnAnalyze.addEventListener("click", () => {
      agentQuery.value = item.symbol;
      agentForm.requestSubmit();
      document.querySelector("#agent-response")?.scrollIntoView({ behavior: "smooth" });
    });

    // Remove Button
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "watchlist-remove";
    removeBtn.setAttribute("aria-label", `Remove ${item.symbol} from watchlist`);
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", () => {
      removeFromBrokerWatchlist(currentBroker, item.symbol);
      renderWatchlist();
      if (!searchResults.hidden && searchInput.value.trim()) renderSearch(searchInput.value.trim());
    });

    actionsDiv.append(btnWf, btnAnalyze, removeBtn);
    entry.append(symbolSpan, nameSpan, sentPill, actionsDiv);
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
let binanceL2WebSocket = null;

function disconnectBinanceWebSocket() {
  if (binanceWebSocket) {
    try {
      binanceWebSocket.onclose = null;
      binanceWebSocket.onerror = null;
      binanceWebSocket.close();
    } catch (_) {}
    binanceWebSocket = null;
  }
  if (binanceL2WebSocket) {
    try {
      binanceL2WebSocket.onclose = null;
      binanceL2WebSocket.onerror = null;
      binanceL2WebSocket.close();
    } catch (_) {}
    binanceL2WebSocket = null;
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
  const wsKlineUrl = `wss://stream.binance.com:9443/ws/${pair}@kline_${klineInterval}`;
  const wsL2Url = `wss://stream.binance.com:9443/ws/${pair}@depth10@100ms`;

  try {
    binanceWebSocket = new WebSocket(wsKlineUrl);
    binanceWebSocket.onopen = () => {
      badge.hidden = false;
      badge.title = `Live WebSocket stream active: ${pair}@kline_${klineInterval} + sub-second L2 @depth10@100ms`;
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

    // Sub-Second Level 2 Orderbook Stream (@depth10@100ms)
    binanceL2WebSocket = new WebSocket(wsL2Url);
    binanceL2WebSocket.onmessage = (event) => {
      try {
        const l2 = JSON.parse(event.data);
        const bids = l2.bids || [];
        const asks = l2.asks || [];
        if (bids.length && asks.length) {
          const sumBids = bids.reduce((acc, b) => acc + parseFloat(b[1]), 0);
          const sumAsks = asks.reduce((acc, a) => acc + parseFloat(a[1]), 0);
          const total = sumBids + sumAsks;
          const obi = total > 0 ? (sumBids - sumAsks) / total : 0;
          const bestBid = parseFloat(bids[0][0]);
          const bestAsk = parseFloat(asks[0][0]);
          const spreadBps = bestBid > 0 ? ((bestAsk - bestBid) / bestBid) * 10000 : 0;

          const liqCluster = document.querySelector("#liq-cluster");
          if (liqCluster) {
            const bias = obi > 0.15 ? "BID ABSORPTION" : obi < -0.15 ? "ASK DUMPING" : "BALANCED";
            liqCluster.textContent = `L2 OBI: ${(obi * 100).toFixed(0)}% [${bias}]`;
            liqCluster.className = obi > 0.15 ? "color-green" : obi < -0.15 ? "color-red" : "color-cyan";
            liqCluster.title = `Top 10 Bids: ${sumBids.toFixed(2)} | Asks: ${sumAsks.toFixed(2)} | Spread: ${spreadBps.toFixed(1)} bps`;
          }
        }
      } catch (_) {}
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

  // Draw Structural Trade Geometry Overlays (Entry, Stop Loss, Take Profit, 50% CE / 200 SMA)
  const chkOverlays = document.querySelector("#chk-chart-overlays");
  if ((!chkOverlays || chkOverlays.checked) && typeof wfCurrentData !== "undefined" && wfCurrentData?.step_6_parameters) {
    const p = wfCurrentData.step_6_parameters;
    const s4 = wfCurrentData.step_4_analyze;
    const entry = Number(p.entry_price || 0);
    const sl = Number(p.stop_loss || 0);
    const tp = Number(p.take_profit || 0);
    const ce = Number(s4?.consequent_encroachment || s4?.sma_200 || 0);

    // 1. 50% CE / 200 SMA (Purple dashed)
    if (ce >= minimum && ce <= maximum) {
      const yCe = Math.round(yAt(ce)) + 0.5;
      context.strokeStyle = "rgba(168, 85, 247, 0.85)";
      context.lineWidth = 1.2;
      context.setLineDash([3, 3]);
      context.beginPath();
      context.moveTo(left, yCe);
      context.lineTo(right, yCe);
      context.stroke();
      context.fillStyle = "#c084fc";
      context.textAlign = "left";
      context.fillText(`${wfCurrentData.asset_class === "ETF" ? "200 SMA" : "50% CE"} $${ce.toFixed(2)}`, left + 4, yCe - 4);
    }

    // 2. Entry Price (Emerald Green dashed)
    if (entry >= minimum && entry <= maximum) {
      const yEntry = Math.round(yAt(entry)) + 0.5;
      context.strokeStyle = "rgba(16, 185, 129, 0.9)";
      context.lineWidth = 1.5;
      context.setLineDash([5, 4]);
      context.beginPath();
      context.moveTo(left, yEntry);
      context.lineTo(right, yEntry);
      context.stroke();
      context.fillStyle = "#10b981";
      context.textAlign = "right";
      context.fillText(`ENTRY $${entry.toFixed(2)}`, right - 4, yEntry - 4);
    }

    // 3. Stop Loss (Coral Red solid)
    if (sl >= minimum && sl <= maximum) {
      const ySl = Math.round(yAt(sl)) + 0.5;
      context.strokeStyle = "rgba(239, 68, 68, 0.9)";
      context.lineWidth = 1.5;
      context.setLineDash([]);
      context.beginPath();
      context.moveTo(left, ySl);
      context.lineTo(right, ySl);
      context.stroke();
      context.fillStyle = "#f87171";
      context.textAlign = "right";
      context.fillText(`SL $${sl.toFixed(2)} (-${p.risk_pct}%)`, right - 4, ySl + 10);
    }

    // 4. Take Profit (Lime Green solid)
    if (tp >= minimum && tp <= maximum) {
      const yTp = Math.round(yAt(tp)) + 0.5;
      context.strokeStyle = "rgba(34, 197, 94, 0.9)";
      context.lineWidth = 1.5;
      context.setLineDash([]);
      context.beginPath();
      context.moveTo(left, yTp);
      context.lineTo(right, yTp);
      context.stroke();
      context.fillStyle = "#4ade80";
      context.textAlign = "right";
      context.fillText(`TARGET $${tp.toFixed(2)} (1:${p.risk_reward_ratio} R:R)`, right - 4, yTp - 4);
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

/* =========================================================================
   1. REAL VS. DEMO ACCOUNT SWITCHER
   ========================================================================= */
async function initEnvironmentSwitcher() {
  const btnDemo = document.querySelector("#btn-env-demo");
  const btnReal = document.querySelector("#btn-env-real");
  const badge = document.querySelector("#env-badge");
  const modal = document.querySelector("#real-mode-modal");
  const btnCancel = document.querySelector("#btn-modal-cancel");
  const btnConfirm = document.querySelector("#btn-modal-confirm");

  function setEnvUI(env) {
    const isDemo = env === "demo";
    if (btnDemo) btnDemo.classList.toggle("is-active", isDemo);
    if (btnReal) btnReal.classList.toggle("is-active", !isDemo);
    if (badge) {
      badge.textContent = isDemo ? "PRACTICE (SAFE)" : "REAL CAPITAL (LIVE)";
      badge.className = isDemo ? "env-badge env-badge-demo" : "env-badge env-badge-real";
    }
  }

  try {
    const res = await fetch("/api/environment/mode");
    const data = await res.json();
    setEnvUI(data.environment || "demo");
  } catch (e) {
    setEnvUI("demo");
  }

  if (btnDemo) {
    btnDemo.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/environment/mode", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ environment: "demo" }),
        });
        const data = await res.json();
        setEnvUI(data.environment || "demo");
        if (currentBroker !== "admin") loadPortfolio(currentBroker);
      } catch (err) {
        console.error("Failed to switch to demo mode:", err);
      }
    });
  }

  if (btnReal) {
    btnReal.addEventListener("click", () => {
      if (modal) modal.hidden = false;
    });
  }

  if (btnCancel) {
    btnCancel.addEventListener("click", () => {
      if (modal) modal.hidden = true;
    });
  }

  if (btnConfirm) {
    btnConfirm.addEventListener("click", async () => {
      if (modal) modal.hidden = true;
      try {
        const res = await fetch("/api/environment/mode", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ environment: "real" }),
        });
        const data = await res.json();
        setEnvUI(data.environment || "real");
        if (currentBroker !== "admin") loadPortfolio(currentBroker);
      } catch (err) {
        console.error("Failed to switch to real mode:", err);
      }
    });
  }
}

/* =========================================================================
   2. AUTOMATION & SELECTABLE STRATEGIES
   ========================================================================= */
async function initAutomationAndStrategies() {
  const stratSelect = document.querySelector("#auto-strategy-select");
  const modePills = document.querySelectorAll(".mode-pill");
  const activeBadge = document.querySelector("#active-mode-badge");
  const autoCardTitle = document.querySelector("#auto-card-title");
  const btnToggle = document.querySelector("#btn-auto-toggle");
  const toggleText = document.querySelector("#auto-toggle-text");
  const toggleIcon = document.querySelector("#auto-toggle-icon");
  const autoDot = document.querySelector("#auto-status-dot");
  const autoIndicator = document.querySelector("#auto-status-indicator");
  const quickModeLbl = document.querySelector("#auto-mode-label");
  const quickStateLbl = document.querySelector("#auto-state-label");
  const quickPill = document.querySelector("#auto-quick-pill");
  const btnEval = document.querySelector("#btn-auto-eval");
  const telemetryText = document.querySelector("#auto-telemetry-text");

  // Load Strategy Catalog
  try {
    const res = await fetch("/api/strategies");
    const data = await res.json();
    if (data.strategies && stratSelect) {
      stratSelect.innerHTML = "";
      data.strategies.forEach((strat) => {
        const opt = document.createElement("option");
        opt.value = strat.id;
        opt.textContent = `${strat.name} (${strat.execution_mode.toUpperCase()})`;
        if (strat.id === data.active_strategy) opt.selected = true;
        stratSelect.appendChild(opt);
      });
    }
  } catch (err) {
    console.warn("Could not load strategies catalog:", err);
  }

  // Load Automation Status
  async function refreshAutomationStatus() {
    try {
      const res = await fetch("/api/automation/status");
      const data = await res.json();
      const isRunning = Boolean(data.is_running);
      const mode = data.mode || "reactive";

      if (autoDot) autoDot.classList.toggle("is-running", isRunning);
      if (autoIndicator) autoIndicator.classList.toggle("is-running", isRunning);
      if (btnToggle) btnToggle.classList.toggle("is-running", isRunning);
      if (toggleText) toggleText.textContent = isRunning ? "Pause Automation" : "Start Automation";
      if (toggleIcon) toggleIcon.textContent = isRunning ? "⏸" : "▶";
      if (quickStateLbl) quickStateLbl.textContent = isRunning ? "ACTIVE" : "PAUSED";
      if (quickModeLbl) quickModeLbl.textContent = mode.toUpperCase();

      if (activeBadge) {
        activeBadge.textContent = mode.toUpperCase();
        activeBadge.className = `mode-badge mode-badge-${mode}`;
      }
      if (autoCardTitle) {
        autoCardTitle.textContent = mode === "reactive"
          ? "Reactive Price Action Engine"
          : mode === "predictive" ? "Predictive Quant Momentum Engine" : "Hybrid Macro-Structural Engine";
      }

      modePills.forEach((p) => {
        p.classList.toggle("is-active", p.dataset.mode === mode);
      });

      if (data.guardrails) {
        const maxO = document.querySelector("#auto-max-order");
        const stopL = document.querySelector("#auto-stop-loss");
        const rr = document.querySelector("#auto-rr-target");
        const sigs = document.querySelector("#auto-signals-count");
        if (maxO) maxO.textContent = `$${data.guardrails.max_order_usd.toFixed(2)}`;
        if (stopL) stopL.textContent = `-${data.guardrails.stop_loss_pct.toFixed(1)}%`;
        if (rr) rr.textContent = `1:${data.guardrails.min_risk_reward.toFixed(1)}`;
        if (sigs) sigs.textContent = String(data.signals_generated || 0);
      }
    } catch (err) {
      console.warn("Could not load automation status:", err);
    }
  }

  refreshAutomationStatus();

  // Strategy change handler
  if (stratSelect) {
    stratSelect.addEventListener("change", async () => {
      try {
        await fetch("/api/strategies/select", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strategy_id: stratSelect.value }),
        });
        refreshAutomationStatus();
      } catch (e) {
        console.error("Failed to select strategy:", e);
      }
    });
  }

  // Mode pill handler
  modePills.forEach((pill) => {
    pill.addEventListener("click", async () => {
      const mode = pill.dataset.mode;
      try {
        await fetch("/api/automation/configure", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode }),
        });
        refreshAutomationStatus();
      } catch (e) {
        console.error("Failed to set automation mode:", e);
      }
    });
  });

  // Toggle run handler
  if (btnToggle) {
    btnToggle.addEventListener("click", async () => {
      try {
        await fetch("/api/automation/toggle", { method: "POST" });
        refreshAutomationStatus();
      } catch (e) {
        console.error("Failed to toggle automation:", e);
      }
    });
  }

  // Quick pill scroll
  if (quickPill) {
    quickPill.addEventListener("click", () => {
      const card = document.querySelector("#automation-card");
      if (card) {
        if (currentBroker === "admin") {
          document.querySelector("#tab-t212")?.click();
        }
        card.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  // Evaluate handler
  if (btnEval) {
    btnEval.addEventListener("click", async () => {
      if (telemetryText) telemetryText.textContent = "Running evaluation on current bar...";
      try {
        const symbol = document.querySelector("#market-symbol")?.value || "ETH";
        const res = await fetch("/api/automation/evaluate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol }),
        });
        const evalData = await res.json();
        if (telemetryText) {
          telemetryText.textContent = `[${evalData.action}] ${evalData.symbol} @ $${evalData.current_price?.toFixed(2)} | Setup: ${evalData.pattern || "N/A"} | ${evalData.reason || ""}`;
        }
        refreshAutomationStatus();
      } catch (e) {
        if (telemetryText) telemetryText.textContent = `Evaluation failed: ${e.message}`;
      }
    });
  }
}

/* =========================================================================
   3. ADMIN WORKSPACE & TELEMETRY
   ========================================================================= */
async function loadAdminData() {
  // Load Masked Keys
  try {
    const res = await fetch("/api/admin/keys");
    const data = await res.json();
    if (data.t212) {
      const elK = document.querySelector("#hint-t212-key");
      const elS = document.querySelector("#hint-t212-sec");
      if (elK) elK.textContent = data.t212.key_preview ? `Current: ${data.t212.key_preview}` : "Current: Not configured";
      if (elS) elS.textContent = data.t212.has_secret ? "Current: •••••••• (Configured)" : "Current: Not configured";
    }
    if (data.etoro) {
      const elK = document.querySelector("#hint-etoro-key");
      const elS = document.querySelector("#hint-etoro-sec");
      if (elK) elK.textContent = data.etoro.key_preview ? `Current: ${data.etoro.key_preview}` : "Current: Not configured";
      if (elS) elS.textContent = data.etoro.has_secret ? "Current: •••••••• (Configured)" : "Current: Not configured";
    }
    if (data.binance) {
      const elK = document.querySelector("#hint-binance-key");
      const elS = document.querySelector("#hint-binance-sec");
      if (elK) elK.textContent = data.binance.key_preview ? `Current: ${data.binance.key_preview}` : "Current: Not configured";
      if (elS) elS.textContent = data.binance.has_secret ? "Current: •••••••• (Configured)" : "Current: Not configured";
    }
    if (data.kraken) {
      const elK = document.querySelector("#hint-kraken-key");
      const elS = document.querySelector("#hint-kraken-sec");
      if (elK) elK.textContent = data.kraken.key_preview ? `Current: ${data.kraken.key_preview}` : "Current: Not configured";
      if (elS) elS.textContent = data.kraken.has_secret ? "Current: •••••••• (Configured)" : "Current: Not configured";
    }
    if (data.ctrader) {
      const elId = document.querySelector("#hint-ctrader-id");
      const elS = document.querySelector("#hint-ctrader-sec");
      const elAcc = document.querySelector("#hint-ctrader-acc");
      const elTok = document.querySelector("#hint-ctrader-tok");
      if (elId) elId.textContent = data.ctrader.key_preview ? `Current: ${data.ctrader.key_preview}` : "Current: Not configured";
      if (elS) elS.textContent = data.ctrader.has_secret ? "Current: •••••••• (Configured)" : "Current: Not configured";
      if (elAcc) elAcc.textContent = data.ctrader.account_id ? `Current: ${data.ctrader.account_id}` : "Current: Not configured";
      if (elTok) elTok.textContent = data.ctrader.has_secret ? "Current: •••••••• (Configured)" : "Current: Not configured";
    }
  } catch (err) {
    console.warn("Failed to load admin keys:", err);
  }

  // Load AI Configuration
  try {
    const res = await fetch("/api/admin/ai-config");
    const data = await res.json();
    const sel = document.querySelector("#ai-provider-select");
    const url = document.querySelector("#ai-base-url");
    const mod = document.querySelector("#ai-model-name");
    const fb = document.querySelector("#ai-fallback-local");
    const hint = document.querySelector("#hint-ai-key");
    const provExt = document.querySelector("#prov-extai");

    if (sel && data.provider) sel.value = data.provider;
    if (url && data.external_base_url) url.value = data.external_base_url;
    if (mod && data.external_model) mod.value = data.external_model;
    if (fb && data.fallback_to_local !== undefined) fb.checked = Boolean(data.fallback_to_local);
    if (hint) hint.textContent = data.has_api_key ? `Current: ${data.api_key_preview || "•••••••• (Configured)"}` : "Current: Not configured";
    if (provExt) provExt.textContent = data.provider === "external" ? `${data.external_model || "External AI"}` : "Local Ollama";
  } catch (err) {
    console.warn("Failed to load AI config:", err);
  }

  // Load Agent Telemetry
  try {
    const res = await fetch("/api/admin/agents");
    const data = await res.json();
    if (data.agents) {
      const engineAgent = data.agents.find((a) => a.id === "engine_loop");
      if (engineAgent) {
        const dot = document.querySelector("#engine-dot");
        const badge = document.querySelector("#engine-state-badge");
        const isRun = engineAgent.status === "running";
        if (dot) {
          dot.className = isRun ? "status-dot status-dot-online" : "status-dot";
        }
        if (badge) {
          badge.textContent = engineAgent.status.toUpperCase();
          badge.className = isRun ? "agent-state-badge" : "agent-state-badge agent-state-standby";
        }
      }
    }
  } catch (err) {
    console.warn("Failed to load agents telemetry:", err);
  }

  // Run initial latency probe
  testAdminConnections();
}

async function testAdminConnections() {
  try {
    const res = await fetch("/api/admin/test-connection", { method: "POST" });
    const data = await res.json();
    if (data.services) {
      Object.entries(data.services).forEach(([svc, info]) => {
        const statEl = document.querySelector(`#stat-${svc}`);
        const latEl = document.querySelector(`#lat-${svc}`);
        const dot = document.querySelector(`#dot-${svc}`);
        if (statEl) statEl.textContent = info.status.toUpperCase();
        if (latEl) latEl.textContent = `${info.latency_ms} ms`;
        if (dot) {
          dot.className = info.status === "online" ? "api-dot is-online" : "api-dot is-offline";
        }
      });
    }
  } catch (err) {
    console.warn("Connection test failed:", err);
  }
}

function initAdminWorkspace() {
  // Password Visibility Toggle
  document.querySelectorAll(".btn-toggle-vis").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      const input = document.getElementById(targetId);
      if (input) {
        const isPass = input.type === "password";
        input.type = isPass ? "text" : "password";
        btn.textContent = isPass ? "🔒" : "👁";
      }
    });
  });

  // Keys form submit
  const formKeys = document.querySelector("#form-admin-keys");
  const saveKeysStatus = document.querySelector("#save-keys-status");
  if (formKeys) {
    formKeys.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (saveKeysStatus) saveKeysStatus.textContent = "Saving credentials...";
      const payload = {
        T212_API_KEY: document.querySelector("#key-t212-val")?.value || "",
        T212_API_SECRET: document.querySelector("#sec-t212-val")?.value || "",
        ETORO_API_KEY: document.querySelector("#key-etoro-val")?.value || "",
        ETORO_USER_KEY: document.querySelector("#sec-etoro-val")?.value || "",
        BINANCE_API_KEY: document.querySelector("#key-binance-val")?.value || "",
        BINANCE_API_SECRET: document.querySelector("#sec-binance-val")?.value || "",
        KRAKEN_API_KEY: document.querySelector("#key-kraken-val")?.value || "",
        KRAKEN_API_SECRET: document.querySelector("#sec-kraken-val")?.value || "",
        CTRADER_CLIENT_ID: document.querySelector("#key-ctrader-id")?.value || "",
        CTRADER_CLIENT_SECRET: document.querySelector("#sec-ctrader-val")?.value || "",
        CTRADER_ACCOUNT_ID: document.querySelector("#acc-ctrader-val")?.value || "",
        CTRADER_ACCESS_TOKEN: document.querySelector("#tok-ctrader-val")?.value || "",
      };

      try {
        const res = await fetch("/api/admin/keys", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (saveKeysStatus) {
          saveKeysStatus.textContent = `✓ Credentials saved (${data.updated_keys?.length || 0} updated)`;
        }
        loadAdminData();
      } catch (err) {
        if (saveKeysStatus) saveKeysStatus.textContent = `Error: ${err.message}`;
      }
    });
  }

  // Test All APIs button
  const btnTestApis = document.querySelector("#btn-test-all-apis");
  if (btnTestApis) {
    btnTestApis.addEventListener("click", testAdminConnections);
  }

  // Refresh Agents button
  const btnRefreshAgents = document.querySelector("#btn-refresh-agents");
  if (btnRefreshAgents) {
    btnRefreshAgents.addEventListener("click", loadAdminData);
  }

  // AI Test button
  const btnTestAi = document.querySelector("#btn-test-ai");
  const aiTestStatus = document.querySelector("#ai-test-status");
  if (btnTestAi) {
    btnTestAi.addEventListener("click", async () => {
      if (aiTestStatus) aiTestStatus.textContent = "Pinging AI provider...";
      const payload = {
        provider: document.querySelector("#ai-provider-select")?.value || "ollama",
        base_url: document.querySelector("#ai-base-url")?.value || "",
        model: document.querySelector("#ai-model-name")?.value || "",
        api_key: document.querySelector("#ai-api-key")?.value || "",
      };
      try {
        const res = await fetch("/api/admin/ai-test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (aiTestStatus) {
          if (data.status === "online") {
            aiTestStatus.textContent = `✓ Online (${data.latency_ms} ms) - ${data.detail || ""}`;
          } else {
            aiTestStatus.textContent = `✗ ${data.status.toUpperCase()}: ${data.detail || "Connection failed"}`;
          }
        }
      } catch (err) {
        if (aiTestStatus) aiTestStatus.textContent = `Failed: ${err.message}`;
      }
    });
  }

  // AI Save form
  const formAi = document.querySelector("#form-ai-config");
  if (formAi) {
    formAi.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (aiTestStatus) aiTestStatus.textContent = "Saving AI settings...";
      const payload = {
        provider: document.querySelector("#ai-provider-select")?.value || "ollama",
        external_base_url: document.querySelector("#ai-base-url")?.value || "",
        external_model: document.querySelector("#ai-model-name")?.value || "",
        external_api_key: document.querySelector("#ai-api-key")?.value || "",
        fallback_to_local: document.querySelector("#ai-fallback-local")?.checked ?? true,
      };
      try {
        const res = await fetch("/api/admin/ai-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (aiTestStatus) aiTestStatus.textContent = "✓ AI configuration saved";
        loadAdminData();
      } catch (err) {
        if (aiTestStatus) aiTestStatus.textContent = `Error: ${err.message}`;
      }
    });
  }
}

// Initialize New Modules on Page Load
initEnvironmentSwitcher();
initAutomationAndStrategies();
initAdminWorkspace();
initMarketIntel();
initOrchestratorAdmin();

// ==========================================================================
// AGENT C: MARKET INTELLIGENCE TERMINAL LOGIC
// ==========================================================================

let currentIntelSymbol = "ETH";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function initMarketIntel() {
  const btnRefresh = document.querySelector("#btn-refresh-intel");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      loadMarketIntel(currentIntelSymbol);
    });
  }

  // Symbol selector buttons
  document.querySelectorAll(".intel-sym-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".intel-sym-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      currentIntelSymbol = btn.dataset.sym || "ETH";
      loadMarketIntel(currentIntelSymbol);
    });
  });

  // Prompt suggestions for Agent C
  document.querySelectorAll(".agent-c-prompt-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.querySelector("#agent-c-query-input");
      if (input && btn.dataset.prompt) {
        input.value = btn.dataset.prompt;
        input.focus();
      }
    });
  });

  // Agent C Form Query
  const formAgentC = document.querySelector("#agent-c-form");
  if (formAgentC) {
    formAgentC.addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.querySelector("#agent-c-query-input");
      const question = input?.value.trim() || "";
      const respBox = document.querySelector("#agent-c-response");
      const respText = document.querySelector("#agent-c-response-text");
      const respMeta = document.querySelector("#agent-c-response-meta");
      const submitBtn = document.querySelector("#btn-agent-c-query");

      if (respBox) respBox.hidden = false;
      if (respText) respText.textContent = "Agent C (Grok) is synthesizing live market telemetry...";
      if (respMeta) respMeta.textContent = "";
      if (submitBtn) submitBtn.disabled = true;

      try {
        const res = await fetch("/api/agent-c/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol: currentIntelSymbol, question }),
        });
        if (!res.ok) throw new Error(`Query failed (HTTP ${res.status})`);
        const data = await res.json();
        if (respText) respText.textContent = data.briefing || "No response received.";
        if (respMeta) {
          respMeta.textContent = `Provider: ${data.provider_used || "xai/grok"} · Model: ${data.model || "grok-2-latest"} · Latency: ${Math.round(data.latency_ms || 0)}ms`;
        }
      } catch (err) {
        if (respText) respText.textContent = `Error consulting Agent C: ${err.message}`;
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }
}

async function loadMarketIntel(symbol = "ETH") {
  const sym = symbol.toUpperCase();
  try {
    const res = await fetch(`/api/agent-c/intel?symbol=${encodeURIComponent(sym)}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`Intel fetch failed (HTTP ${res.status})`);
    const data = await res.json();
    renderMarketIntel(data);
  } catch (err) {
    console.error("Failed to load Agent C market intel:", err);
  }
}

function renderMarketIntel(data) {
  if (!data) return;
  const { social, calendar, news, company } = data;

  // 1. Topline Sentiment
  if (social) {
    const badge = document.querySelector("#intel-sentiment-badge");
    const fill = document.querySelector("#intel-sentiment-fill");
    const bullPct = document.querySelector("#intel-bull-pct");
    const bearPct = document.querySelector("#intel-bear-pct");
    const velocity = document.querySelector("#intel-velocity");

    const score = social.sentiment_score ?? 0;
    const sign = score > 0 ? "+" : "";
    if (badge) {
      badge.textContent = `${sign}${score.toFixed(2)} ${social.sentiment_label || "NEUTRAL"}`;
      badge.className = "sentiment-score-badge " + (score > 0.15 ? "" : score < -0.15 ? "is-bearish" : "is-neutral");
    }

    if (fill) {
      const pct = Math.max(0, Math.min(100, Math.round(((score + 1) / 2) * 100)));
      fill.style.width = `${pct}%`;
    }

    if (bullPct) bullPct.textContent = `Bulls: ${social.bull_percentage}%`;
    if (bearPct) bearPct.textContent = `Bears: ${social.bear_percentage}%`;
    if (velocity && social.mention_velocity_hr) {
      velocity.textContent = Number(social.mention_velocity_hr).toLocaleString();
    }

    // Render Chat Stream
    const chatContainer = document.querySelector("#chat-stream-container");
    if (chatContainer && Array.isArray(social.chatter_stream)) {
      chatContainer.innerHTML = social.chatter_stream.map((c) => {
        const isDiscord = (c.source || "").toLowerCase().includes("discord");
        const sentClass = (c.sentiment || "NEUTRAL").toLowerCase();
        return `
          <div class="chat-card">
            <div class="chat-card-top">
              <div>
                <span class="chat-source-tag ${isDiscord ? "discord" : ""}">${escapeHtml(c.source || "Social")}</span>
                <span class="chat-user">${escapeHtml(c.user || "")}</span>
              </div>
              <span class="chat-time">${escapeHtml(c.time || "")}</span>
            </div>
            <div class="chat-text">${escapeHtml(c.text || "")}</div>
            <div class="chat-card-bottom">
              <span class="sentiment-pill ${sentClass}">${escapeHtml(c.sentiment || "NEUTRAL")}</span>
            </div>
          </div>
        `;
      }).join("");
    }

    // Whale Alerts
    const whaleBox = document.querySelector("#whale-alerts-box");
    if (whaleBox) {
      if (Array.isArray(social.whale_alerts) && social.whale_alerts.length > 0) {
        whaleBox.innerHTML = social.whale_alerts.map((w) => `
          <div class="whale-card">
            <div>
              <strong>🐋 WHALE ${escapeHtml(w.type || "FLOW")}:</strong>
              <span>${escapeHtml(w.amount || "")} ${escapeHtml(w.asset || "")} — ${escapeHtml(w.detail || "")}</span>
            </div>
            <span class="sentiment-pill ${w.impact === "BEARISH" ? "bearish" : "bullish"}">${escapeHtml(w.impact || "INFO")}</span>
          </div>
        `).join("");
      } else {
        whaleBox.innerHTML = "";
      }
    }
  }

  // 2. Macro Event Risk & Calendar
  if (calendar) {
    const riskPill = document.querySelector("#intel-event-risk-pill");
    const countdown = document.querySelector("#intel-event-countdown");
    const sentinelStatus = document.querySelector("#intel-risk-sentinel-status");
    const advisoryText = document.querySelector("#calendar-advisory-text");
    const advisoryBox = document.querySelector("#calendar-advisory-box");

    const level = calendar.event_risk_level || "LOW";
    if (riskPill) {
      riskPill.textContent = `${level} EVENT RISK`;
      riskPill.className = "event-risk-pill " + (level === "HIGH" ? "risk-high" : level === "MEDIUM" ? "risk-medium" : "");
    }

    if (countdown && calendar.next_tier1_event) {
      const next = calendar.next_tier1_event;
      const mins = next.minutes_away || 0;
      const hours = Math.floor(mins / 60);
      const remMins = mins % 60;
      const timeStr = hours > 0 ? `${hours}h ${remMins}m` : `${remMins}m`;
      countdown.textContent = `Next: ${next.event} (in ${timeStr})`;
    }

    if (sentinelStatus) {
      if (level === "HIGH") {
        sentinelStatus.className = "risk-sentinel-status halted";
        sentinelStatus.innerHTML = '<span class="sentinel-dot"></span>RiskSentinel: EVENT RISK HALT ACTIVE';
      } else {
        sentinelStatus.className = "risk-sentinel-status";
        sentinelStatus.innerHTML = '<span class="sentinel-dot"></span>RiskSentinel: CLEAR TO TRADE';
      }
    }

    if (advisoryText && calendar.risk_advisory) {
      advisoryText.textContent = calendar.risk_advisory;
    }
    if (advisoryBox) {
      advisoryBox.className = "calendar-advisory-box " + (level === "HIGH" ? "advisory-high" : "");
    }

    // Calendar Table
    const tbody = document.querySelector("#calendar-table-body");
    if (tbody && Array.isArray(calendar.events)) {
      tbody.innerHTML = calendar.events.map((ev) => {
        const impClass = (ev.impact || "LOW").toLowerCase();
        return `
          <tr>
            <td class="event-name">${escapeHtml(ev.event || "")}</td>
            <td class="event-time">${escapeHtml(ev.release_time || "")}</td>
            <td class="event-val">${escapeHtml(ev.forecast || "—")}</td>
            <td class="event-val">${escapeHtml(ev.previous || "—")}</td>
            <td><span class="impact-pill impact-${impClass}">${escapeHtml(ev.impact || "LOW")}</span></td>
          </tr>
        `;
      }).join("");
    }
  }

  // 3. Breaking News Feeds
  if (Array.isArray(news)) {
    const newsContainer = document.querySelector("#news-stream-container");
    if (newsContainer) {
      newsContainer.innerHTML = news.map((item) => {
        const sentClass = (item.sentiment || "NEUTRAL").toLowerCase();
        const impClass = (item.impact || "LOW").toLowerCase();
        const symTags = Array.isArray(item.symbols)
          ? item.symbols.map((s) => `<span class="news-sym-tag">${escapeHtml(s)}</span>`).join("")
          : "";
        return `
          <div class="news-card">
            <div class="news-topline">
              <span class="news-source">${escapeHtml(item.source || "Newswire")}</span>
              <span class="news-time">${escapeHtml(item.timestamp || "")}</span>
            </div>
            <div class="news-title">${escapeHtml(item.title || "")}</div>
            <div class="news-summary">${escapeHtml(item.summary || "")}</div>
            <div class="news-bottomline">
              <div class="news-symbols">${symTags}</div>
              <div style="display:flex;gap:4px;">
                <span class="sentiment-pill ${sentClass}">${escapeHtml(item.sentiment || "NEUTRAL")}</span>
                <span class="impact-pill impact-${impClass}">${escapeHtml(item.impact || "LOW")}</span>
              </div>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  // 4. Company Fundamentals
  if (company) {
    const badge = document.querySelector("#company-symbol-badge");
    if (badge) badge.textContent = data.symbol || "EQUITY";

    const setField = (id, val) => {
      const el = document.querySelector(id);
      if (el) el.textContent = (val !== null && val !== undefined && val !== "") ? String(val) : "—";
    };

    setField("#fund-name", company.name);
    setField("#fund-sector", company.sector);
    setField("#fund-mcap", company.market_cap);
    setField("#fund-pe", company.pe_ratio ? `${company.pe_ratio}x` : "N/A");
    setField("#fund-fpe", company.forward_pe ? `${company.forward_pe}x` : "N/A");
    setField("#fund-eps", company.eps ? `$${company.eps}` : "N/A");
    setField("#fund-beta", company.beta ? String(company.beta) : "N/A");
    setField("#fund-range", company.range_52w);
    setField("#fund-div", company.dividend_yield);
    setField("#fund-earnings", company.next_earnings_date);
  }

  // 5. Engine / Grok Badge
  const engineBadge = document.querySelector("#agent-c-engine-badge");
  if (engineBadge) {
    const prov = (data.provider_used || "grok").toUpperCase();
    engineBadge.innerHTML = `<span class="status-dot"></span>${prov} READY`;
  }
}

// ==========================================================================
// AI ORCHESTRATOR (OLLAMA / OPEN-WEBUI) ADMIN LOGIC
// ==========================================================================

function initOrchestratorAdmin() {
  const typeSelect = document.querySelector("#orch-type-select");
  const baseUrlInput = document.querySelector("#orch-base-url");
  const modelInput = document.querySelector("#orch-model-name");
  const apiKeyInput = document.querySelector("#orch-api-key");
  const testBtn = document.querySelector("#btn-test-orchestrator");
  const testStatus = document.querySelector("#orch-test-status");
  const formOrch = document.querySelector("#form-orchestrator-config");
  const copyToolBtn = document.querySelector("#btn-copy-owui-tool");

  if (typeSelect && baseUrlInput) {
    typeSelect.addEventListener("change", () => {
      if (typeSelect.value === "ollama") {
        if (!baseUrlInput.value || baseUrlInput.value.includes("8080") || baseUrlInput.value.includes("3000")) {
          baseUrlInput.value = "http://10.10.10.15:11434";
        }
      } else if (typeSelect.value === "open_webui") {
        if (!baseUrlInput.value || baseUrlInput.value.includes("11434")) {
          baseUrlInput.value = "http://192.168.2.15:8080";
        }
      }
    });
  }

  if (testBtn) {
    testBtn.addEventListener("click", async () => {
      if (testStatus) testStatus.textContent = "Probing orchestrator host...";
      try {
        const res = await fetch("/api/orchestrator/status", { cache: "no-store" });
        const data = await res.json();
        if (testStatus) {
          if (data.status === "online") {
            testStatus.textContent = `✓ Online (${data.latency_ms} ms) - Type: ${data.type || "Ollama"}`;
          } else {
            testStatus.textContent = `✗ Offline: ${data.error || "Cannot reach host"}`;
          }
        }
      } catch (err) {
        if (testStatus) testStatus.textContent = `Error: ${err.message}`;
      }
    });
  }

  if (formOrch) {
    formOrch.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (testStatus) testStatus.textContent = "Saving configuration...";
      const payload = {
        orchestrator_url: baseUrlInput?.value.trim() || "",
        orchestrator_model: modelInput?.value.trim() || "",
        open_webui_api_key: apiKeyInput?.value.trim() || "",
      };
      try {
        const res = await fetch("/api/orchestrator/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (testStatus) {
          if (data.status === "success") {
            const probe = data.probe || {};
            testStatus.textContent = `✓ Saved & Verified: ${probe.status || "ready"} (${probe.latency_ms || 0} ms)`;
          } else {
            testStatus.textContent = `Error: ${data.message || "Failed to save"}`;
          }
        }
      } catch (err) {
        if (testStatus) testStatus.textContent = `Save error: ${err.message}`;
      }
    });
  }

  if (copyToolBtn) {
    copyToolBtn.addEventListener("click", async () => {
      const origText = copyToolBtn.textContent;
      try {
        const res = await fetch("/api/orchestrator/tool-script");
        if (!res.ok) throw new Error("Could not fetch script");
        const data = await res.json();
        if (data.code) {
          await navigator.clipboard.writeText(data.code);
          copyToolBtn.textContent = "✓ Copied to Clipboard!";
          setTimeout(() => {
            copyToolBtn.textContent = origText;
          }, 3000);
        }
      } catch (err) {
        copyToolBtn.textContent = "✗ Copy failed";
        setTimeout(() => {
          copyToolBtn.textContent = origText;
        }, 2000);
      }
    });
  }

  // Open-WebUI Workspace & RAG Manager
  const btnSyncOwui = document.querySelector("#btn-sync-openwebui");
  const btnInspectOwui = document.querySelector("#btn-inspect-openwebui");
  const btnPreviewRag = document.querySelector("#btn-preview-rag");
  const fastModelSelect = document.querySelector("#owui-fast-base-model");
  const deepModelSelect = document.querySelector("#owui-deep-base-model");
  const syncQuickStatus = document.querySelector("#owui-sync-quick-status");
  const syncBox = document.querySelector("#owui-sync-box");
  const syncBadge = document.querySelector("#owui-sync-badge");
  const syncLog = document.querySelector("#owui-sync-log");

  function getTargetOwuiUrl() {
    let url = baseUrlInput?.value.trim() || "";
    if (!url || url.includes("11434")) {
      url = "http://192.168.2.15:8080";
    }
    return url;
  }

  function appendLog(line) {
    if (!syncLog) return;
    const ts = new Date().toLocaleTimeString();
    syncLog.textContent += `[${ts}] ${line}\n`;
    syncLog.scrollTop = syncLog.scrollHeight;
  }

  function setBadgeState(state, text) {
    if (!syncBadge) return;
    syncBadge.className = `sync-badge ${state}`;
    syncBadge.textContent = text || state.toUpperCase();
  }

  if (btnSyncOwui) {
    btnSyncOwui.addEventListener("click", async () => {
      const owuiUrl = getTargetOwuiUrl();
      const apiKey = apiKeyInput?.value.trim() || "";
      const fastModel = fastModelSelect?.value || "llama3.1:8b";
      const deepModel = deepModelSelect?.value || "deepseek-r1:14b";

      if (syncBox) syncBox.hidden = false;
      if (syncLog) syncLog.textContent = "";
      setBadgeState("running", "PROVISIONING");
      if (syncQuickStatus) syncQuickStatus.textContent = "Deploying workspace to Open-WebUI...";
      btnSyncOwui.disabled = true;

      appendLog(`Connecting to Open-WebUI at: ${owuiUrl}`);
      appendLog(`Base models: Fast [${fastModel}] | Deep Reasoner [${deepModel}]`);

      try {
        const res = await fetch("/api/orchestrator/openwebui/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            open_webui_url: owuiUrl,
            api_key: apiKey,
            fast_base_model: fastModel,
            deep_base_model: deepModel,
          }),
        });

        const data = await res.json();
        if (res.ok && data.status === "success") {
          setBadgeState("success", "PROVISIONED");
          appendLog("✓ Open-WebUI Host Online");
          appendLog(`✓ Tool Plugin: ${data.tool?.tool_id || "trader_core_tools"} (${data.tool?.status || "deployed"})`);
          appendLog(`✓ Knowledge Base: ${data.rag?.knowledge_name || "trader_core_rag"} (${data.rag?.knowledge_id || "active"})`);
          if (Array.isArray(data.rag?.uploaded_files)) {
            data.rag.uploaded_files.forEach(f => appendLog(`   📄 Uploaded: ${f.filename}`));
          }
          appendLog("✓ Dual Models Registered:");
          if (Array.isArray(data.models?.models)) {
            data.models.models.forEach(m => appendLog(`   🤖 ${m.name} (${m.id})`));
          }
          appendLog("✓ Quick Prompts Registered:");
          if (Array.isArray(data.prompts?.prompts)) {
            data.prompts.prompts.forEach(p => appendLog(`   ⚡ ${p.command} (${p.status})`));
          }
          appendLog("🚀 Workspace successfully optimized and ready!");
          if (syncQuickStatus) syncQuickStatus.textContent = "✓ Workspace provisioned!";
        } else {
          setBadgeState("error", "FAILED");
          appendLog(`✗ Provisioning error: ${data.message || "Failed"}`);
          if (syncQuickStatus) syncQuickStatus.textContent = "✗ Provisioning failed";
        }
      } catch (err) {
        setBadgeState("error", "ERROR");
        appendLog(`✗ Network error: ${err.message}`);
        if (syncQuickStatus) syncQuickStatus.textContent = `Error: ${err.message}`;
      } finally {
        btnSyncOwui.disabled = false;
      }
    });
  }

  if (btnInspectOwui) {
    btnInspectOwui.addEventListener("click", async () => {
      const owuiUrl = getTargetOwuiUrl();
      const apiKey = apiKeyInput?.value.trim() || "";

      if (syncBox) syncBox.hidden = false;
      if (syncLog) syncLog.textContent = "";
      setBadgeState("running", "INSPECTING");
      appendLog(`Inspecting Open-WebUI workspace at: ${owuiUrl}...`);

      try {
        const query = new URLSearchParams({ url: owuiUrl, api_key: apiKey });
        const res = await fetch(`/api/orchestrator/openwebui/inspect?${query.toString()}`);
        const data = await res.json();

        if (data.status === "online") {
          setBadgeState("ready", "AUDITED");
          appendLog(`✓ Host status: ONLINE (${data.version || "Open-WebUI"})`);
          appendLog(`• Tools (${(data.tools || []).length}):`);
          (data.tools || []).forEach(t => appendLog(`   - [${t.id}] ${t.name}`));
          appendLog(`• Knowledge Bases (${(data.knowledge_bases || []).length}):`);
          (data.knowledge_bases || []).forEach(k => appendLog(`   - [${k.id}] ${k.name} (${k.num_files || 0} files)`));
          appendLog(`• Custom Models (${(data.models || []).length}):`);
          (data.models || []).forEach(m => appendLog(`   - [${m.id}] ${m.name}`));
          appendLog(`• Quick Prompts (${(data.prompts || []).length}):`);
          (data.prompts || []).forEach(p => appendLog(`   - ${p.command}: ${p.title}`));
        } else {
          setBadgeState("error", "OFFLINE");
          appendLog(`✗ Inspection failed: Host is ${data.status} (${data.error || "Cannot reach host"})`);
        }
      } catch (err) {
        setBadgeState("error", "ERROR");
        appendLog(`✗ Inspection error: ${err.message}`);
      }
    });
  }

  if (btnPreviewRag) {
    btnPreviewRag.addEventListener("click", async () => {
      if (syncBox) syncBox.hidden = false;
      if (syncLog) syncLog.textContent = "";
      setBadgeState("ready", "RAG PLAYBOOKS");
      appendLog("Loading Institutional RAG Playbooks preview...");

      try {
        const res = await fetch("/api/orchestrator/openwebui/rag-preview");
        const data = await res.json();
        if (data.status === "success" && Array.isArray(data.documents)) {
          appendLog(`✓ Compiled ${data.documents.length} Institutional RAG Playbooks for Knowledge Base:\n`);
          data.documents.forEach((doc, idx) => {
            appendLog(`[${idx + 1}] ${doc.filename}`);
            appendLog(`    Title:       ${doc.title}`);
            appendLog(`    Description: ${doc.description}`);
            appendLog(`    Length:      ${doc.content.length} characters\n`);
          });
          appendLog("These documents are auto-embedded into Open-WebUI Knowledge Base during 1-click provisioning.");
        } else {
          appendLog("✗ Could not load RAG playbooks preview.");
        }
      } catch (err) {
        appendLog(`✗ Preview error: ${err.message}`);
      }
    });
  }
}


/* =========================================================================
   4. 8-STEP INTERACTIVE TRADE WORKFLOW PIPELINE CONTROLLER
   ========================================================================= */

const wfWatchlistsByBroker = {
  binance: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"],
  t212: ["EQQQ.L", "VUKE.L", "VUSA.L", "SPY", "QQQ", "VOO", "AAPL", "NVDA", "MSFT", "TSLA"],
  etoro: ["ETH", "BTC", "SOL", "NVDA", "SPX500", "NAS100"],
  kraken: ["BTCUSD", "ETHUSD", "SOLUSD", "DOTUSD", "ADAUSD"],
  ctrader: ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "XAUUSD", "USOIL"],
  quantai: ["BTCUSDT", "EQQQ.L", "SPY", "EURUSD", "ETHUSDT", "NVDA"],
};

let wfCurrentStep = 1;
let wfCurrentSymbol = "ETHUSDT";
let wfCurrentData = null;

function renderWorkflowChips(broker, assetFilter = "ALL") {
  const container = document.querySelector("#wf-instrument-chips");
  if (!container) return;
  container.innerHTML = "";

  const list = wfWatchlistsByBroker[broker] || wfWatchlistsByBroker.binance;
  list.forEach((sym) => {
    // Quick asset class categorization
    let assetClass = "CRYPTO";
    if (sym.includes("USD") && (sym.includes("EUR") || sym.includes("GBP") || sym.includes("JPY") || sym.includes("AUD") || sym.includes("CAD"))) {
      assetClass = "FOREX";
    } else if (sym === "XAUUSD" || sym === "USOIL") {
      assetClass = "COMMODITY";
    } else if (sym.endsWith(".L") || ["SPY", "QQQ", "VOO", "VTI", "IWM", "GLD", "EQQQ.L", "VUKE.L", "VUSA.L"].includes(sym)) {
      assetClass = "ETFS";
    } else if (["AAPL", "NVDA", "MSFT", "TSLA"].includes(sym)) {
      assetClass = "STOCKS";
    }

    if (assetFilter === "ALL" || assetFilter === assetClass || (assetFilter === "FOREX" && assetClass === "COMMODITY")) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `wf-chip ${sym === wfCurrentSymbol ? "is-active" : ""}`;
      btn.textContent = sym;
      btn.addEventListener("click", () => {
        container.querySelectorAll(".wf-chip").forEach((c) => c.classList.remove("is-active"));
        btn.classList.add("is-active");
        wfCurrentSymbol = sym;
        const input = document.querySelector("#wf-symbol-input");
        if (input) input.value = sym;
      });
      container.appendChild(btn);
    }
  });
}

function goToWorkflowStep(stepNum) {
  wfCurrentStep = stepNum;
  const nodes = document.querySelectorAll(".wf-step-node");
  nodes.forEach((node) => {
    const s = Number(node.dataset.step);
    node.classList.toggle("is-active", s === stepNum);
    node.classList.toggle("is-completed", s < stepNum);
  });

  for (let i = 1; i <= 8; i++) {
    const panel = document.querySelector(`#wf-panel-${i}`);
    if (panel) panel.hidden = (i !== stepNum);
  }

  const badge = document.querySelector("#wf-current-badge");
  if (badge) badge.textContent = `STEP ${stepNum} OF 8`;
}

function renderWorkflowDetails(data) {
  wfCurrentData = data;

  // Step 1 Badge update
  const pipeBadge = document.querySelector("#wf-pipeline-badge");
  if (pipeBadge) {
    const isMacro = data.execution_pipeline === "MACRO_DCA";
    pipeBadge.innerHTML = `<span class="badge ${isMacro ? "badge-strat" : ""}">${isMacro ? "PIPELINE: MACRO DCA (ETF)" : "PIPELINE: INTRADAY STRUCTURAL"}</span>`;
  }

  // Step 2: Research
  const scoreEl = document.querySelector("#wf-sentiment-score");
  const badgeEl = document.querySelector("#wf-sentiment-badge");
  const velEl = document.querySelector("#wf-mention-velocity");
  const newsEl = document.querySelector("#wf-news-headline");
  const newsSentEl = document.querySelector("#wf-news-sentiment");
  const macroRiskEl = document.querySelector("#wf-macro-risk");
  const macroDotEl = document.querySelector("#wf-macro-dot");

  if (scoreEl) scoreEl.textContent = (data.step_2_research.sentiment_score > 0 ? "+" : "") + data.step_2_research.sentiment_score.toFixed(2);
  if (badgeEl) {
    badgeEl.textContent = data.step_2_research.sentiment_label;
    badgeEl.className = data.step_2_research.sentiment_label === "BULLISH" ? "badge badge-strat" : "badge";
  }
  if (velEl) velEl.textContent = `${data.step_2_research.mention_velocity} mentions / hr · Institutional sentiment`;
  if (newsEl) newsEl.textContent = data.step_2_research.headline;
  if (newsSentEl) newsSentEl.textContent = `AI Sentiment: ${data.step_2_research.sentiment_label} ACCUMULATION`;
  if (macroRiskEl) {
    macroRiskEl.textContent = data.step_2_research.macro_risk_warning ? "HIGH RISK EVENT SOON" : "TIER-1 CLEAR (SAFE)";
    macroRiskEl.style.color = data.step_2_research.macro_risk_warning ? "#ef4444" : "#10b981";
  }
  if (macroDotEl) {
    macroDotEl.className = data.step_2_research.macro_risk_warning ? "status-dot status-dot-offline" : "status-dot status-dot-online";
  }

  // Step 3: Suggest
  const setupName = document.querySelector("#wf-setup-name");
  const setupBias = document.querySelector("#wf-setup-bias");
  const setupConf = document.querySelector("#wf-setup-confidence");
  const engineNote = document.querySelector("#wf-engine-note");
  if (setupName) setupName.textContent = data.step_3_suggest.setup_name;
  if (setupBias) {
    setupBias.textContent = `BIAS: ${data.step_3_suggest.action}`;
    setupBias.style.color = data.step_3_suggest.action === "BUY" ? "#10b981" : (data.step_3_suggest.action === "HOLD" ? "#eab308" : "#ef4444");
  }
  if (setupConf) setupConf.textContent = `CONFIDENCE: ${(data.step_3_suggest.confidence * 100).toFixed(0)}%`;
  if (engineNote) engineNote.textContent = data.step_3_suggest.engine_note || "";

  // Step 4: Analyze
  const pHigh = document.querySelector("#wf-pivot-high");
  const pLow = document.querySelector("#wf-pivot-low");
  const poc = document.querySelector("#wf-poc");
  const va = document.querySelector("#wf-va");
  const fvg = document.querySelector("#wf-fvg");
  const ce = document.querySelector("#wf-ce");
  if (pHigh) pHigh.textContent = `$${data.step_4_analyze.pivot_high.toFixed(2)}`;
  if (pLow) pLow.textContent = `$${data.step_4_analyze.pivot_low.toFixed(2)}`;
  if (poc) poc.textContent = `$${data.step_4_analyze.point_of_control.toFixed(2)}`;
  if (va) va.textContent = `$${data.step_4_analyze.value_area_low.toFixed(2)} - $${data.step_4_analyze.value_area_high.toFixed(2)}`;
  if (fvg) fvg.textContent = `Retest $${data.step_4_analyze.fvg_zone[0].toFixed(2)} - $${data.step_4_analyze.fvg_zone[1].toFixed(2)}`;
  if (ce) {
    if (data.asset_class === "ETF") {
      ce.textContent = `200 SMA $${data.step_4_analyze.sma_200.toFixed(2)}`;
    } else {
      ce.textContent = `50% CE $${data.step_4_analyze.consequent_encroachment.toFixed(2)}`;
    }
  }

  // Step 5: Strategy
  const stratTitle = document.querySelector("#wf-strat-title");
  if (stratTitle) stratTitle.textContent = `${data.step_5_strategy.strategy_name} (${data.step_5_strategy.pipeline_type || data.step_5_strategy.category.toUpperCase()})`;

  // Step 6: Parameters & Pre-Trade Audit
  const pEntry = document.querySelector("#wf-param-entry");
  const pStop = document.querySelector("#wf-param-stop");
  const pRiskPct = document.querySelector("#wf-param-risk-pct");
  const pTp = document.querySelector("#wf-param-tp");
  const pRr = document.querySelector("#wf-param-rr");
  const pSize = document.querySelector("#wf-param-size");
  const pUnits = document.querySelector("#wf-param-units");
  const pMaxLoss = document.querySelector("#wf-param-max-loss");
  const pEquityBudget = document.querySelector("#wf-param-equity-budget");
  const auditStatus = document.querySelector("#wf-audit-status");
  const brokerBadge = document.querySelector("#wf-target-broker-badge");
  const auditDetail = document.querySelector("#wf-audit-detail");

  const p = data.step_6_parameters;
  if (pEntry) pEntry.textContent = `$${p.entry_price.toFixed(p.entry_price < 10 ? 4 : 2)}`;
  if (pStop) pStop.textContent = `$${p.stop_loss.toFixed(p.stop_loss < 10 ? 4 : 2)}`;
  if (pRiskPct) pRiskPct.textContent = `-${p.risk_pct}% Risk (Under Invalidation Wick)`;
  if (pTp) pTp.textContent = `$${p.take_profit.toFixed(p.take_profit < 10 ? 4 : 2)}`;
  if (pRr) pRr.textContent = `Target R:R 1:${p.risk_reward_ratio} (≥ 1:2.0 Mandatory)`;
  if (pSize) pSize.textContent = `$${p.recommended_size_usd.toFixed(2)}`;
  if (pUnits) pUnits.textContent = `Units: ${p.recommended_units} · RiskSentinel Cap`;
  if (pMaxLoss) pMaxLoss.textContent = `-$${p.max_loss_base_currency.toFixed(2)}`;
  if (pEquityBudget) pEquityBudget.textContent = `Equity: $${p.equity.toFixed(2)} (2% = $${(p.equity * 0.02).toFixed(2)})`;
  if (auditStatus) {
    auditStatus.textContent = p.pre_trade_audit?.valid ? "PASSED" : "REJECTED";
    auditStatus.className = p.pre_trade_audit?.valid ? "color-green" : "color-red";
  }
  if (brokerBadge) brokerBadge.textContent = `DESTINATION: ${p.target_broker.toUpperCase()}`;
  if (auditDetail) {
    auditDetail.textContent = `Capital preservation rule satisfied · Max loss bounded to $${p.max_loss_base_currency.toFixed(2)} (≤ 2.0% equity) · Order notional $${p.recommended_size_usd.toFixed(2)} (≤ $50.00 RiskSentinel limit) · Mandatory R:R 1:${p.risk_reward_ratio} verified.`;
  }

  // Update Breadcrumb Ribbon
  const ribbon = document.querySelector("#wf-breadcrumb-ribbon");
  if (ribbon) {
    ribbon.hidden = false;
    const rSym = document.querySelector("#ribbon-symbol");
    if (rSym) rSym.textContent = data.symbol;
    const rPipe = document.querySelector("#ribbon-pipeline");
    if (rPipe) {
      rPipe.textContent = data.execution_pipeline === "MACRO_DCA" ? "MACRO DCA (ETF)" : "INTRADAY STRUCTURAL";
      rPipe.className = data.execution_pipeline === "MACRO_DCA" ? "badge badge-strat" : "badge";
    }
    const rBias = document.querySelector("#ribbon-bias");
    if (rBias) {
      rBias.textContent = `${data.step_3_suggest.action} · ${(data.step_3_suggest.confidence * 100).toFixed(0)}%`;
      rBias.className = data.step_3_suggest.action === "BUY" ? "color-green" : "color-red";
    }
    const rLvl = document.querySelector("#ribbon-level");
    if (rLvl) {
      if (data.asset_class === "ETF") {
        rLvl.textContent = `200 SMA $${data.step_4_analyze.sma_200.toFixed(2)}`;
      } else {
        rLvl.textContent = `50% CE $${data.step_4_analyze.consequent_encroachment.toFixed(2)}`;
      }
    }
    const rRr = document.querySelector("#ribbon-rr");
    if (rRr) rRr.textContent = `1:${data.step_6_parameters.risk_reward_ratio}`;
    const rAud = document.querySelector("#ribbon-audit");
    if (rAud) {
      rAud.textContent = data.step_6_parameters.pre_trade_audit?.valid ? "PASSED" : "REJECTED";
      rAud.className = data.step_6_parameters.pre_trade_audit?.valid ? "badge badge-strat color-green" : "badge color-red";
    }
  }

  // Redraw chart overlays if chart has data
  if (loadedMarketData) {
    drawMarketChart(loadedMarketData.bars, loadedMarketData.liquidity);
  }
}

async function loadWorkflowRecommendation(symbol) {
  wfCurrentSymbol = symbol.toUpperCase().trim();
  goToWorkflowStep(2);

  const headline = document.querySelector("#wf-news-headline");
  if (headline) headline.textContent = `Analyzing ${wfCurrentSymbol} across social feeds, orderbook, and structure...`;

  try {
    const res = await fetch("/api/workflow/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: wfCurrentSymbol, broker: currentBroker }),
    });
    const data = await res.json();
    if (data.status !== "success") throw new Error(data.error || "Recommendation failed");
    renderWorkflowDetails(data);
  } catch (err) {
    if (headline) headline.textContent = `Error loading workflow intel: ${err.message}`;
    showToast(`Workflow error: ${err.message}`, "error");
  }
}

async function runInstantAutoScan(symbol) {
  const sym = (symbol || wfCurrentSymbol || "ETHUSDT").toUpperCase().trim();
  wfCurrentSymbol = sym;
  const input = document.querySelector("#wf-symbol-input");
  if (input) input.value = sym;

  const btnAuto = document.querySelector("#btn-wf-step1-autoscan");
  if (btnAuto) {
    btnAuto.disabled = true;
    btnAuto.innerHTML = `<span>⏳ Scanning...</span>`;
  }
  showToast(`⚡ Instant Scan: Analyzing ${sym} across dual-engine pipeline...`, "info", 2000);

  try {
    const res = await fetch("/api/workflow/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: sym, broker: currentBroker }),
    });
    const data = await res.json();
    if (data.status !== "success") throw new Error(data.error || "Recommendation failed");

    renderWorkflowDetails(data);

    // Jump directly to Step 6 Pre-Trade Parameters & Audit!
    goToWorkflowStep(6);

    // Auto-load symbol on chart
    const symInput = document.querySelector("#market-symbol");
    const provSelect = document.querySelector("#market-provider");
    if (symInput) symInput.value = sym;
    if (provSelect) {
      provSelect.value = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "AVAXUSDT"].some((k) => sym.includes(k)) ? "binance" : "yahoo";
    }
    document.querySelector("#load-market-data")?.click();

    showToast(`✓ Pre-Trade Audit Verified: Entry $${data.step_6_parameters.entry_price.toFixed(2)} | SL $${data.step_6_parameters.stop_loss.toFixed(2)} | Target 1:${data.step_6_parameters.risk_reward_ratio}`, "success", 4000);

  } catch (err) {
    showToast(`Auto-Scan failed: ${err.message}`, "error", 4000);
  } finally {
    if (btnAuto) {
      btnAuto.disabled = false;
      btnAuto.innerHTML = `<span>⚡ 1-Click Instant Scan</span>`;
    }
  }
}

function initWorkflowController() {
  renderWorkflowChips(currentBroker);

  // Topbar 8-Step Workflow Button
  const topbarWorkflowBtn = document.querySelector("#btn-topbar-workflow");
  if (topbarWorkflowBtn) {
    topbarWorkflowBtn.addEventListener("click", () => {
      const card = document.querySelector("#trade-workflow-card");
      if (card) {
        card.scrollIntoView({ behavior: "smooth", block: "start" });
        card.classList.add("highlight-pulse");
        setTimeout(() => card.classList.remove("highlight-pulse"), 1500);
      }
    });
  }

  // Stepper Node Click
  document.querySelectorAll(".wf-step-node").forEach((node) => {
    node.addEventListener("click", () => {
      const step = Number(node.dataset.step);
      goToWorkflowStep(step);
    });
  });

  // Asset Filter Pills
  document.querySelectorAll(".wf-filter-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".wf-filter-pill").forEach((p) => p.classList.remove("is-active"));
      pill.classList.add("is-active");
      renderWorkflowChips(currentBroker, pill.dataset.asset);
    });
  });

  // Reset Workflow
  const btnReset = document.querySelector("#btn-wf-reset");
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      goToWorkflowStep(1);
    });
  }

  // 1-Click Instant Auto-Scan
  const btnAutoScan = document.querySelector("#btn-wf-step1-autoscan");
  if (btnAutoScan) {
    btnAutoScan.addEventListener("click", () => {
      const input = document.querySelector("#wf-symbol-input");
      const sym = input?.value.trim() || wfCurrentSymbol || "ETHUSDT";
      runInstantAutoScan(sym);
    });
  }

  // Ribbon Jump to Audit
  const btnRibbonAudit = document.querySelector("#btn-ribbon-jump-audit");
  if (btnRibbonAudit) {
    btnRibbonAudit.addEventListener("click", () => {
      goToWorkflowStep(6);
      document.querySelector("#trade-workflow-card")?.scrollIntoView({ behavior: "smooth" });
    });
  }

  // Chart Overlays Toggle
  const chkOverlays = document.querySelector("#chk-chart-overlays");
  if (chkOverlays) {
    chkOverlays.addEventListener("change", () => {
      if (loadedMarketData) {
        drawMarketChart(loadedMarketData.bars, loadedMarketData.liquidity);
      }
      showToast(`Chart geometry overlays: ${chkOverlays.checked ? "ENABLED" : "DISABLED"}`, "info", 1500);
    });
  }

  // Step 1: Next / Research
  const btnStep1Next = document.querySelector("#btn-wf-step1-next");
  if (btnStep1Next) {
    btnStep1Next.addEventListener("click", () => {
      const input = document.querySelector("#wf-symbol-input");
      const sym = input?.value.trim() || wfCurrentSymbol || "ETHUSDT";
      loadWorkflowRecommendation(sym);
    });
  }

  // Stepper Back/Next buttons
  for (let i = 1; i <= 7; i++) {
    const btnBack = document.querySelector(`#btn-wf-back-${i}`);
    if (btnBack) btnBack.addEventListener("click", () => goToWorkflowStep(i));

    const btnNext = document.querySelector(`#btn-wf-step${i}-next`);
    if (btnNext) btnNext.addEventListener("click", () => goToWorkflowStep(i + 1));
  }

  // Step 4: Load on Candlestick Chart
  const btnChartLoad = document.querySelector("#btn-wf-chart-load");
  if (btnChartLoad) {
    btnChartLoad.addEventListener("click", () => {
      const symInput = document.querySelector("#market-symbol");
      const provSelect = document.querySelector("#market-provider");
      if (symInput && wfCurrentSymbol) {
        symInput.value = wfCurrentSymbol;
        if (provSelect) {
          provSelect.value = ["BTCUSDT", "ETHUSDT", "SOLUSDT"].some((k) => wfCurrentSymbol.includes(k)) ? "binance" : "yahoo";
        }
        document.querySelector("#load-market-data")?.click();
        document.querySelector("#market-chart-frame")?.scrollIntoView({ behavior: "smooth" });
      }
    });
  }

  // Step 5: Apply Strategy
  const btnApplyStrat = document.querySelector("#btn-wf-apply-strat");
  if (btnApplyStrat) {
    btnApplyStrat.addEventListener("click", async () => {
      const stratId = wfCurrentData?.step_5_strategy?.strategy_id || "price_action";
      try {
        await fetch("/api/strategies/select", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strategy_id: stratId }),
        });
        const select = document.querySelector("#auto-strategy-select");
        if (select) select.value = stratId;
        btnApplyStrat.textContent = "✓ Strategy Selected & Applied";
        btnApplyStrat.disabled = true;
      } catch (_) {}
    });
  }

  // Step 7: Demo Order Execution
  const btnDemoExec = document.querySelector("#btn-wf-demo-execute");
  const wfDemoMsg = document.querySelector("#wf-demo-msg");
  if (btnDemoExec) {
    btnDemoExec.addEventListener("click", async () => {
      if (wfDemoMsg) wfDemoMsg.textContent = "Submitting simulated demo order...";
      const params = wfCurrentData?.step_6_parameters || {};
      const payload = {
        symbol: wfCurrentSymbol,
        broker: currentBroker,
        side: wfCurrentData?.step_3_suggest?.action || "BUY",
        units: params.recommended_units || 1.0,
        price: params.entry_price || 100.0,
      };

      try {
        const res = await fetch("/api/workflow/demo-execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const d = await res.json();
        if (wfDemoMsg) {
          wfDemoMsg.textContent = `✓ Demo Order Executed (${d.order_id}): ${payload.side} ${payload.symbol}`;
          wfDemoMsg.className = "status-msg color-green";
        }
        showToast(`✓ Demo Order Executed: ${payload.side} ${payload.symbol} (${d.order_id})`, "success", 4000);
        loadPortfolio(currentBroker);
      } catch (err) {
        if (wfDemoMsg) wfDemoMsg.textContent = `Failed: ${err.message}`;
        showToast(`Demo order failed: ${err.message}`, "error", 4000);
      }
    });
  }

  // Step 8: Live Realtime Execution
  const btnLiveExec = document.querySelector("#btn-wf-live-execute");
  const wfLiveMsg = document.querySelector("#wf-live-msg");
  if (btnLiveExec) {
    btnLiveExec.addEventListener("click", () => {
      // Trigger confirmation modal
      const modal = document.querySelector("#real-mode-modal");
      if (modal) {
        modal.hidden = false;
        const confirmBtn = document.querySelector("#btn-modal-confirm");
        if (confirmBtn) {
          confirmBtn.onclick = () => {
            modal.hidden = true;
            if (wfLiveMsg) {
              wfLiveMsg.textContent = `🚀 Live Order Armed for ${wfCurrentSymbol} on ${currentBroker.toUpperCase()}`;
              wfLiveMsg.className = "status-msg color-green";
            }
            showToast(`🚀 Live Order Armed: ${wfCurrentSymbol} on ${currentBroker.toUpperCase()}`, "success", 4000);
          };
        }
      }
    });
  }
}


/* =========================================================================
   5. FLOATING AI QUANT COPILOT CHATBOT CONTROLLER
   ========================================================================= */

function initQuantCopilot() {
  const toggleBtn = document.querySelector("#btn-copilot-toggle");
  const topbarCopilotBtn = document.querySelector("#btn-topbar-copilot");
  const copilotWin = document.querySelector("#copilot-window");
  const closeBtn = document.querySelector("#btn-copilot-close");
  const clearBtn = document.querySelector("#btn-copilot-clear");
  const modelSelect = document.querySelector("#copilot-active-model");
  const modelPill = document.querySelector("#copilot-model-pill");
  const form = document.querySelector("#copilot-form");
  const input = document.querySelector("#copilot-input");
  const messagesBox = document.querySelector("#copilot-messages");

  if (!copilotWin) return;

  const toggleCopilot = () => {
    copilotWin.hidden = !copilotWin.hidden;
    if (!copilotWin.hidden && input) input.focus();
  };

  if (toggleBtn) {
    toggleBtn.addEventListener("click", toggleCopilot);
  }

  if (topbarCopilotBtn) {
    topbarCopilotBtn.addEventListener("click", toggleCopilot);
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      copilotWin.hidden = true;
    });
  }

  if (clearBtn && messagesBox) {
    clearBtn.addEventListener("click", () => {
      messagesBox.innerHTML = `
        <div class="copilot-msg msg-assistant">
          <div class="msg-bubble">
            <strong>Chat history cleared.</strong> How can I assist your quantitative analysis today?
          </div>
        </div>
      `;
    });
  }

  if (modelSelect && modelPill) {
    modelSelect.addEventListener("change", () => {
      modelPill.textContent = modelSelect.value;
    });
  }

  // Quick Chips
  document.querySelectorAll(".copilot-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (input) {
        input.value = chip.dataset.query;
        form?.dispatchEvent(new Event("submit"));
      }
    });
  });

  function appendCopilotMessage(sender, text, isActionable = false) {
    if (!messagesBox) return;
    const msgDiv = document.createElement("div");
    msgDiv.className = `copilot-msg msg-${sender}`;

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.innerHTML = text.replace(/\n/g, "<br/>");

    if (isActionable) {
      // Extract possible ticker symbols (e.g. BTC, ETH, SOL, NVDA, AAPL, EURUSD)
      const words = text.match(/\b(BTC|ETH|SOL|NVDA|AAPL|MSFT|SPY|QQQ|EURUSD|GBPUSD|XAUUSD)\b/g);
      if (words && words.length) {
        const uniqueSym = [...new Set(words)][0];
        const actionBtn = document.createElement("button");
        actionBtn.type = "button";
        actionBtn.className = "chat-action-btn";
        actionBtn.textContent = `⚡ Step Into 8-Step Workflow (${uniqueSym})`;
        actionBtn.addEventListener("click", () => {
          loadWorkflowRecommendation(uniqueSym);
          document.querySelector("#trade-workflow-card")?.scrollIntoView({ behavior: "smooth" });
        });
        bubble.appendChild(document.createElement("br"));
        bubble.appendChild(actionBtn);
      }
    }

    msgDiv.appendChild(bubble);
    messagesBox.appendChild(msgDiv);
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  if (form && input) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;

      appendCopilotMessage("user", text);
      input.value = "";

      // Typing placeholder
      const typingDiv = document.createElement("div");
      typingDiv.className = "copilot-msg msg-assistant typing-indicator";
      typingDiv.innerHTML = '<div class="msg-bubble"><em>Quant Copilot is reasoning...</em></div>';
      messagesBox?.appendChild(typingDiv);
      messagesBox.scrollTop = messagesBox.scrollHeight;

      const selectedModel = modelSelect?.value || "llama3.1:8b";
      try {
        const res = await fetch("/api/orchestrator/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            command: text,
            model: selectedModel,
            broker: currentBroker,
          }),
        });
        typingDiv.remove();

        const data = await res.json();
        if (data.status === "success" && data.response) {
          appendCopilotMessage("assistant", data.response, true);
        } else {
          // Dynamic fallback to local Ollama if 404
          const fbRes = await fetch("/api/agent/query?broker=" + currentBroker + "&symbol=ETH");
          const fbData = await fbRes.json();
          appendCopilotMessage("assistant", fbData.analysis || data.error || "Analysis completed.", true);
        }
      } catch (err) {
        typingDiv.remove();
        appendCopilotMessage("assistant", `Copilot request failed: ${err.message}`);
      }
    });
  }
}


/* =========================================================================
   6. ADMIN SENTINEL BOUNDS & AUDIT LEDGER CONTROLLER
   ========================================================================= */

async function loadAuditLedger() {
  const tbody = document.querySelector("#audit-ledger-tbody");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="8" class="empty-cell">Loading StateStore trade ledger...</td></tr>';

  try {
    const res = await fetch("/api/admin/audit-ledger");
    const data = await res.json();
    const positions = Array.isArray(data.positions) ? data.positions : [];
    if (!positions.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty-cell">No trades recorded yet. Run a demo order in Step 7 to see live ledger rows.</td></tr>';
      return;
    }

    tbody.innerHTML = "";
    positions.forEach((p) => {
      const tr = document.createElement("tr");
      const sideClass = p.side === "BUY" ? "color-green" : "color-red";
      tr.innerHTML = `
        <td><code>${p.position_id}</code></td>
        <td><strong>${p.symbol}</strong></td>
        <td><span class="badge">${(p.broker || "BINANCE").toUpperCase()}</span></td>
        <td class="${sideClass}"><strong>${p.side}</strong></td>
        <td>${p.units}</td>
        <td>$${Number(p.entry_price || 0).toFixed(4)}</td>
        <td><small>${p.opened_at ? new Date(p.opened_at).toLocaleTimeString() : "Recent"}</small></td>
        <td><span class="badge badge-strat">RECORDED</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-cell">Ledger error: ${err.message}</td></tr>`;
  }
}

function initAdminControls() {
  // Load Bounds on init
  const loadBounds = async () => {
    try {
      const res = await fetch("/api/automation/status");
      const data = await res.json();
      if (data.guardrails) {
        const g = data.guardrails;
        const elMax = document.querySelector("#bounds-max-order");
        const elSl = document.querySelector("#bounds-stop-loss");
        const elCb = document.querySelector("#bounds-circuit-breaker");
        const elPos = document.querySelector("#bounds-max-positions");
        const elRr = document.querySelector("#bounds-min-rr");

        if (elMax && g.max_order_usd) elMax.value = g.max_order_usd;
        if (elSl && g.stop_loss_pct) elSl.value = g.stop_loss_pct;
        if (elCb && g.max_daily_drawdown_pct) elCb.value = g.max_daily_drawdown_pct;
        if (elPos && g.max_open_positions) elPos.value = g.max_open_positions;
        if (elRr && g.min_risk_reward) elRr.value = g.min_risk_reward;
      }
    } catch (_) {}
  };
  loadBounds();

  // Save Bounds Form
  const formBounds = document.querySelector("#form-risksentinel-bounds");
  const boundsStatus = document.querySelector("#bounds-save-status");
  if (formBounds) {
    formBounds.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (boundsStatus) boundsStatus.textContent = "Saving RiskSentinel bounds...";

      const payload = {
        max_order_usd: parseFloat(document.querySelector("#bounds-max-order")?.value || 50),
        stop_loss_pct: parseFloat(document.querySelector("#bounds-stop-loss")?.value || 2.0),
        max_daily_drawdown_pct: parseFloat(document.querySelector("#bounds-circuit-breaker")?.value || 3.0),
        max_open_positions: parseInt(document.querySelector("#bounds-max-positions")?.value || 5, 10),
        min_risk_reward: parseFloat(document.querySelector("#bounds-min-rr")?.value || 2.0),
      };

      try {
        const res = await fetch("/api/automation/configure", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (boundsStatus) {
          boundsStatus.textContent = "✓ RiskSentinel bounds saved and armed.";
          boundsStatus.className = "status-msg color-green";
        }
        refreshAutomationStatus();
      } catch (err) {
        if (boundsStatus) boundsStatus.textContent = `Error: ${err.message}`;
      }
    });
  }

  // Refresh Ledger Button
  const btnRefreshLedger = document.querySelector("#btn-refresh-ledger");
  if (btnRefreshLedger) {
    btnRefreshLedger.addEventListener("click", loadAuditLedger);
  }
}


/* =========================================================================
   7. PRO COMMAND PALETTE (Ctrl+K / ⌘K) & GLOBAL SHORTCUTS
   ========================================================================= */

function selectBrokerTab(brokerKey) {
  const tab = document.querySelector(`.broker-tab[data-broker="${brokerKey}"]`);
  if (tab) tab.click();
}

const COMMAND_REGISTRY = [
  // Focus View Modes
  { id: "view_workflow", title: "Switch to 🎯 8-Step Workflow View", category: "View Mode", shortcut: "1", action: () => applyWorkspaceViewMode("workflow") },
  { id: "view_portfolio", title: "Switch to 📊 Portfolio Hub View", category: "View Mode", shortcut: "2", action: () => applyWorkspaceViewMode("portfolio") },
  { id: "view_quantlab", title: "Switch to 🔬 Quant Lab & Charts View", category: "View Mode", shortcut: "3", action: () => applyWorkspaceViewMode("quantlab") },
  { id: "view_all", title: "Switch to 🌐 All Panels (Continuous Layout)", category: "View Mode", shortcut: "4", action: () => applyWorkspaceViewMode("all") },

  // Instant Auto-Scans
  { id: "scan_eth", title: "⚡ Instant Auto-Scan: ETHUSDT (Intraday Structural)", category: "Auto-Scan", keyword: "eth ethereum crypto", action: () => runInstantAutoScan("ETHUSDT") },
  { id: "scan_btc", title: "⚡ Instant Auto-Scan: BTCUSDT (Intraday Structural)", category: "Auto-Scan", keyword: "btc bitcoin crypto", action: () => runInstantAutoScan("BTCUSDT") },
  { id: "scan_sol", title: "⚡ Instant Auto-Scan: SOLUSDT (Intraday Structural)", category: "Auto-Scan", keyword: "sol solana crypto", action: () => runInstantAutoScan("SOLUSDT") },
  { id: "scan_eqqq", title: "⚡ Instant Auto-Scan: EQQQ.L (Macro DCA ETF - LSE)", category: "Auto-Scan", keyword: "eqqq qqq nasdaq etf t212", action: () => runInstantAutoScan("EQQQ.L") },
  { id: "scan_vuke", title: "⚡ Instant Auto-Scan: VUKE.L (Macro DCA FTSE 100)", category: "Auto-Scan", keyword: "vuke ftse etf t212", action: () => runInstantAutoScan("VUKE.L") },
  { id: "scan_eurusd", title: "⚡ Instant Auto-Scan: EURUSD (Forex London/NY)", category: "Auto-Scan", keyword: "eur usd forex ctrader", action: () => runInstantAutoScan("EURUSD") },
  { id: "scan_xauusd", title: "⚡ Instant Auto-Scan: XAUUSD (Gold Imbalance Retest)", category: "Auto-Scan", keyword: "gold commodity xau ctrader", action: () => runInstantAutoScan("XAUUSD") },
  { id: "scan_nvda", title: "⚡ Instant Auto-Scan: NVDA (US Tech Structural)", category: "Auto-Scan", keyword: "nvda nvidia stock equities", action: () => runInstantAutoScan("NVDA") },

  // Broker Routing Tabs
  { id: "broker_binance", title: "Select Broker: Binance Spot Crypto", category: "Brokers", keyword: "binance btc eth crypto", action: () => selectBrokerTab("binance") },
  { id: "broker_t212", title: "Select Broker: Trading 212 (Invest / ISA)", category: "Brokers", keyword: "t212 stocks etfs eqqq", action: () => selectBrokerTab("t212") },
  { id: "broker_etoro", title: "Select Broker: eToro Multi-Asset Demo", category: "Brokers", keyword: "etoro demo copy portfolio", action: () => selectBrokerTab("etoro") },
  { id: "broker_kraken", title: "Select Broker: Kraken Spot Crypto", category: "Brokers", keyword: "kraken btc eth crypto", action: () => selectBrokerTab("kraken") },
  { id: "broker_ctrader", title: "Select Broker: cTrader Open API Forex", category: "Brokers", keyword: "ctrader forex eurusd xauusd", action: () => selectBrokerTab("ctrader") },
  { id: "broker_quantai", title: "Select Broker: Quant AI Engine", category: "Brokers", keyword: "ai copilot orchestrator", action: () => selectBrokerTab("quantai") },
  { id: "broker_admin", title: "Admin Portal: RiskSentinel & Audit Ledger", category: "Brokers", keyword: "admin ledger bounds store", action: () => selectBrokerTab("admin") },
  { id: "broker_resources", title: "Resource Hub: Knowledge Base & Open-WebUI RAG", category: "Brokers", shortcut: "5", keyword: "resource hub knowledge rag sec openwebui data equation", action: () => selectBrokerTab("resources") },
  { id: "sync_resources", title: "⚡ Sync All Resources to Open-WebUI Vector Memory", category: "Tools", keyword: "sync rag openwebui vector", action: () => document.querySelector("#btn-sync-resources-now")?.click() },

  // Actions & Utilities
  { id: "toggle_copilot", title: "Toggle AI Quant Copilot Window", category: "Tools", shortcut: "C", action: () => document.querySelector("#btn-topbar-copilot")?.click() },
  { id: "refresh_portfolio", title: "Refresh Active Broker Portfolio & Balances", category: "Tools", shortcut: "R", action: () => { loadPortfolio(currentBroker); showToast(`Refreshed ${currentBroker.toUpperCase()} portfolio`, "info", 1500); } },
  { id: "toggle_overlays", title: "Toggle Candlestick Geometry Overlays (SL/TP/CE)", category: "Chart", shortcut: "O", action: () => {
    const chk = document.querySelector("#chk-chart-overlays");
    if (chk) {
      chk.checked = !chk.checked;
      chk.dispatchEvent(new Event("change"));
    }
  }},
  { id: "toggle_mode", title: "Toggle Demo / Real Capital Mode", category: "Execution", shortcut: "M", action: () => document.querySelector("#mode-toggle-btn")?.click() },
  { id: "shortcuts_help", title: "Open Keyboard Shortcuts Cheat Sheet", category: "Help", shortcut: "?", action: () => openShortcutsModal() },
];

let cmdSelectedIndex = 0;
let currentFilteredCommands = [...COMMAND_REGISTRY];

function openCommandPalette() {
  const modal = document.querySelector("#command-palette-modal");
  const input = document.querySelector("#cmd-palette-input");
  if (!modal || !input) return;

  modal.hidden = false;
  input.value = "";
  renderCommandPaletteResults("");
  input.focus();
}

function closeCommandPalette() {
  const modal = document.querySelector("#command-palette-modal");
  if (modal) modal.hidden = true;
}

function renderCommandPaletteResults(query = "") {
  const container = document.querySelector("#cmd-palette-results");
  if (!container) return;

  const q = query.trim().toLowerCase();
  currentFilteredCommands = COMMAND_REGISTRY.filter((cmd) => {
    if (!q) return true;
    return (
      cmd.title.toLowerCase().includes(q) ||
      cmd.category.toLowerCase().includes(q) ||
      (cmd.keyword && cmd.keyword.toLowerCase().includes(q))
    );
  });

  cmdSelectedIndex = 0;
  container.innerHTML = "";

  if (currentFilteredCommands.length === 0) {
    container.innerHTML = '<div class="cmd-item" style="cursor:default;opacity:0.6;"><span>No matching commands or assets found.</span></div>';
    return;
  }

  currentFilteredCommands.forEach((cmd, idx) => {
    const item = document.createElement("div");
    item.className = `cmd-item ${idx === cmdSelectedIndex ? "is-active" : ""}`;
    item.dataset.index = String(idx);

    let icon = "⚡";
    if (cmd.category === "View Mode") icon = "🎯";
    else if (cmd.category === "Auto-Scan") icon = "🔍";
    else if (cmd.category === "Brokers") icon = "🏦";
    else if (cmd.category === "Tools") icon = "🛠";
    else if (cmd.category === "Chart") icon = "📈";
    else if (cmd.category === "Execution") icon = "🛡";

    item.innerHTML = `
      <div class="cmd-item-left">
        <span class="cmd-item-icon">${icon}</span>
        <div>
          <span class="cmd-item-title">${cmd.title}</span>
          <span class="cmd-item-sub">${cmd.category}</span>
        </div>
      </div>
      ${cmd.shortcut ? `<span class="cmd-item-badge"><kbd>${cmd.shortcut}</kbd></span>` : `<span class="cmd-item-badge">ENTER</span>`}
    `;

    item.addEventListener("click", () => {
      closeCommandPalette();
      cmd.action();
    });

    item.addEventListener("mouseenter", () => {
      cmdSelectedIndex = idx;
      container.querySelectorAll(".cmd-item").forEach((el, i) => {
        el.classList.toggle("is-active", i === cmdSelectedIndex);
      });
    });

    container.appendChild(item);
  });
}

function updateCommandPaletteSelection(newIndex) {
  const container = document.querySelector("#cmd-palette-results");
  const items = container?.querySelectorAll(".cmd-item") || [];
  if (!items.length) return;

  cmdSelectedIndex = (newIndex + items.length) % items.length;
  items.forEach((item, idx) => {
    const isActive = idx === cmdSelectedIndex;
    item.classList.toggle("is-active", isActive);
    if (isActive) {
      item.scrollIntoView({ block: "nearest" });
    }
  });
}

function initCommandPalette() {
  const modal = document.querySelector("#command-palette-modal");
  const input = document.querySelector("#cmd-palette-input");
  const btnClose = document.querySelector("#btn-close-cmd-palette");
  const btnTrigger = document.querySelector("#btn-trigger-cmd-k");

  if (!modal || !input) return;

  btnTrigger?.addEventListener("click", openCommandPalette);
  btnClose?.addEventListener("click", closeCommandPalette);

  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeCommandPalette();
  });

  input.addEventListener("input", () => {
    renderCommandPaletteResults(input.value);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      updateCommandPaletteSelection(cmdSelectedIndex + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      updateCommandPaletteSelection(cmdSelectedIndex - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (currentFilteredCommands[cmdSelectedIndex]) {
        const cmd = currentFilteredCommands[cmdSelectedIndex];
        closeCommandPalette();
        cmd.action();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      closeCommandPalette();
    }
  });
}

function openShortcutsModal() {
  const modal = document.querySelector("#shortcuts-modal");
  if (modal) modal.hidden = false;
}

function closeShortcutsModal() {
  const modal = document.querySelector("#shortcuts-modal");
  if (modal) modal.hidden = true;
}

function initShortcutsModal() {
  const modal = document.querySelector("#shortcuts-modal");
  const btnClose = document.querySelector("#btn-close-shortcuts");
  const btnHelp = document.querySelector("#btn-shortcuts-help");

  btnHelp?.addEventListener("click", openShortcutsModal);
  btnClose?.addEventListener("click", closeShortcutsModal);

  modal?.addEventListener("click", (e) => {
    if (e.target === modal) closeShortcutsModal();
  });
}

function initGlobalShortcuts() {
  document.addEventListener("keydown", (e) => {
    const isInputActive = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
    const cmdPaletteModal = document.querySelector("#command-palette-modal");
    const isCmdPaletteOpen = cmdPaletteModal && !cmdPaletteModal.hidden;
    const shortcutsModal = document.querySelector("#shortcuts-modal");
    const isShortcutsOpen = shortcutsModal && !shortcutsModal.hidden;

    // Ctrl+K / Cmd+K toggle
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      if (isCmdPaletteOpen) {
        closeCommandPalette();
      } else {
        openCommandPalette();
      }
      return;
    }

    // Escape closes modals
    if (e.key === "Escape") {
      if (isCmdPaletteOpen) {
        closeCommandPalette();
        return;
      }
      if (isShortcutsOpen) {
        closeShortcutsModal();
        return;
      }
      const realModal = document.querySelector("#real-mode-modal");
      if (realModal && !realModal.hidden) {
        realModal.hidden = true;
        return;
      }
      const copilotWin = document.querySelector("#copilot-window");
      if (copilotWin && !copilotWin.hidden && document.activeElement?.id === "copilot-input") {
        copilotWin.hidden = true;
        return;
      }
    }

    // Do NOT trigger single-key navigation if typing in an input or textarea
    if (isInputActive) return;

    if (e.key === "/") {
      e.preventDefault();
      openCommandPalette();
    } else if (e.key === "?") {
      e.preventDefault();
      openShortcutsModal();
    } else if (e.key === "1") {
      applyWorkspaceViewMode("workflow");
      showToast("View mode: 🎯 8-Step Workflow", "info", 1500);
    } else if (e.key === "2") {
      applyWorkspaceViewMode("portfolio");
      showToast("View mode: 📊 Portfolio Hub", "info", 1500);
    } else if (e.key === "3") {
      applyWorkspaceViewMode("quantlab");
      showToast("View mode: 🔬 Quant Lab & Charts", "info", 1500);
    } else if (e.key === "4") {
      applyWorkspaceViewMode("all");
      showToast("View mode: 🌐 Continuous Layout (All Panels)", "info", 1500);
    } else if (e.key === "5") {
      selectBrokerTab("resources");
      showToast("Tab: 📚 Resource Hub & RAG", "info", 1500);
    } else if (e.key === "c" || e.key === "C") {
      document.querySelector("#btn-topbar-copilot")?.click();
    } else if (e.key === "r" || e.key === "R") {
      loadPortfolio(currentBroker);
      showToast(`Refreshed ${currentBroker.toUpperCase()} portfolio`, "info", 1500);
    } else if (e.key === "m" || e.key === "M") {
      document.querySelector("#mode-toggle-btn")?.click();
    }
  });
}

/* =========================================================================
   8. RESOURCE HUB & OPEN-WEBUI KNOWLEDGE INGESTION CONTROLLER
   ========================================================================= */

let currentResourceCategory = "ALL";
let allLoadedResources = [];
let currentViewResourceId = null;

async function loadResourcesHub() {
  const grid = document.querySelector("#resources-grid");
  const owuDot = document.querySelector("#res-owu-dot");
  const owuText = document.querySelector("#res-owu-status-text");
  const hudTotal = document.querySelector("#hud-total-resources");
  const hudSynced = document.querySelector("#hud-synced-resources");
  const hudLastTime = document.querySelector("#hud-last-sync-time");
  const hudLastStatus = document.querySelector("#hud-last-sync-status");
  const logsTbody = document.querySelector("#res-sync-logs-tbody");

  // 1. Fetch Sync Status & Telemetry
  try {
    const statusRes = await fetch("/api/resources/sync/status");
    if (statusRes.ok) {
      const data = await statusRes.json();
      const isOwuOnline = data.openwebui && data.openwebui.status === "online";
      if (owuDot) owuDot.className = isOwuOnline ? "status-dot status-dot-online" : "status-dot status-dot-offline";
      if (owuText) owuText.textContent = isOwuOnline ? `OWU: ONLINE (${data.openwebui.latency_ms}ms)` : `OWU: ${data.openwebui?.status?.toUpperCase() || "OFFLINE"}`;
      if (hudTotal) hudTotal.textContent = String(data.total_resources || 0);
      if (hudSynced) hudSynced.textContent = String(data.synced_resources || 0);
      if (hudLastTime) {
        if (data.last_synced_at && data.last_synced_at !== "Never") {
          const d = new Date(data.last_synced_at);
          hudLastTime.textContent = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        } else {
          hudLastTime.textContent = "Never";
        }
      }
      if (hudLastStatus) {
        hudLastStatus.textContent = `${data.synced_resources || 0}/${data.total_resources || 0} Synced to Vector KB`;
      }

      // Update Category Badge Counts
      if (data.category_counts) {
        const counts = data.category_counts;
        const setCt = (id, count) => {
          const el = document.querySelector(`#${id}`);
          if (el) el.textContent = String(count || 0);
        };
        setCt("count-all", data.total_resources);
        setCt("count-equation", counts.EQUATION);
        setCt("count-historical_data", counts.HISTORICAL_DATA);
        setCt("count-sec_data", counts.SEC_DATA);
        setCt("count-company", counts.COMPANY);
        setCt("count-calendar", counts.CALENDAR);
        setCt("count-website", counts.WEBSITE);
      }

      // Populate Audit Logs
      if (logsTbody && data.recent_sync_logs && data.recent_sync_logs.length > 0) {
        logsTbody.innerHTML = data.recent_sync_logs.map(log => `
          <tr>
            <td style="font-family:var(--mono);">${log.id}</td>
            <td><span class="badge ${log.trigger_type === 'NIGHTLY_CRON' ? 'badge-company' : 'badge-historical_data'}">${log.trigger_type}</span></td>
            <td style="font-family:var(--mono);">${log.synced_at.replace("T", " ").slice(0, 19)}</td>
            <td style="color:#34d399; font-weight:600;">${log.items_synced}</td>
            <td style="color:${log.items_failed > 0 ? '#ef4444' : 'var(--muted)'};">${log.items_failed}</td>
            <td><span class="res-sync-badge ${log.status === 'SUCCESS' ? 'is-synced' : 'is-pending'}">${log.status}</span></td>
            <td style="font-family:var(--mono);">${log.duration_ms}ms</td>
          </tr>
        `).join("");
      }
    }
  } catch (err) {
    console.warn("Could not fetch resource sync status:", err);
  }

  // 2. Fetch Resources List
  try {
    const url = currentResourceCategory === "ALL" 
      ? "/api/resources" 
      : `/api/resources?category=${encodeURIComponent(currentResourceCategory)}`;
    const res = await fetch(url);
    if (res.ok) {
      const data = await res.json();
      allLoadedResources = data.resources || [];
      renderResourcesGrid(allLoadedResources);
    }
  } catch (err) {
    if (grid) grid.innerHTML = `<div class="empty-cell" style="padding:20px; color:#ef4444;">Failed to load resources: ${err.message}</div>`;
  }
}

function renderResourcesGrid(resources) {
  const grid = document.querySelector("#resources-grid");
  if (!grid) return;

  if (!resources || resources.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 36px 20px; text-align: center; background: var(--surface); border: 1px dashed var(--line); border-radius: var(--radius);">
        <p style="font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 6px;">No resources found in this category.</p>
        <p style="font-size: 12.5px; color: var(--muted); margin-bottom: 16px;">Click "+ Add Resource" above or click "↻ Seed Quant Library" to re-seed default formulas.</p>
        <button type="button" class="button button-primary" onclick="document.querySelector('#btn-open-add-resource')?.click()">+ Add First Resource</button>
      </div>
    `;
    return;
  }

  grid.innerHTML = resources.map(res => {
    const catClass = `badge-${res.category.toLowerCase()}`;
    const isSynced = Boolean(res.openwebui_file_id);
    const syncBadge = isSynced 
      ? `<span class="res-sync-badge is-synced">✓ VECTORIZED</span>`
      : `<span class="res-sync-badge is-pending">⏳ PENDING SYNC</span>`;

    let cleanDate = "Never";
    if (res.updated_at) {
      cleanDate = res.updated_at.replace("T", " ").slice(0, 16) + " UTC";
    }

    return `
      <div class="resource-card" data-id="${res.id}">
        <div class="res-card-header">
          <div class="res-card-badges">
            <span class="res-category-badge ${catClass}">${res.category.replace("_", " ")}</span>
            ${syncBadge}
          </div>
          <span style="font-family:var(--mono); font-size:10px; color:var(--quiet);">${res.id.slice(0, 16)}</span>
        </div>
        <div>
          <h4 class="res-card-title">${escapeHtml(res.title)}</h4>
          <p class="res-card-summary">${escapeHtml(res.summary || res.content.slice(0, 140))}</p>
        </div>
        <div class="res-card-meta">
          <span>Source: ${escapeHtml((res.source_url_or_path || "Direct Input").slice(0, 28))}</span>
          <span>${cleanDate}</span>
        </div>
        <div class="res-card-actions">
          <button type="button" class="button button-small" onclick="viewResourceDetail('${res.id}')">📄 View Dossier</button>
          <button type="button" class="button button-small button-danger" onclick="deleteResourceItem('${res.id}', '${escapeHtml(res.title)}')">🗑️</button>
        </div>
      </div>
    `;
  }).join("");
}

async function viewResourceDetail(resourceId) {
  try {
    const res = await fetch(`/api/resources/${resourceId}`);
    if (!res.ok) return;
    const data = await res.json();
    const r = data.resource;
    currentViewResourceId = r.id;

    const modal = document.querySelector("#modal-view-resource");
    const titleEl = document.querySelector("#view-res-title");
    const badgesEl = document.querySelector("#view-res-badges");
    const metaEl = document.querySelector("#view-res-meta");
    const summaryEl = document.querySelector("#view-res-summary");
    const contentEl = document.querySelector("#view-res-content");

    if (titleEl) titleEl.textContent = r.title;
    if (badgesEl) {
      const catClass = `badge-${r.category.toLowerCase()}`;
      const isSynced = Boolean(r.openwebui_file_id);
      badgesEl.innerHTML = `
        <span class="res-category-badge ${catClass}">${r.category.replace("_", " ")}</span>
        <span class="res-sync-badge ${isSynced ? 'is-synced' : 'is-pending'}">${isSynced ? '✓ VECTORIZED IN OPEN-WEBUI' : '⏳ PENDING SYNC'}</span>
      `;
    }
    if (metaEl) {
      metaEl.innerHTML = `
        <span>ID: <code>${r.id}</code></span>
        <span>Source: <strong>${escapeHtml(r.source_url_or_path || 'Manual')}</strong></span>
        <span>Updated: <strong>${r.updated_at ? r.updated_at.slice(0, 19).replace('T', ' ') : 'N/A'}</strong></span>
        <span>Auto-Sync: <strong>${r.auto_update ? 'YES (02:00 UTC)' : 'NO'}</strong></span>
      `;
    }
    if (summaryEl) {
      summaryEl.textContent = r.summary || "No executive summary provided.";
    }
    if (contentEl) {
      contentEl.textContent = r.content;
    }

    if (modal) modal.hidden = false;
  } catch (err) {
    showToast(`Failed to view resource: ${err.message}`, "error", 2500);
  }
}

async function deleteResourceItem(resourceId, title) {
  if (!confirm(`Are you sure you want to delete "${title}"? This will also remove it from Open-WebUI vector memory.`)) {
    return;
  }
  try {
    const res = await fetch(`/api/resources/${resourceId}`, { method: "DELETE" });
    if (res.ok) {
      showToast(`Deleted resource: ${title}`, "info", 2000);
      const viewModal = document.querySelector("#modal-view-resource");
      if (viewModal) viewModal.hidden = true;
      loadResourcesHub();
    } else {
      const err = await res.json();
      showToast(`Deletion failed: ${err.message}`, "error", 3000);
    }
  } catch (err) {
    showToast(`Deletion error: ${err.message}`, "error", 3000);
  }
}

function initResourceHub() {
  // Category Pill Filter Clicks
  document.querySelectorAll(".res-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".res-pill").forEach(p => p.classList.remove("is-active"));
      pill.classList.add("is-active");
      currentResourceCategory = pill.dataset.category || "ALL";
      loadResourcesHub();
    });
  });

  // Search Input live filtering
  const searchInput = document.querySelector("#res-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const q = searchInput.value.toLowerCase().trim();
      if (!q) {
        renderResourcesGrid(allLoadedResources);
        return;
      }
      const filtered = allLoadedResources.filter(r => 
        (r.title && r.title.toLowerCase().includes(q)) ||
        (r.summary && r.summary.toLowerCase().includes(q)) ||
        (r.content && r.content.toLowerCase().includes(q)) ||
        (r.category && r.category.toLowerCase().includes(q)) ||
        (r.id && r.id.toLowerCase().includes(q))
      );
      renderResourcesGrid(filtered);
    });
  }

  // Modals management
  const addModal = document.querySelector("#modal-add-resource");
  const viewModal = document.querySelector("#modal-view-resource");
  const btnOpenAdd = document.querySelector("#btn-open-add-resource");
  const btnCloseAdd = document.querySelector("#btn-close-add-resource");
  const btnCancelAdd = document.querySelector("#btn-cancel-add-resource");
  const btnCloseView = document.querySelector("#btn-close-view-resource");
  const btnDismissView = document.querySelector("#btn-dismiss-view-resource");
  const btnDeleteView = document.querySelector("#btn-delete-view-resource");

  if (btnOpenAdd) btnOpenAdd.addEventListener("click", () => { if (addModal) addModal.hidden = false; });
  if (btnCloseAdd) btnCloseAdd.addEventListener("click", () => { if (addModal) addModal.hidden = true; });
  if (btnCancelAdd) btnCancelAdd.addEventListener("click", () => { if (addModal) addModal.hidden = true; });
  if (btnCloseView) btnCloseView.addEventListener("click", () => { if (viewModal) viewModal.hidden = true; });
  if (btnDismissView) btnDismissView.addEventListener("click", () => { if (viewModal) viewModal.hidden = true; });
  if (btnDeleteView) {
    btnDeleteView.addEventListener("click", () => {
      if (currentViewResourceId) {
        deleteResourceItem(currentViewResourceId, "selected resource");
      }
    });
  }

  // Ingest Mode Tabs (Manual vs URL vs Upload)
  const modeBtns = document.querySelectorAll(".res-mode-btn");
  let activeMode = "manual";
  modeBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      modeBtns.forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      activeMode = btn.dataset.mode;

      const secManual = document.querySelector("#res-mode-manual");
      const secUrl = document.querySelector("#res-mode-url");
      const secUpload = document.querySelector("#res-mode-upload");
      if (secManual) secManual.hidden = activeMode !== "manual";
      if (secUrl) secUrl.hidden = activeMode !== "url";
      if (secUpload) secUpload.hidden = activeMode !== "upload";
    });
  });

  // CSV Dropzone
  const dropzone = document.querySelector("#csv-dropzone");
  const fileInput = document.querySelector("#add-res-file");
  const fileNameLabel = document.querySelector("#selected-file-name");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.style.borderColor = "var(--accent)";
    });
    dropzone.addEventListener("dragleave", () => {
      dropzone.style.borderColor = "var(--line)";
    });
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.style.borderColor = "var(--line)";
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        if (fileNameLabel) fileNameLabel.textContent = `Selected: ${fileInput.files[0].name} (${(fileInput.files[0].size / 1024).toFixed(1)} KB)`;
      }
    });
    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length > 0) {
        if (fileNameLabel) fileNameLabel.textContent = `Selected: ${fileInput.files[0].name} (${(fileInput.files[0].size / 1024).toFixed(1)} KB)`;
      }
    });
  }

  // Add Resource Form Submission
  const addForm = document.querySelector("#form-add-resource");
  const addStatus = document.querySelector("#add-res-status");

  if (addForm) {
    addForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (addStatus) {
        addStatus.textContent = "Ingesting and synthesizing resource...";
        addStatus.className = "status-msg";
      }

      const category = document.querySelector("#add-res-category")?.value || "WEBSITE";
      const title = document.querySelector("#add-res-title-input")?.value || "";
      const summary = document.querySelector("#add-res-summary")?.value || "";
      const content = document.querySelector("#add-res-content")?.value || "";
      const url = document.querySelector("#add-res-url")?.value || "";
      const tags = document.querySelector("#add-res-tags")?.value || "";
      const autoUpdate = document.querySelector("#add-res-autoupdate")?.checked ? 1 : 0;

      try {
        if (activeMode === "upload") {
          // Multipart file upload
          if (!fileInput.files || fileInput.files.length === 0) {
            throw new Error("Please select a CSV or JSON file to upload.");
          }
          const fd = new FormData();
          fd.append("file", fileInput.files[0]);
          fd.append("symbol", document.querySelector("#add-res-csv-symbol")?.value || "ASSET");
          fd.append("timeframe", document.querySelector("#add-res-csv-timeframe")?.value || "1d");
          if (title) fd.append("title", title);

          const res = await fetch("/api/resources/upload", { method: "POST", body: fd });
          const data = await res.json();
          if (!res.ok) throw new Error(data.message || "Upload failed");
          showToast(`Ingested historical dataset: ${data.resource?.title}`, "success", 2500);
        } else if (activeMode === "url") {
          // URL Ingestion
          if (!url) throw new Error("Please enter a valid web URL.");
          const res = await fetch("/api/resources", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              category: "WEBSITE",
              title: title || url,
              source_url_or_path: url,
              auto_update: autoUpdate,
              metadata_json: { tags: tags.split(",").map(t => t.trim()).filter(Boolean) }
            })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.message || "URL ingestion failed");
          showToast(`Ingested web resource: ${data.resource?.title}`, "success", 2500);
        } else {
          // Manual input
          if (!content) throw new Error("Please enter document content or formula code.");
          const res = await fetch("/api/resources", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              category,
              title,
              summary,
              content,
              auto_update: autoUpdate,
              metadata_json: { tags: tags.split(",").map(t => t.trim()).filter(Boolean) }
            })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.message || "Failed to save resource");
          showToast(`Saved resource: ${data.resource?.title}`, "success", 2500);
        }

        if (addModal) addModal.hidden = true;
        addForm.reset();
        loadResourcesHub();
      } catch (err) {
        if (addStatus) {
          addStatus.textContent = err.message;
          addStatus.className = "status-msg color-red";
        }
        showToast(`Resource error: ${err.message}`, "error", 3000);
      }
    });
  }

  // Trigger Open-WebUI Sync
  const btnSyncNow = document.querySelector("#btn-sync-resources-now");
  if (btnSyncNow) {
    btnSyncNow.addEventListener("click", async () => {
      btnSyncNow.disabled = true;
      btnSyncNow.textContent = "⚡ Syncing to Open-WebUI...";
      showToast("Syncing all resources to Open-WebUI RAG vector storage...", "info", 3000);

      try {
        const res = await fetch("/api/resources/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: true })
        });
        const data = await res.json();
        if (data.status === "offline") {
          showToast(`Open-WebUI offline: ${data.message}`, "error", 3500);
        } else {
          showToast(`Open-WebUI Sync: ${data.items_synced} files vectorized in ${data.duration_ms}ms`, "success", 3000);
        }
        loadResourcesHub();
      } catch (err) {
        showToast(`Sync error: ${err.message}`, "error", 3000);
      } finally {
        btnSyncNow.disabled = false;
        btnSyncNow.textContent = "⚡ Sync Open-WebUI Now";
      }
    });
  }

  // Trigger Nightly Refresh Run
  const btnNightlyRun = document.querySelector("#btn-run-nightly-now");
  if (btnNightlyRun) {
    btnNightlyRun.addEventListener("click", async () => {
      btnNightlyRun.disabled = true;
      btnNightlyRun.textContent = "🌙 Running Nightly Sync...";
      showToast("Executing automated 02:00 UTC nightly refresh routine...", "info", 3000);

      try {
        const res = await fetch("/api/resources/nightly-run", { method: "POST" });
        const data = await res.json();
        const synced = data.sync_result?.items_synced || 0;
        showToast(`Nightly refresh complete: ${data.refreshed_resources?.length || 0} feeds updated, ${synced} vectorized in ${data.duration_ms}ms`, "success", 3500);
        loadResourcesHub();
      } catch (err) {
        showToast(`Nightly refresh error: ${err.message}`, "error", 3000);
      } finally {
        btnNightlyRun.disabled = false;
        btnNightlyRun.textContent = "🌙 Nightly Refresh";
      }
    });
  }

  // Seed default quant library button
  const btnSeed = document.querySelector("#btn-seed-resources");
  if (btnSeed) {
    btnSeed.addEventListener("click", async () => {
      showToast("Seeding foundational quant formulas and profiles...", "info", 2000);
      try {
        const res = await fetch("/api/resources/nightly-run", { method: "POST" });
        if (res.ok) {
          showToast("Quant knowledge base seeded and refreshed!", "success", 2500);
          loadResourcesHub();
        }
      } catch (e) {
        showToast(`Seed failed: ${e.message}`, "error", 2500);
      }
    });
  }

  // Refresh sync logs button
  const btnRefreshLogs = document.querySelector("#btn-refresh-sync-logs");
  if (btnRefreshLogs) {
    btnRefreshLogs.addEventListener("click", () => {
      loadResourcesHub();
      showToast("Refreshed sync audit logs", "info", 1500);
    });
  }
}

// Global initialization of new workflow & copilot modules
initWorkflowController();
initQuantCopilot();
initAdminControls();
initCommandPalette();
initShortcutsModal();
initResourceHub();
initGlobalShortcuts();
applyWorkspaceViewMode();
renderWatchlist();