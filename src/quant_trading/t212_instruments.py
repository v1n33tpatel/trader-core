"""
Trading 212 Invest & Stocks and Shares ISA Instrument Catalog & Smart Taxonomy Classifier.

Categorizes 14,200+ traditional investments across 5 Core Pillars:
1. Global Stocks (9,000+ shares across UK, US, Germany, Netherlands, Switzerland, Spain)
2. Exchange-Traded Funds (5,000+ ETFs across global indices, sectors, bonds)
3. Investment Trusts & REITs (~200 property and closed-end trust products)
4. Exchange-Traded Commodities (ETCs for physically backed gold, silver, oil)
5. Crypto ETNs (London Stock Exchange listed cryptocurrency notes)

Provides ETF facet screening:
- Distribution Policy: Dividend Paying (Dist) vs Auto-Compounding (Acc)
- Themes: Global Indices, Sectors & Themes, Fixed Income & Bonds, High Dividend & Aristocrats
- FX Drag: Native GBX (0.0% FX Fee) vs foreign currency listings (0.15% FX conversion fee)
"""

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from brokers.t212_adapter import normalize_t212_ticker

logger = logging.getLogger("T212Instruments")


@dataclass(frozen=True)
class T212Instrument:
    ticker: str
    clean_symbol: str
    name: str
    short_name: str
    isin: str
    currency: str
    type: str
    pillar: str  # STOCKS, ETFS, REITS, ETCS, CRYPTO_ETNS
    etf_type: Optional[str]  # DIVIDEND_DIST, ACCUMULATING, GLOBAL_INDICES, SECTORS_THEMES, BONDS, OTHER
    is_dividend_paying: bool
    is_native_gbx: bool
    extended_hours: bool
    working_schedule_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Comprehensive seed catalog of benchmark UK/US/European instruments
