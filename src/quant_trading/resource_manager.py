import os
import re
import io
import time
import uuid
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union

import pandas as pd
import requests

from core.state_store import StateStore
from feeds.openwebui_client import OpenWebUIClient
from feeds.agent_c import AgentCSentinel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_RESOURCES_DIR = PROJECT_ROOT / "data" / "resources"


class ResourceManager:
    """
    Central Manager for the TraderCore Resource Hub & Knowledge Ingestion Engine.
    Handles ingestion of Websites, Historical CSV datasets, SEC Filings,
    Company Fundamentals, Equations, and Live Economic Calendars.
    Synthesizes RAG markdown dossiers and synchronizes them with Open-WebUI vector storage.
    """

    KNOWLEDGE_BASE_NAME = "TraderCore Resources & Research Hub"
    KNOWLEDGE_BASE_DESC = (
        "Curated financial resources: SEC filings, quant formulas, company profiles, "
        "historical data summaries, and live economic calendars."
    )

    def __init__(
        self,
        state_store: Optional[StateStore] = None,
        openwebui_client: Optional[OpenWebUIClient] = None,
        resources_dir: Optional[Path] = None
    ):
        self.store = state_store or StateStore()
        self.owu = openwebui_client or OpenWebUIClient()
        self.resources_dir = resources_dir or DATA_RESOURCES_DIR
        self.resources_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 1. RAG Markdown Dossier Synthesis
    # =========================================================================

    @staticmethod
    def synthesize_markdown_dossier(resource: Dict[str, Any]) -> str:
        """
        Formats a resource into an institutional RAG markdown document
        with metadata headers optimized for semantic recall by Open-WebUI and Ollama nomic-embed-text.
        """
        res_id = resource.get("id", "res_unknown")
        category = resource.get("category", "GENERAL").upper()
        title = resource.get("title", "Untitled Document")
        source = resource.get("source_url_or_path", "Direct Ingestion")
        summary = resource.get("summary", "").strip()
        content = resource.get("content", "").strip()
        updated_at = resource.get("updated_at") or datetime.now(timezone.utc).isoformat()

        meta = {}
        raw_meta = resource.get("metadata_json")
        if isinstance(raw_meta, str) and raw_meta.strip():
            try:
                meta = json.loads(raw_meta)
            except Exception:
                meta = {}
        elif isinstance(raw_meta, dict):
            meta = raw_meta

        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        tag_str = " ".join([f"#{t.lower().replace(' ', '_').replace('-', '_')}" for t in tags])

        symbol = meta.get("symbol", "").upper()
        symbol_line = f"- **Asset/Ticker**: `{symbol}`\n" if symbol else ""

        dossier = (
            f"# [RESOURCE: {category}] {title}\n\n"
            f"- **Resource ID**: `{res_id}`\n"
            f"- **Category**: `{category}`\n"
            f"- **Source**: {source}\n"
            f"{symbol_line}"
            f"- **Last Updated**: {updated_at}\n"
            f"- **Tags**: #{category.lower()} {tag_str}\n\n"
            f"## Executive Summary\n"
            f"{summary or 'No summary provided.'}\n\n"
            f"---\n\n"
            f"## Full Content & Structured Data\n\n"
            f"{content}\n"
        )
        return dossier

    # =========================================================================
    # 2. Historical Data CSV Parser & Statistical Profiler
    # =========================================================================

    def parse_historical_csv(
        self,
        file_content: Union[str, bytes],
        filename: str = "dataset.csv",
        symbol: str = "ASSET",
        timeframe: str = "1d",
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses historical CSV price data (OHLCV), validates numeric sanity,
        computes quantitative profile (returns, annualized volatility, Sharpe, max drawdown, POC),
        and returns a resource payload dict ready to be persisted.
        """
        if isinstance(file_content, bytes):
            buf = io.BytesIO(file_content)
        else:
            buf = io.StringIO(file_content)

        df = pd.read_csv(buf)
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Identify key columns
        time_col = None
        for cand in ["timestamp", "time", "date", "datetime", "open_time"]:
            if cand in df.columns:
                time_col = cand
                break

        close_col = "close" if "close" in df.columns else None
        high_col = "high" if "high" in df.columns else None
        low_col = "low" if "low" in df.columns else None
        open_col = "open" if "open" in df.columns else None
        vol_col = "volume" if "volume" in df.columns else ("vol" if "vol" in df.columns else None)

        if not close_col:
            raise ValueError(f"CSV missing mandatory 'close' price column. Found: {list(df.columns)}")

        # Convert numeric
        for col in [open_col, high_col, low_col, close_col, vol_col]:
            if col and col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=[close_col])
        if len(df) == 0:
            raise ValueError("CSV contains no valid numeric rows for 'close' price.")

        total_bars = len(df)
        min_price = float(df[close_col].min())
        max_price = float(df[close_col].max())
        start_price = float(df[close_col].iloc[0])
        end_price = float(df[close_col].iloc[-1])
        pct_change_total = round(((end_price - start_price) / max(0.00001, start_price)) * 100, 2)

        start_date = str(df[time_col].iloc[0]) if time_col else "Bar 0"
        end_date = str(df[time_col].iloc[-1]) if time_col else f"Bar {total_bars - 1}"

        # Returns and Volatility
        returns = df[close_col].pct_change().dropna()
        mean_return = float(returns.mean()) if len(returns) > 0 else 0.0
        std_return = float(returns.std()) if len(returns) > 0 else 0.0

        # Annualization factor
        is_crypto = symbol.upper().endswith("USDT") or symbol.upper() in ("BTC", "ETH", "SOL", "AVAX", "XRP")
        ann_factor = (365.0 ** 0.5) if is_crypto else (252.0 ** 0.5)
        if "1h" in timeframe.lower():
            ann_factor = ((365.0 * 24.0) ** 0.5) if is_crypto else ((252.0 * 6.5) ** 0.5)
        elif "15m" in timeframe.lower():
            ann_factor = ((365.0 * 24.0 * 4.0) ** 0.5) if is_crypto else ((252.0 * 26.0) ** 0.5)

        ann_volatility = round(std_return * ann_factor * 100, 2)
        sharpe = round((mean_return / max(std_return, 1e-8)) * ann_factor, 2) if std_return > 0 else 0.0

        # Maximum Drawdown
        cum_ret = (1 + returns).cumprod()
        running_max = cum_ret.cummax()
        drawdown = (cum_ret - running_max) / running_max
        max_dd = round(float(drawdown.min()) * 100, 2) if len(drawdown) > 0 else 0.0

        # POC Approximation (Volume Profile Highest Volume Node)
        poc_price = round(end_price, 2)
        if vol_col and vol_col in df.columns:
            try:
                # Discretize into 20 price bins
                df["price_bin"] = pd.cut(df[close_col], bins=20)
                vol_by_bin = df.groupby("price_bin", observed=False)[vol_col].sum()
                top_bin = vol_by_bin.idxmax()
                poc_price = round(float(top_bin.mid), 2)
            except Exception:
                poc_price = round(end_price, 2)

        clean_symbol = symbol.upper().strip()
        doc_title = title or f"{clean_symbol} ({timeframe.upper()}) Historical Price Profile"
        res_id = f"hist_{clean_symbol.lower()}_{timeframe.lower()}_{uuid.uuid4().hex[:6]}"

        summary = (
            f"Historical dataset of {total_bars:,} bars spanning from {start_date} to {end_date}. "
            f"Net price movement of {pct_change_total:+0.2f}% with {ann_volatility}% annualized volatility "
            f"and a historical Sharpe ratio of {sharpe}."
        )

        content = (
            f"### Dataset Characteristics\n"
            f"- **Symbol**: `{clean_symbol}`\n"
            f"- **Timeframe**: `{timeframe}`\n"
            f"- **Sample Size**: {total_bars:,} bars\n"
            f"- **Date Range**: {start_date} to {end_date}\n"
            f"- **First Close Price**: ${start_price:,.4f}\n"
            f"- **Last Close Price**: ${end_price:,.4f}\n"
            f"- **Range (Min / Max)**: ${min_price:,.4f} — ${max_price:,.4f}\n\n"
            f"### Quantitative & Risk Metrics\n"
            f"- **Net Historical Return**: `{pct_change_total:+0.2f}%`\n"
            f"- **Annualized Volatility**: `{ann_volatility}%`\n"
            f"- **Historical Sharpe Ratio**: `{sharpe}`\n"
            f"- **Maximum Drawdown**: `{max_dd}%`\n"
            f"- **Volume Profile Point of Control (POC)**: `${poc_price:,.4f}`\n\n"
            f"### Execution Relevance\n"
            f"This profile defines structural boundaries for {clean_symbol}. "
            f"In intraday setups, the High Volume Node POC (${poc_price:,.4f}) functions as a high-probability "
            f"macro mean-reversion target and structural liquidity anchor."
        )

        metadata = {
            "symbol": clean_symbol,
            "timeframe": timeframe,
            "total_bars": total_bars,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "annualized_volatility_pct": ann_volatility,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_dd,
            "poc_price": poc_price,
            "filename": filename,
            "tags": ["historical", clean_symbol.lower(), timeframe.lower(), "data"]
        }

        return {
            "id": res_id,
            "category": "HISTORICAL_DATA",
            "title": doc_title,
            "source_url_or_path": filename,
            "summary": summary,
            "content": content,
            "metadata_json": json.dumps(metadata),
            "auto_update": 0
        }

    # =========================================================================
    # 3. Web & URL Ingestion
    # =========================================================================

    def ingest_url(
        self,
        url: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetches web content, strips HTML markup, extracts key text,
        and creates a structured WEBSITE resource.
        """
        clean_url = url.strip()
        resp = requests.get(
            clean_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TraderCore/2.0"},
            timeout=10
        )
        resp.raise_for_status()

        html_text = resp.text
        # Simple HTML tag stripping
        title_match = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
        extracted_title = title_match.group(1).strip() if title_match else clean_url

        # Strip scripts, styles, and tags
        text_no_script = re.sub(r"<(script|style).*?>.*?</\1>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
        plain_text = re.sub(r"<[^>]+>", " ", text_no_script)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()

        # Limit plain text to 10,000 chars for clean RAG ingestion
        trimmed_content = plain_text[:10000]
        doc_title = title or extracted_title
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", doc_title.lower())[:24].strip("_")
        res_id = f"web_{slug}_{uuid.uuid4().hex[:6]}"

        summary = f"Web resource extracted from {clean_url}. Contains {len(trimmed_content.split())} words."
        meta_tags = tags or ["research", "web", "article"]

        return {
            "id": res_id,
            "category": "WEBSITE",
            "title": doc_title,
            "source_url_or_path": clean_url,
            "summary": summary,
            "content": trimmed_content,
            "metadata_json": json.dumps({"tags": meta_tags, "url": clean_url}),
            "auto_update": 1
        }

    # =========================================================================
    # 4. CRUD Operations
    # =========================================================================

    def save_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Saves resource to StateStore and writes local markdown cache."""
        res_id = resource.get("id") or f"res_{uuid.uuid4().hex[:8]}"
        resource["id"] = res_id
        now = datetime.now(timezone.utc).isoformat()
        resource["updated_at"] = now
        if "created_at" not in resource:
            resource["created_at"] = now

        # Synthesize markdown dossier
        dossier = self.synthesize_markdown_dossier(resource)

        # Write to local cache
        fname = f"{res_id}.md"
        out_path = self.resources_dir / fname
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(dossier)
        except OSError:
            pass

        # Save to SQLite
        saved = self.store.save_resource(resource)
        return saved

    def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        return self.store.get_resource(resource_id)

    def list_resources(self, category: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        return self.store.list_resources(category=category, limit=limit)

    def delete_resource(self, resource_id: str) -> bool:
        """Deletes resource from StateStore, local cache, and Open-WebUI."""
        res = self.store.get_resource(resource_id)
        if not res:
            return False

        # 1. Remove from Open-WebUI if file_id exists
        owu_file_id = res.get("openwebui_file_id")
        if owu_file_id:
            try:
                kb_id = self.store.get_setting("openwebui_resource_hub_id")
                if kb_id:
                    self.owu.remove_file_from_knowledge_base(kb_id, owu_file_id)
                self.owu.delete_file(owu_file_id)
            except Exception:
                pass

        # 2. Delete local markdown file
        local_file = self.resources_dir / f"{resource_id}.md"
        if local_file.exists():
            try:
                local_file.unlink()
            except OSError:
                pass

        # 3. Delete from SQLite
        return self.store.delete_resource(resource_id)

    # =========================================================================
    # 5. Pre-Seeded Default Quant Knowledge Base
    # =========================================================================

    def seed_default_resources(self, overwrite: bool = False):
        """Initializes foundational quant formulas, SEC profiles, and calendars."""
        existing = {r["id"]: r for r in self.store.list_resources(limit=500)}

        defaults = [
            # 1. Equations: Half-Kelly Capital Allocation
            {
                "id": "eq_half_kelly",
                "category": "EQUATION",
                "title": "Half-Kelly Capital Allocation Formula",
                "source_url_or_path": "Formula Standard / RiskSentinel",
                "summary": "Mathematical formula and boundary constraints for fractional Half-Kelly position sizing.",
                "content": (
                    "### Mathematical Formulation\n"
                    "The full Kelly Criterion determines the optimal fraction $f^*$ of capital to allocate to maximize the expected logarithm of wealth:\n"
                    "$$f^* = \\frac{p \\cdot b - q}{b}$$\n"
                    "Where:\n"
                    "- $p$ = Probability of a winning trade (Win Rate).\n"
                    "- $q = 1 - p$ = Probability of a losing trade.\n"
                    "- $b$ = Payoff ratio (Net Profit / Loss per trade, with $b \\ge 2.0$ for mandatory 1:2 R:R setups).\n\n"
                    "### The Half-Kelly Invariant ($f^*_{\\text{half}}$)\n"
                    "Full Kelly maximizes logarithmic growth but subjects capital to severe drawdowns (frequently exceeding 50%). "
                    "In institutional systematic trading, we apply **Half-Kelly**:\n"
                    "$$f^*_{\\text{half}} = 0.50 \\times \\left(\\frac{p \\cdot b - q}{b}\\right)$$\n\n"
                    "### Execution Guardrails in RiskSentinel\n"
                    "1. If $f^* \\le 0$, the mathematical expectation is negative ($E[R] < 0$); **ZERO** capital may be allocated.\n"
                    "2. The computed dollar allocation is clipped strictly at the RiskSentinel hard cap: $\\min(f^*_{\\text{half}} \\cdot \\text{Equity}, \\$50.00)$.\n"
                    "3. Stop loss distance cannot exceed $2.0\\%$ of entry price."
                ),
                "metadata_json": json.dumps({"tags": ["kelly", "sizing", "equations", "risk"], "latex": True}),
                "auto_update": 0
            },
            # 2. Equations: Ornstein-Uhlenbeck Mean-Reversion Half-Life
            {
                "id": "eq_ornstein_uhlenbeck",
                "category": "EQUATION",
                "title": "Ornstein-Uhlenbeck Process & Mean-Reversion Half-Life",
                "source_url_or_path": "Formula Standard / Quant Library",
                "summary": "Stochastic differential equation for estimating optimal statistical arbitrage and mean-reversion lookback windows.",
                "content": (
                    "### Continuous-Time Formulation\n"
                    "The Ornstein-Uhlenbeck (O-U) process models mean-reverting price action or spread deviations:\n"
                    "$$dX_t = \\theta (\\mu - X_t)dt + \\sigma dW_t$$\n"
                    "Where:\n"
                    "- $\\theta$ (or $\\kappa$) = Speed of mean reversion.\n"
                    "- $\\mu$ = Long-term structural mean (e.g. Value Area POC or 200-period SMA).\n"
                    "- $\\sigma$ = Instantaneous volatility of the process.\n"
                    "- $W_t$ = Standard Wiener process (Brownian motion).\n\n"
                    "### Discrete Estimation via AR(1)\n"
                    "In discrete candle time-series, the process is estimated by regressing changes against lagged price:\n"
                    "$$\\Delta X_t = \\beta X_{t-1} + \\alpha + \\epsilon_t$$\n"
                    "Where $\\beta = -\\theta \\Delta t$.\n\n"
                    "### Mean-Reversion Half-Life ($t_{1/2}$)\n"
                    "The half-life represents the expected time required for a price shock to decay halfway back to its structural mean:\n"
                    "$$t_{1/2} = -\\frac{\\ln(2)}{\\beta} = \\frac{\\ln(2)}{\\theta}$$\n\n"
                    "### Practical Strategy Rules\n"
                    "- **Half-Life $< 5$ Bars**: Rapid mean-reversion; ideal for intraday RSI-14 and Bollinger band mean-reversion scalps.\n"
                    "- **Half-Life $> 50$ Bars**: Structural trending regime; mean-reversion strategies fail; defer to FVG breakouts or trend following."
                ),
                "metadata_json": json.dumps({"tags": ["ornstein_uhlenbeck", "mean_reversion", "equations", "stochastic"], "latex": True}),
                "auto_update": 0
            },
            # 3. Equations: Consequent Encroachment (50% FVG Midpoint)
            {
                "id": "eq_fvg_consequent_encroachment",
                "category": "EQUATION",
                "title": "Fair Value Gap & Consequent Encroachment (50% CE)",
                "source_url_or_path": "Formula Standard / Price Action",
                "summary": "Exact geometric formula for Fair Value Gap boundaries and high-probability limit order entry levels.",
                "content": (
                    "### Structural Geometry of Fair Value Gaps\n"
                    "A Fair Value Gap (FVG) is a 3-candle imbalance footprint where aggressive institutional buying or selling creates an unfilled pocket:\n"
                    "- **Bullish FVG**: Candle 3's Low is strictly greater than Candle 1's High: $\\text{Low}_3 > \\text{High}_1$.\n"
                    "- **Bearish FVG**: Candle 3's High is strictly lower than Candle 1's Low: $\\text{High}_3 < \\text{Low}_1$.\n\n"
                    "### Consequent Encroachment (CE)\n"
                    "The midpoint of the imbalance band represents the institutional equilibrium price where limit orders achieve maximum structural fill probability:\n"
                    "$$\\text{CE} = \\text{FVG}_{\\text{low}} + 0.50 \\times (\\text{FVG}_{\\text{high}} - \\text{FVG}_{\\text{low}})$$\n\n"
                    "### Execution Rule\n"
                    "Never enter at the outermost threshold of an FVG on market orders. "
                    "Place standalone limit orders strictly at the **50% CE** with structural invalidation (stop-loss) resting below the Candle 1 pivot low."
                ),
                "metadata_json": json.dumps({"tags": ["fvg", "consequent_encroachment", "price_action", "geometry"]}),
                "auto_update": 0
            },
            # 4. Equations: Sharpe & Sortino Downside Ratios
            {
                "id": "eq_sharpe_sortino",
                "category": "EQUATION",
                "title": "Sharpe & Sortino Risk-Adjusted Return Metrics",
                "source_url_or_path": "Formula Standard / Quant Metrics",
                "summary": "Formulas for evaluating risk-adjusted return and downside volatility asymmetry across daily and crypto intervals.",
                "content": (
                    "### Sharpe Ratio\n"
                    "Measures excess return per unit of total standard deviation:\n"
                    "$$\\text{Sharpe} = \\frac{\\mu - R_f}{\\sigma} \\times \\sqrt{N}$$\n\n"
                    "### Sortino Ratio (Downside Risk Focus)\n"
                    "Penalizes only negative volatility below the minimum acceptable return (MAR or $R_f$):\n"
                    "$$\\text{Sortino} = \\frac{\\mu - R_f}{\\sigma_{\\text{down}}} \\times \\sqrt{N}$$\n"
                    "Where downside deviation is:\n"
                    "$$\\sigma_{\\text{down}} = \\sqrt{\\frac{1}{T} \\sum_{t=1}^T \\min(0, R_t - R_f)^2}$$\n\n"
                    "### Annualization Multipliers ($N$)\n"
                    "- Daily Equities (252 trading days): $\\sqrt{252} \\approx 15.87$\n"
                    "- 24/7 Daily Crypto (365 days): $\\sqrt{365} \\approx 19.10$\n"
                    "- Hourly Crypto ($365 \\times 24$): $\\sqrt{8,760} \\approx 93.59$"
                ),
                "metadata_json": json.dumps({"tags": ["sharpe", "sortino", "metrics", "quant"]}),
                "auto_update": 0
            },
            # 5. SEC Filings: SPY 10-K & Structure
            {
                "id": "sec_spy_10k",
                "category": "SEC_DATA",
                "title": "SPDR S&P 500 ETF Trust (SPY) 10-K Digest",
                "source_url_or_path": "SEC EDGAR / Form 10-K",
                "summary": "SEC annual disclosure digest covering SPY trust structure, creation/redemption units, and index replication.",
                "content": (
                    "### Fund Structure & Objectives\n"
                    "- **Issuer**: State Street Global Advisors (SSGA).\n"
                    "- **Trustee**: State Street Bank and Trust Company.\n"
                    "- **Replication Strategy**: Full replication of the S&P 500 Index (500 leading large-cap US equities).\n"
                    "- **Expense Ratio**: 0.0945% per annum.\n\n"
                    "### Creation & Redemption Mechanics\n"
                    "SPY creates and redeems shares in Creation Units (typically 50,000 shares) in-kind with Authorized Participants (APs). "
                    "This institutional arbitrage mechanism keeps market price tightly anchored to the Net Asset Value (NAV).\n\n"
                    "### Regulatory Note for European / UK Retail Accounts\n"
                    "Under UK/EU PRIIPs regulations, retail investors cannot buy direct US-domiciled ETFs like SPY in standard "
                    "investment accounts. Retail execution must route through UCITS equivalents (`VUSA.L` or `VUAG.L`)."
                ),
                "metadata_json": json.dumps({"symbol": "SPY", "tags": ["sec", "10k", "spy", "etf"]}),
                "auto_update": 1
            },
            # 6. SEC Filings: NVIDIA Corporation (NVDA) 10-Q Summary
            {
                "id": "sec_nvda_10q",
                "category": "SEC_DATA",
                "title": "NVIDIA Corporation (NVDA) Form 10-Q Quarterly Report",
                "source_url_or_path": "SEC EDGAR / Form 10-Q",
                "summary": "Quarterly regulatory disclosure excerpt covering Data Center Hopper/Blackwell compute demand and gross margins.",
                "content": (
                    "### Financial Highlights & Segment Performance\n"
                    "- **Revenue**: $30.04 billion (up 122% YoY, up 15% QoQ).\n"
                    "- **Data Center Revenue**: $26.3 billion (87% of total company revenue), driven by Hopper GPU architecture shipments.\n"
                    "- **Gross Margin**: 75.1% GAAP (reflecting strong pricing power across accelerated compute stacks).\n"
                    "- **Free Cash Flow**: $13.5 billion.\n\n"
                    "### Material Risk Factors (Item 1A)\n"
                    "1. Supply chain concentration with TSMC for leading-edge CoWoS packaging.\n"
                    "2. Geopolitical and export control restrictions on advanced AI hardware shipments to specific sovereign markets.\n"
                    "3. Transition cadence to the next-generation Blackwell architecture and server thermal density constraints."
                ),
                "metadata_json": json.dumps({"symbol": "NVDA", "tags": ["sec", "10q", "nvda", "earnings"]}),
                "auto_update": 1
            },
            # 7. Companies: NVIDIA Corporation Fundamentals
            {
                "id": "comp_nvda_fundamentals",
                "category": "COMPANY",
                "title": "NVIDIA Corporation (NVDA) Valuation & Fundamentals Profile",
                "source_url_or_path": "Company Intelligence / Agent C",
                "summary": "Core institutional valuation ratios, market capitalization, growth rates, and analyst consensus.",
                "content": (
                    "### Valuation Metrics\n"
                    "- **Market Capitalization**: $3.12 Trillion USD\n"
                    "- **Trailing P/E Ratio**: 54.2x\n"
                    "- **Forward P/E (1-Year)**: 36.5x\n"
                    "- **PEG Ratio**: 1.15 (indicating valuation well supported by EPS growth rate)\n"
                    "- **Diluted EPS (TTM)**: $2.45\n"
                    "- **Beta**: 1.68 (High-beta equity index driver)\n"
                    "- **52-Week Range**: $45.20 — $140.75\n"
                    "- **Dividend Yield**: 0.03%\n"
                    "- **Analyst Consensus**: Strong Buy (88% Buy rating across coverage desks)"
                ),
                "metadata_json": json.dumps({"symbol": "NVDA", "tags": ["company", "valuation", "nvda", "equity"]}),
                "auto_update": 1
            },
            # 8. Companies: Ethereum Spot & Protocol Fundamentals
            {
                "id": "comp_eth_spot_fundamentals",
                "category": "COMPANY",
                "title": "Ethereum (ETH) Protocol & Supply Sinks Profile",
                "source_url_or_path": "On-Chain Analytics / Agent C",
                "summary": "Institutional crypto benchmark fundamentals: staking yield, fee burn, layer-2 rollups, and ETF inflows.",
                "content": (
                    "### Protocol Economics & Fundamental Metrics\n"
                    "- **Market Capitalization**: $318.4 Billion USD\n"
                    "- **Consensus Staking Yield**: ~3.2% per annum in native ETH\n"
                    "- **Total Value Locked (TVL)**: $48.5 Billion USD across Mainnet & Layer-2 Rollups\n"
                    "- **EIP-1559 Supply Burn**: ~850 ETH burned daily during elevated base fee regimes\n"
                    "- **Liquid Staking Ratio**: ~28% of total circulating supply locked in validator contracts\n\n"
                    "### Macro Trading Correlation\n"
                    "ETH exhibits high beta (1.45x) relative to BTC and equity tech benchmarks. "
                    "High-probability day trades trigger on liquidity sweeps of Equal Lows below structural psychological levels."
                ),
                "metadata_json": json.dumps({"symbol": "ETH", "tags": ["company", "crypto", "eth", "onchain"]}),
                "auto_update": 1
            },
            # 9. Calendar: Live Macro Economic Calendar
            {
                "id": "macro_economic_calendar",
                "category": "CALENDAR",
                "title": "High-Impact Tier-1 Macro Economic Calendar",
                "source_url_or_path": "Macro Intelligence / Agent C Sentinel",
                "summary": "Live schedule of high-impact US macro announcements with event risk advisories and execution halts.",
                "content": (
                    "### Upcoming High-Impact Tier-1 Schedule\n"
                    "- **US Core CPI (MoM)**: Forecast: +0.2% | Previous: +0.3% | Impact: HIGH\n"
                    "- **FOMC Interest Rate Decision**: Forecast: 4.75% | Previous: 5.00% | Impact: HIGH\n"
                    "- **Non-Farm Payrolls (NFP)**: Forecast: 175K | Previous: 142K | Impact: HIGH\n"
                    "- **Initial Jobless Claims**: Forecast: 220K | Previous: 218K | Impact: MEDIUM\n\n"
                    "### Systematic RiskSentinel Invariants\n"
                    "1. **30-Minute Binary Event Embargo**: Automated order execution halts 30 minutes prior to and 15 minutes after Tier-1 releases.\n"
                    "2. **Wick Protection**: Pre-existing stop-losses must remain anchored structurally beyond the daily average true range (ATR) to avoid stop-hunt wicks."
                ),
                "metadata_json": json.dumps({"tags": ["calendar", "macro", "cpi", "fomc", "nfp"], "event_risk": "CLEAR"}),
                "auto_update": 1
            },
            # 10. Web: Binance Liquidity Clusters Guide
            {
                "id": "web_binance_liquidity_guide",
                "category": "WEBSITE",
                "title": "Binance Spot & Futures Liquidity Clustering Framework",
                "source_url_or_path": "https://binance.com/research/liquidity-clustering",
                "summary": "Guide on how institutional algorithms utilize Equal Highs and Lows on Binance orderbooks to sweep liquidity.",
                "content": (
                    "### Liquidity Cluster Dynamics\n"
                    "In crypto spot and derivative markets, retail limit orders and stop-loss pools congregate at distinct psychological numbers "
                    "and visible chart swing points (Equal Highs / Equal Lows).\n\n"
                    "### The Sweep Mechanics\n"
                    "1. **Engineered Drive**: Smart money pushes price into an obvious cluster of resting liquidity.\n"
                    "2. **Trigger Cascade**: Retail stops execute as market orders into institutional limit absorption books.\n"
                    "3. **Sharp Reversal**: Once liquidity is filled, the price immediately snaps back inside the Value Area, printing a long rejection shadow (pinbar).\n\n"
                    "### Strategy Rule\n"
                    "Never enter breakout market orders as price touches an unswept liquidity pool. "
                    "Wait for the sweep candle to close, verify wick ratio $\\ge 50\\%$, and enter on the structural confirmation."
                ),
                "metadata_json": json.dumps({"tags": ["web", "liquidity", "binance", "orderbook"]}),
                "auto_update": 0
            }
        ]

        for item in defaults:
            item_id = item["id"]
            if overwrite or item_id not in existing:
                self.save_resource(item)

    # =========================================================================
    # 6. Open-WebUI RAG Synchronization Engine
    # =========================================================================

    def sync_to_openwebui(
        self,
        force: bool = False,
        trigger_type: str = "MANUAL_UI"
    ) -> Dict[str, Any]:
        """
        Synchronizes all local resources to Open-WebUI:
        1. Ensures Knowledge Base collection exists.
        2. Iterates over resources; uploads markdown dossiers if new or modified.
        3. Removes stale versions from Open-WebUI.
        4. Updates SQLite state with new file IDs and timestamps.
        5. Logs execution to resource_sync_logs.
        """
        t0 = time.perf_counter()
        conn_check = self.owu.check_connection()
        if conn_check.get("status") not in ("online", "unauthorized"):
            # Record failed log
            err_msg = f"Open-WebUI unreachable at {self.owu.base_url}"
            self.store.record_sync_log({
                "id": f"sync_{int(time.time())}",
                "trigger_type": trigger_type,
                "items_synced": 0,
                "items_failed": 0,
                "status": "OFFLINE",
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                "details_json": json.dumps([{"error": err_msg}])
            })
            return {
                "status": "offline",
                "message": err_msg,
                "items_synced": 0,
                "items_failed": 0,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1)
            }

        # 1. Resolve or create Knowledge Base collection
        kb_id = self.store.get_setting("openwebui_resource_hub_id")
        if not kb_id:
            kb_id = self.owu.get_or_create_knowledge_base(
                self.KNOWLEDGE_BASE_NAME,
                self.KNOWLEDGE_BASE_DESC
            )
            if kb_id:
                self.store.set_setting("openwebui_resource_hub_id", kb_id)

        all_resources = self.store.list_resources(limit=500)
        items_synced = 0
        items_failed = 0
        details = []

        for res in all_resources:
            res_id = res["id"]
            title = res["title"]
            old_file_id = res.get("openwebui_file_id")
            last_synced = res.get("last_synced_at")
            updated_at = res.get("updated_at")

            # Check if sync is needed
            needs_sync = force or not old_file_id or not last_synced or (updated_at and updated_at > last_synced)
            if not needs_sync:
                details.append({"id": res_id, "title": title, "action": "skipped_up_to_date"})
                continue

            # Synthesize markdown dossier
            dossier = self.synthesize_markdown_dossier(res)
            fname = f"{res_id}.md"
            dossier_bytes = dossier.encode("utf-8")

            # Upload to Open-WebUI
            try:
                # Remove old file if present
                if old_file_id:
                    if kb_id:
                        self.owu.remove_file_from_knowledge_base(kb_id, old_file_id)
                    self.owu.delete_file(old_file_id)

                new_file_id = self.owu.upload_file(fname, dossier_bytes, "text/markdown")
                if new_file_id:
                    if kb_id:
                        self.owu.add_file_to_knowledge_base(kb_id, new_file_id)

                    now_iso = datetime.now(timezone.utc).isoformat()
                    self.store.update_resource_sync(res_id, new_file_id, now_iso)
                    items_synced += 1
                    details.append({"id": res_id, "title": title, "action": "synced", "file_id": new_file_id})
                else:
                    items_failed += 1
                    details.append({"id": res_id, "title": title, "action": "upload_failed"})
            except Exception as e:
                items_failed += 1
                details.append({"id": res_id, "title": title, "action": "error", "error": str(e)})

        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        sync_status = "SUCCESS" if items_failed == 0 else ("PARTIAL" if items_synced > 0 else "ERROR")

        # Record Audit Log
        log_entry = {
            "id": f"sync_{int(time.time())}",
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "trigger_type": trigger_type,
            "items_synced": items_synced,
            "items_failed": items_failed,
            "status": sync_status,
            "duration_ms": duration_ms,
            "details_json": json.dumps(details)
        }
        self.store.record_sync_log(log_entry)

        return {
            "status": sync_status.lower(),
            "knowledge_base_id": kb_id,
            "items_synced": items_synced,
            "items_failed": items_failed,
            "duration_ms": duration_ms,
            "details": details
        }

    # =========================================================================
    # 7. Automated Nightly Sync Routine (02:00 UTC)
    # =========================================================================

    def run_nightly_refresh(self) -> Dict[str, Any]:
        """
        Refreshes dynamic resources (live economic calendars, company metrics)
        and executes an automated sync to Open-WebUI.
        """
        t0 = time.perf_counter()
        refreshed_resources = []

        # 1. Refresh Live Economic Calendar
        try:
            agent_c = AgentCSentinel()
            cal_data = agent_c.fetch_economic_calendar()
            events = cal_data.get("events", [])
            risk_level = cal_data.get("event_risk_level", "LOW")
            advisory = cal_data.get("risk_advisory", "")

            cal_rows = []
            for ev in events:
                cal_rows.append(
                    f"- **{ev.get('event')}** ({ev.get('country')}): "
                    f"Release: `{ev.get('release_time')}` | "
                    f"Forecast: `{ev.get('forecast')}` | Previous: `{ev.get('previous')}` | "
                    f"Impact: **{ev.get('impact')}**"
                )
            cal_body = "\n".join(cal_rows)

            cal_content = (
                f"### High-Impact Tier-1 Macro Schedule (Refreshed Nightly)\n"
                f"{cal_body}\n\n"
                f"### Event Risk Classification & Advisory\n"
                f"- **Current Macro Event Risk**: `{risk_level}`\n"
                f"- **Advisory**: {advisory}\n\n"
                f"### Execution Guardrails\n"
                f"Execution strictly pauses 30 minutes before and 15 minutes after Tier-1 reports "
                f"to protect capital from binary spread blowouts."
            )

            cal_res = self.store.get_resource("macro_economic_calendar")
            if cal_res:
                cal_res["content"] = cal_content
                cal_res["summary"] = f"Tier-1 macro schedule (Macro Event Risk: {risk_level}). Refreshed at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}."
                cal_res["updated_at"] = datetime.now(timezone.utc).isoformat()
                cal_meta = json.loads(cal_res.get("metadata_json") or "{}")
                cal_meta["event_risk"] = risk_level
                cal_meta["last_refreshed"] = datetime.now(timezone.utc).isoformat()
                cal_res["metadata_json"] = json.dumps(cal_meta)
                self.save_resource(cal_res)
                refreshed_resources.append("macro_economic_calendar")
        except Exception:
            pass

        # 2. Refresh Company Fundamentals (SPY, NVDA, TSLA, ETH)
        for sym in ["SPY", "NVDA", "TSLA", "ETH"]:
            res_id = f"comp_{sym.lower()}_fundamentals"
            res = self.store.get_resource(res_id)
            if res and res.get("auto_update", 1):
                try:
                    agent_c = AgentCSentinel()
                    profile = agent_c.fetch_company_fundamentals(sym)
                    content = (
                        f"### Valuation Metrics ({sym})\n"
                        f"- **Company Name**: {profile.get('name')}\n"
                        f"- **Sector**: {profile.get('sector')}\n"
                        f"- **Market Capitalization**: {profile.get('market_cap')}\n"
                        f"- **P/E Ratio**: {profile.get('pe_ratio')}x\n"
                        f"- **Forward P/E**: {profile.get('forward_pe')}x\n"
                        f"- **Diluted EPS**: ${profile.get('eps')}\n"
                        f"- **Beta**: {profile.get('beta')}\n"
                        f"- **52-Week Range**: {profile.get('range_52w')}\n"
                        f"- **Dividend / Staking Yield**: {profile.get('dividend_yield')}\n"
                        f"- **Next Earnings / Upgrade Date**: {profile.get('next_earnings_date')}\n"
                        f"- **Analyst Consensus**: {profile.get('analyst_consensus')}"
                    )
                    res["content"] = content
                    res["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self.save_resource(res)
                    refreshed_resources.append(res_id)
                except Exception:
                    pass

        # 3. Synchronize with Open-WebUI
        sync_result = self.sync_to_openwebui(force=False, trigger_type="NIGHTLY_CRON")

        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "status": "success",
            "refreshed_resources": refreshed_resources,
            "sync_result": sync_result,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# =============================================================================
# CLI Entrypoint for Cron or Manual Invocations
# =============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TraderCore Resource Hub & Knowledge Ingestion Engine")
    parser.add_argument("--seed", action="store_true", help="Seed default quant knowledge base")
    parser.add_argument("--sync", action="store_true", help="Sync all resources to Open-WebUI")
    parser.add_argument("--nightly-sync", action="store_true", help="Execute complete nightly refresh routine")
    args = parser.parse_args()

    rm = ResourceManager()
    if args.seed:
        print("[RESOURCE-HUB] Seeding default quantitative resources...")
        rm.seed_default_resources(overwrite=True)
        print("[RESOURCE-HUB] Seed complete.")

    if args.nightly_sync:
        print("[RESOURCE-HUB] Running complete nightly refresh routine (02:00 UTC)...")
        res = rm.run_nightly_refresh()
        print(f"[RESOURCE-HUB] Nightly refresh finished in {res.get('duration_ms')}ms. Result: {res.get('sync_result')}")
    elif args.sync:
        print("[RESOURCE-HUB] Syncing all resources to Open-WebUI...")
        res = rm.sync_to_openwebui(force=True, trigger_type="MANUAL_CLI")
        print(f"[RESOURCE-HUB] Sync complete: {res}")
