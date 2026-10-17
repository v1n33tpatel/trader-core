import pytest
from quant_trading.t212_instruments import classify_t212_instrument, T212InstrumentCatalog
from quant_trading.etf_analyzer import get_etf_profile, calculate_cost_of_investing
from main import app


def test_classify_t212_instrument_pillars():
    # 1. Global Stock
    stock = classify_t212_instrument({
        "ticker": "AAPL_US_EQ",
        "name": "Apple Inc",
        "shortName": "AAPL",
        "currencyCode": "USD",
        "type": "STOCK",
    })
    assert stock.pillar == "STOCKS"
    assert stock.clean_symbol == "AAPL"
    assert not stock.is_native_gbx

    # 2. ETF - Dividend Distributing
    vusa = classify_t212_instrument({
        "ticker": "VUSA_l_EQ",
        "name": "Vanguard S&P 500 UCITS ETF (Dist)",
        "shortName": "VUSA",
        "currencyCode": "GBX",
        "type": "ETF",
    })
    assert vusa.pillar == "ETFS"
    assert vusa.etf_type == "DIVIDEND_DIST"
    assert vusa.is_dividend_paying is True
    assert vusa.is_native_gbx is True
    assert vusa.clean_symbol == "VUSA.L"

    # 3. ETF - Accumulating
    vuag = classify_t212_instrument({
        "ticker": "VUAG_l_EQ",
        "name": "Vanguard S&P 500 UCITS ETF (Acc)",
        "shortName": "VUAG",
        "currencyCode": "GBX",
        "type": "ETF",
    })
    assert vuag.pillar == "ETFS"
    assert vuag.etf_type == "ACCUMULATING"
    assert vuag.is_dividend_paying is False
    assert vuag.is_native_gbx is True

    # 4. Investment Trust / REIT
    reit = classify_t212_instrument({
        "ticker": "LAND_l_EQ",
        "name": "Land Securities Group PLC REIT",
        "shortName": "LAND",
        "currencyCode": "GBX",
        "type": "STOCK",
    })
    assert reit.pillar == "REITS"
    assert reit.is_dividend_paying is True
    assert reit.is_native_gbx is True

    # 5. Physical Commodity (ETC)
    gold = classify_t212_instrument({
        "ticker": "SGLN_l_EQ",
        "name": "iShares Physical Gold ETC",
        "shortName": "SGLN",
        "currencyCode": "GBX",
        "type": "ETF",
    })
    assert gold.pillar == "ETCS"

    # 6. Crypto ETN
    crypto_etn = classify_t212_instrument({
        "ticker": "WBIT_l_EQ",
        "name": "WisdomTree Physical Bitcoin ETN",
        "shortName": "WBIT",
        "currencyCode": "GBX",
        "type": "CRYPTOCURRENCY",
    })
    assert crypto_etn.pillar == "CRYPTO_ETNS"


def test_t212_catalog_filtering():
    catalog = T212InstrumentCatalog()

    # Search for ETFs only
    etfs, count_etfs = catalog.search(pillar="ETFS", limit=100)
    assert count_etfs > 0
    assert all(i.pillar == "ETFS" for i in etfs)

    # Search for Dividend Distributing ETFs only
    dist_etfs, count_dist = catalog.search(pillar="ETFS", etf_type="DIVIDEND_DIST", limit=100)
    assert count_dist > 0
    assert all(i.etf_type == "DIVIDEND_DIST" for i in dist_etfs)

    # Search for Native GBX (0% FX Drag)
    native_list, count_native = catalog.search(native_only=True, limit=100)
    assert count_native > 0
    assert all(i.is_native_gbx for i in native_list)

    # Text query search
    vusa_res, _ = catalog.search(query="VUSA")
    assert len(vusa_res) >= 1
    assert vusa_res[0].clean_symbol == "VUSA.L"


def test_etf_profile_and_holdings_pie():
    profile = get_etf_profile("VUSA.L")
    assert profile.clean_symbol == "VUSA.L"
    assert profile.ongoing_charges_figure == 0.07
    assert profile.distribution_policy == "Distributing (Dist)"
    assert profile.dividend_yield_pct > 1.0

    # Verify Holdings Pie structure
    assert len(profile.holdings) == 10
    assert profile.holdings[0].ticker == "MSFT"
    top_10_weight = sum(h.weight_pct for h in profile.holdings)
    assert top_10_weight > 30.0
    assert round(top_10_weight + profile.other_holdings_weight_pct, 1) == 100.0

    # Verify Sector allocations sum to 100%
    sector_weight = sum(s.weight_pct for s in profile.sectors)
    assert round(sector_weight, 1) == 100.0

    # Verify Historical CAGR & Max Drawdown
    assert profile.performance.cagr_5y > 10.0
    assert profile.performance.max_drawdown_covid < -25.0

    # Verify Cost Simulator
    assert profile.cost_simulator["gross_pot_20y"] > profile.cost_simulator["net_pot_20y"]
    assert profile.cost_simulator["total_fee_drag_20y"] > 0


def test_t212_api_flask_endpoints():
    client = app.test_client()

    # 1. GET /api/t212/instruments
    r = client.get("/api/t212/instruments?pillar=ETFS&limit=10")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "success"
    assert len(data["results"]) <= 10
    assert "stats" in data

    # 2. GET /api/t212/etf/breakdown
    r_etf = client.get("/api/t212/etf/breakdown?ticker=VUSA.L")
    assert r_etf.status_code == 200
    data_etf = r_etf.get_json()
    assert data_etf["status"] == "success"
    assert data_etf["profile"]["clean_symbol"] == "VUSA.L"
    assert len(data_etf["profile"]["holdings"]) == 10
    assert "cost_simulator" in data_etf["profile"]

    # 3. GET /api/t212/pies
    r_pies = client.get("/api/t212/pies")
    assert r_pies.status_code == 200
    data_pies = r_pies.get_json()
    assert data_pies["status"] == "success"