DEFAULT_SEED_INSTRUMENTS: List[Dict[str, Any]] = [
    # --- ETFS: Global Indices (Dist & Acc) ---
    {"ticker": "VUSA_l_EQ", "name": "Vanguard S&P 500 UCITS ETF (Dist)", "shortName": "VUSA", "isin": "IE00B3XXRP09", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "VUAG_l_EQ", "name": "Vanguard S&P 500 UCITS ETF (Acc)", "shortName": "VUAG", "isin": "IE00BFMXXD54", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "EQQQ_l_EQ", "name": "Invesco EQQQ NASDAQ-100 UCITS ETF (Dist)", "shortName": "EQQQ", "isin": "IE0032077012", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "QQQA_l_EQ", "name": "Invesco NASDAQ-100 UCITS ETF (Acc)", "shortName": "QQQA", "isin": "IE00BFZXG277", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "VUKE_l_EQ", "name": "Vanguard FTSE 100 UCITS ETF (Dist)", "shortName": "VUKE", "isin": "IE00B810Q511", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "VUKG_l_EQ", "name": "Vanguard FTSE 100 UCITS ETF (Acc)", "shortName": "VUKG", "isin": "IE00BFMXYC85", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "VWRL_l_EQ", "name": "Vanguard FTSE All-World UCITS ETF (Dist)", "shortName": "VWRL", "isin": "IE00B3RBWM25", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "VWCE_l_EQ", "name": "Vanguard FTSE All-World UCITS ETF (Acc)", "shortName": "VWCE", "isin": "IE00BK5BQT80", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "SWDA_l_EQ", "name": "iShares Core MSCI World UCITS ETF (Acc)", "shortName": "SWDA", "isin": "IE00B4L5Y983", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "IWRD_l_EQ", "name": "iShares Core MSCI World UCITS ETF (Dist)", "shortName": "IWRD", "isin": "IE00B0M62Q58", "currencyCode": "GBX", "type": "ETF"},
    # --- ETFS: High Dividend & Income ---
    {"ticker": "IUKD_l_EQ", "name": "iShares UK Dividend UCITS ETF (Dist)", "shortName": "IUKD", "isin": "IE00B0M63060", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "VHYL_l_EQ", "name": "Vanguard FTSE All-World High Dividend Yield UCITS ETF (Dist)", "shortName": "VHYL", "isin": "IE00B8GKDB10", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "SPYD_l_EQ", "name": "SPDR S&P US Dividend Aristocrats UCITS ETF (Dist)", "shortName": "SPYD", "isin": "IE00B6YX5D40", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "FUSD_l_EQ", "name": "Fidelity US Quality Income UCITS ETF (Dist)", "shortName": "FUSD", "isin": "IE00BYXVGX24", "currencyCode": "GBX", "type": "ETF"},
    # --- ETFS: Sectors & Themes ---
    {"ticker": "IITU_l_EQ", "name": "iShares S&P 500 Information Technology Sector UCITS ETF (Acc)", "shortName": "IITU", "isin": "IE00B3WJKG14", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "INRG_l_EQ", "name": "iShares Global Clean Energy UCITS ETF (Dist)", "shortName": "INRG", "isin": "IE00B1XNHC34", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "SMGB_l_EQ", "name": "VanEck Semiconductor UCITS ETF (Acc)", "shortName": "SMGB", "isin": "IE00BMC38736", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "WTAI_l_EQ", "name": "WisdomTree Artificial Intelligence UCITS ETF (Acc)", "shortName": "WTAI", "isin": "IE00BDVPNG13", "currencyCode": "GBX", "type": "ETF"},
    # --- ETFS: Fixed Income & Bonds ---
    {"ticker": "VGOV_l_EQ", "name": "Vanguard U.K. Gilt UCITS ETF (Dist)", "shortName": "VGOV", "isin": "IE00B42WWV65", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "IGLT_l_EQ", "name": "iShares Core UK Gilts UCITS ETF (Dist)", "shortName": "IGLT", "isin": "IE00B1FZSB30", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "LQDE_l_EQ", "name": "iShares $ Corp Bond UCITS ETF (Dist)", "shortName": "LQDE", "isin": "IE0032895942", "currencyCode": "GBX", "type": "ETF"},
    # --- REITs & Investment Trusts ---
    {"ticker": "LAND_l_EQ", "name": "Land Securities Group PLC REIT", "shortName": "LAND", "isin": "GB00BYW0VQ64", "currencyCode": "GBX", "type": "STOCK"},
    {"ticker": "BLND_l_EQ", "name": "British Land Company PLC REIT", "shortName": "BLND", "isin": "GB0001367019", "currencyCode": "GBX", "type": "STOCK"},
    {"ticker": "SGRO_l_EQ", "name": "SEGRO PLC REIT", "shortName": "SGRO", "isin": "GB00B5ZN1N88", "currencyCode": "GBX", "type": "STOCK"},
    {"ticker": "SMT_l_EQ", "name": "Scottish Mortgage Investment Trust PLC", "shortName": "SMT", "isin": "GB00BLDYK618", "currencyCode": "GBX", "type": "STOCK"},
    {"ticker": "CTY_l_EQ", "name": "City of London Investment Trust PLC", "shortName": "CTY", "isin": "GB0001990497", "currencyCode": "GBX", "type": "STOCK"},
    # --- ETCs: Physical Commodities ---
    {"ticker": "SGLN_l_EQ", "name": "iShares Physical Gold ETC", "shortName": "SGLN", "isin": "IE00B4ND3602", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "PHAU_l_EQ", "name": "WisdomTree Physical Gold ETC", "shortName": "PHAU", "isin": "JE00B1VS3770", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "SSLN_l_EQ", "name": "iShares Physical Silver ETC", "shortName": "SSLN", "isin": "IE00B4NCWG09", "currencyCode": "GBX", "type": "ETF"},
    {"ticker": "PHAG_l_EQ", "name": "WisdomTree Physical Silver ETC", "shortName": "PHAG", "isin": "JE00B1VS3333", "currencyCode": "GBX", "type": "ETF"},
    # --- Crypto ETNs (London Stock Exchange) ---
    {"ticker": "WBIT_l_EQ", "name": "WisdomTree Physical Bitcoin ETN (GBP)", "shortName": "WBIT", "isin": "GB00BJYDH287", "currencyCode": "GBX", "type": "CRYPTOCURRENCY"},
    {"ticker": "WETH_l_EQ", "name": "WisdomTree Physical Ethereum ETN (GBP)", "shortName": "WETH", "isin": "GB00BJYDH402", "currencyCode": "GBX", "type": "CRYPTOCURRENCY"},
    {"ticker": "2BTC_l_EQ", "name": "21Shares Bitcoin Core ETN (GBP)", "shortName": "2BTC", "isin": "CH1199067674", "currencyCode": "GBX", "type": "CRYPTOCURRENCY"},
    # --- Global Stocks (UK, US, European) ---
    {"ticker": "AAPL_US_EQ", "name": "Apple Inc", "shortName": "AAPL", "isin": "US0378331005", "currencyCode": "USD", "type": "STOCK"},
    {"ticker": "MSFT_US_EQ", "name": "Microsoft Corporation", "shortName": "MSFT", "isin": "US5949181045", "currencyCode": "USD", "type": "STOCK"},
    {"ticker": "NVDA_US_EQ", "name": "NVIDIA Corporation", "shortName": "NVDA", "isin": "US67066G1040", "currencyCode": "USD", "type": "STOCK"},
    {"ticker": "AMZN_US_EQ", "name": "Amazon.com Inc", "shortName": "AMZN", "isin": "US0231351067", "currencyCode": "USD", "type": "STOCK"},
    {"ticker": "GOOGL_US_EQ", "name": "Alphabet Inc (Class A)", "shortName": "GOOGL", "isin": "US02079K3059", "currencyCode": "USD", "type": "STOCK"},
    {"ticker": "TSLA_US_EQ", "name": "Tesla Inc", "shortName": "TSLA", "isin": "US88160R1014", "currencyCode": "USD", "type": "STOCK"},
    {"ticker": "SHEL_l_EQ", "name": "Shell PLC", "shortName": "SHEL", "isin": "GB00BP6MXD84", "currencyCode": "GBX", "type": "STOCK"},
    {"ticker": "AZN_l_EQ", "name": "AstraZeneca PLC", "shortName": "AZN", "isin": "GB0009895292", "currencyCode": "GBX", "type": "STOCK"},
    {"ticker": "HSBA_l_EQ", "name": "HSBC Holdings PLC", "shortName": "HSBA", "isin": "GB0005405286", "currencyCode": "GBX", "type": "STOCK"},
    {"ticker": "SAP_DE_EQ", "name": "SAP SE", "shortName": "SAP", "isin": "DE0007164600", "currencyCode": "EUR", "type": "STOCK"},
    {"ticker": "ASML_AE_EQ", "name": "ASML Holding NV", "shortName": "ASML", "isin": "NL0010273215", "currencyCode": "EUR", "type": "STOCK"},
]


def classify_t212_instrument(raw: Dict[str, Any]) -> T212Instrument:
    """
    Parses a raw Trading 212 API instrument record into a rich T212Instrument taxonomy:
    - Identifies Pillar: STOCKS, ETFS, REITS, ETCS, CRYPTO_ETNS
    - Identifies ETF sub-type: DIVIDEND_DIST, ACCUMULATING, GLOBAL_INDICES, SECTORS_THEMES, BONDS, OTHER
    - Detects dividend paying policy
    - Detects UK native GBX listing (0% FX drag)
    """
    raw_ticker = str(raw.get("ticker", "")).strip()
    clean_sym = normalize_t212_ticker(raw_ticker)
    name = str(raw.get("name", "")).strip()
    short_name = str(raw.get("shortName", clean_sym.replace(".L", ""))).strip()
    isin = str(raw.get("isin", "")).strip()
    currency = str(raw.get("currencyCode", "USD")).strip().upper()
    raw_type = str(raw.get("type", "STOCK")).strip().upper()
    extended_hours = bool(raw.get("extendedHours", False))
    schedule_id = raw.get("workingScheduleId")

    name_upper = name.upper()
    ticker_upper = raw_ticker.upper()

    # 1. Determine Asset Pillar
    pillar = "STOCKS"
    etf_type: Optional[str] = None

    # Check for Crypto ETNs first
    if (
        raw_type in ("CRYPTOCURRENCY", "CRYPTO")
        or any(k in name_upper for k in ("BITCOIN", "ETHEREUM", "CRYPTO"))
        and any(k in name_upper for k in ("ETN", "ETC", "PHYSICAL"))
    ):
        pillar = "CRYPTO_ETNS"

    # Check for Physical Commodities (ETCs)
    elif any(k in name_upper for k in ("PHYSICAL GOLD", "PHYSICAL SILVER", "PHYSICAL PLATINUM", "COMMODITY ETC", "BRENT CRUDE")) or (
        "ETC" in name_upper and not any(k in name_upper for k in ("BITCOIN", "ETHEREUM"))
    ):
        pillar = "ETCS"

    # Check for Investment Trusts & REITs
    elif any(k in name_upper for k in ("REIT", "REAL ESTATE INVESTMENT", "PROPERTY TRUST", "INVESTMENT TRUST", "TRUST PLC", "CAPITAL TRUST")):
        pillar = "REITS"

    # Check for ETFs
    elif raw_type in ("ETF", "INDEX") or any(k in name_upper for k in ("UCITS", "ETF", "VANGUARD", "ISHARES", "SPDR", "INVESCO", "XTRACKERS")):
        pillar = "ETFS"

    else:
        pillar = "STOCKS"

    # 2. Determine ETF Sub-type & Dividend Policy
    is_dividend_paying = False

    if pillar == "ETFS":
        # Check distribution policy
        is_dist = bool(re.search(r"\bDIST\b|\bDISTRIBUTING\b|\bINCOME\b|\bDIVIDEND\b", name_upper))
        is_acc = bool(re.search(r"\bACC\b|\bACCUMULATING\b", name_upper))

        if is_dist or any(k in name_upper for k in ("HIGH DIVIDEND", "DIVIDEND ARISTOCRATS", "QUALITY INCOME", "DIVIDEND YIELD")):
            etf_type = "DIVIDEND_DIST"
            is_dividend_paying = True
        elif is_acc:
            etf_type = "ACCUMULATING"
        elif any(k in name_upper for k in ("TREASURY", "GILT", "CORP BOND", "BOND", "GOVERNMENT BOND", "INFLATION")):
            etf_type = "BONDS"
            is_dividend_paying = not is_acc
        elif any(k in name_upper for k in ("S&P 500", "FTSE 100", "FTSE ALL-WORLD", "MSCI WORLD", "NASDAQ", "CORE MSCI", "GLOBAL")):
            etf_type = "GLOBAL_INDICES"
            is_dividend_paying = is_dist
        elif any(k in name_upper for k in ("TECH", "CLEAN ENERGY", "SEMICONDUCTOR", "HEALTH", "FINANCIAL", "CYBER", "AI", "ROBOTICS")):
            etf_type = "SECTORS_THEMES"
            is_dividend_paying = is_dist
        else:
            etf_type = "OTHER"
            is_dividend_paying = is_dist

    elif pillar in ("REITS", "STOCKS"):
        # Stocks / REITs with explicit dividend markers
        if any(k in name_upper for k in ("REIT", "HIGH YIELD", "DIVIDEND", "TRUST")):
            is_dividend_paying = True

    # 3. Check Native GBX (0% FX Drag)
    is_native_gbx = currency in ("GBX", "GBP") or raw_ticker.endswith("_l_EQ") or clean_sym.endswith(".L")

    return T212Instrument(
        ticker=raw_ticker,
        clean_symbol=clean_sym,
        name=name,
        short_name=short_name,
        isin=isin,
        currency=currency,
        type=raw_type,
        pillar=pillar,
        etf_type=etf_type,
        is_dividend_paying=is_dividend_paying,
        is_native_gbx=is_native_gbx,
        extended_hours=extended_hours,
        working_schedule_id=schedule_id,
    )


class T212InstrumentCatalog:
    """In-memory searchable index of Trading 212 instruments."""

    def __init__(self):
        self._instruments: List[T212Instrument] = []
        self._by_ticker: Dict[str, T212Instrument] = {}
        self._last_loaded: float = 0.0
        self._cache_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "core",
            "t212_instruments_cache.json",
        )
        self.load()

    def load(self, raw_list: Optional[List[Dict[str, Any]]] = None) -> None:
        """Loads and classifies instruments from raw API data or disk/seed fallback."""
        items_to_process = raw_list

        if not items_to_process and os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    if isinstance(cached_data, list) and len(cached_data) > 0:
                        items_to_process = cached_data
            except Exception as e:
                logger.warning(f"Failed to load cached T212 instruments: {e}")

        if not items_to_process:
            items_to_process = DEFAULT_SEED_INSTRUMENTS

        parsed: List[T212Instrument] = []
        by_ticker: Dict[str, T212Instrument] = {}

        for item in items_to_process:
            try:
                inst = classify_t212_instrument(item)
                parsed.append(inst)
                by_ticker[inst.ticker] = inst
                by_ticker[inst.clean_symbol] = inst
            except Exception:
                continue

        self._instruments = parsed
        self._by_ticker = by_ticker
        self._last_loaded = time.time()
        logger.info(f"Loaded {len(self._instruments)} categorized Trading 212 instruments.")

    def save_cache(self, raw_list: List[Dict[str, Any]]) -> None:
        """Persists raw API instruments to disk cache."""
        try:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(raw_list, f)
            self.load(raw_list)
        except Exception as e:
            logger.warning(f"Failed to save T212 instruments cache: {e}")

    def get(self, identifier: str) -> Optional[T212Instrument]:
        return self._by_ticker.get(identifier.strip().upper())

    def search(
        self,
        query: str = "",
        pillar: Optional[str] = None,
        etf_type: Optional[str] = None,
        dividend_only: bool = False,
        native_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[T212Instrument], int]:
        """
        Filters instruments by pillar, ETF type, dividend policy, currency, and query text.
        Returns (results_slice, total_matching_count).
        """
        q = query.strip().upper()
        p_filter = pillar.strip().upper() if pillar and pillar.strip().upper() != "ALL" else None
        e_filter = etf_type.strip().upper() if etf_type and etf_type.strip().upper() != "ALL" else None

        filtered = []
        for inst in self._instruments:
            # Pillar filter
            if p_filter and inst.pillar != p_filter:
                continue

            # ETF Sub-type filter
            if e_filter and inst.etf_type != e_filter:
                continue

            # Dividend filter
            if dividend_only and not inst.is_dividend_paying:
                continue

            # Native GBX filter (0% FX fee)
            if native_only and not inst.is_native_gbx:
                continue

            # Text query match (ticker, clean symbol, name, or shortName)
            if q:
                match = (
                    q in inst.ticker.upper()
                    or q in inst.clean_symbol.upper()
                    or q in inst.name.upper()
                    or q in inst.short_name.upper()
                    or q in inst.isin.upper()
                )
                if not match:
                    continue

            filtered.append(inst)

        total_count = len(filtered)
        paged_results = filtered[offset : offset + limit]
        return paged_results, total_count

    def get_summary_stats(self) -> Dict[str, Any]:
        """Returns count statistics across pillars and dividend types."""
        stats = {
            "total": len(self._instruments),
            "pillars": {
                "STOCKS": sum(1 for i in self._instruments if i.pillar == "STOCKS"),
                "ETFS": sum(1 for i in self._instruments if i.pillar == "ETFS"),
                "REITS": sum(1 for i in self._instruments if i.pillar == "REITS"),
                "ETCS": sum(1 for i in self._instruments if i.pillar == "ETCS"),
                "CRYPTO_ETNS": sum(1 for i in self._instruments if i.pillar == "CRYPTO_ETNS"),
            },
            "etf_types": {
                "DIVIDEND_DIST": sum(1 for i in self._instruments if i.etf_type == "DIVIDEND_DIST"),
                "ACCUMULATING": sum(1 for i in self._instruments if i.etf_type == "ACCUMULATING"),
                "GLOBAL_INDICES": sum(1 for i in self._instruments if i.etf_type == "GLOBAL_INDICES"),
                "SECTORS_THEMES": sum(1 for i in self._instruments if i.etf_type == "SECTORS_THEMES"),
                "BONDS": sum(1 for i in self._instruments if i.etf_type == "BONDS"),
            },
            "native_gbx_count": sum(1 for i in self._instruments if i.is_native_gbx),
            "dividend_count": sum(1 for i in self._instruments if i.is_dividend_paying),
        }
        return stats


# Global singleton instance
t212_catalog = T212InstrumentCatalog()
