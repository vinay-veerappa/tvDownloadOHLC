"""
Unit and integration tests for CSP Ranking & Scoring System
"""

import pytest
from datetime import date
from scripts.csp_ranking.tos_parser import TOSOptionContract
from scripts.csp_ranking.finviz_client import FinvizTickerProfile
from scripts.csp_ranking.technicals import TechnicalMetrics
from scripts.csp_ranking.scoring_engine import ScoredCandidate, rank_csp_candidates


def test_tos_option_contract_parsing():
    raw = {
        "Symbol": ".DELL260925P390",
        "Description": "DELL 100 (Weeklys) 25 SEP 26 390 PUT",
        "Last": "8.19",
        "Net Chng": "-1.81",
        "%Change": "-18.10%",
        "Volume": "21",
        "Bid": "7.90",
        "Ask": "9.30",
        "Delta": "-.17",
        "Gamma": ".00",
        "Theta": "-.44",
        "Vega": ".30",
    }
    scan_date = date(2026, 8, 31)
    contract = TOSOptionContract(raw, scan_date=scan_date)

    assert contract.ticker == "DELL"
    assert contract.strike == 390.0
    assert contract.expiry_date == date(2026, 9, 25)
    assert contract.dte == 25
    assert contract.bid == 7.90
    assert contract.ask == 9.30
    assert contract.mid_price == 8.60
    assert round(contract.spread, 2) == 1.40
    assert contract.volume == 21
    assert contract.delta == -0.17
    assert contract.ror_pct == pytest.approx(2.0256, rel=1e-2)
    assert contract.annualized_ror_pct == pytest.approx(29.574, rel=1e-2)


def test_hard_filter_low_volume():
    raw = {
        "Symbol": ".XYZ260925P100",
        "Description": "XYZ 25 SEP 26 100 PUT",
        "Last": "2.00",
        "Volume": "2",  # Less than min 10
        "Bid": "1.80",
        "Ask": "2.20",
        "Delta": "-0.15",
    }
    contract = TOSOptionContract(raw, scan_date=date(2026, 8, 31))
    cand = ScoredCandidate(contract=contract, profile=None, technicals=None, min_volume=10)
    
    assert cand.is_passed_hard_filters is False
    assert any("Volume" in r for r in cand.exclusion_reasons)


def test_hard_filter_wide_spread():
    raw = {
        "Symbol": ".XYZ260925P100",
        "Description": "XYZ 25 SEP 26 100 PUT",
        "Last": "2.00",
        "Volume": "50",
        "Bid": "0.50",
        "Ask": "2.50", # Spread is 2.00 / 1.50 = 133% > 50%
        "Delta": "-0.15",
    }
    contract = TOSOptionContract(raw, scan_date=date(2026, 8, 31))
    cand = ScoredCandidate(contract=contract, profile=None, technicals=None, max_spread_pct=50.0)
    
    assert cand.is_passed_hard_filters is False
    assert any("Spread" in r for r in cand.exclusion_reasons)


def test_hard_filter_earnings_overlap():
    raw = {
        "Symbol": ".XYZ260925P100",
        "Description": "XYZ 25 SEP 26 100 PUT",
        "Volume": "50",
        "Bid": "1.90",
        "Ask": "2.10",
        "Delta": "-0.15",
    }
    scan_date = date(2026, 8, 31)
    contract = TOSOptionContract(raw, scan_date=scan_date)
    
    # Earnings on Sep 10 (before expiry on Sep 25)
    finviz_raw = {
        "Price": "110",
        "Earnings": "Sep 10 AMC",
        "EPS Q/Q": "25.0%",
        "Sales Q/Q": "15.0%",
    }
    profile = FinvizTickerProfile("XYZ", finviz_raw)
    
    cand = ScoredCandidate(contract=contract, profile=profile, technicals=None, scan_date=scan_date)
    assert cand.is_passed_hard_filters is False
    assert any("Earnings" in r for r in cand.exclusion_reasons)


def test_scoring_and_adjustments():
    raw = {
        "Symbol": ".LEAD260925P100",
        "Description": "LEAD 25 SEP 26 100 PUT",
        "Volume": "120",
        "Bid": "3.00",
        "Ask": "3.15",
        "Delta": "-0.15",
    }
    scan_date = date(2026, 8, 31)
    contract = TOSOptionContract(raw, scan_date=scan_date)

    finviz_raw = {
        "Price": "120",
        "P/E": "25.0",
        "Earnings": "Nov 15 AMC", # After expiration
        "EPS Q/Q": "35.0%",
        "Sales Q/Q": "22.0%",
        "SMA50": "10.0%",
        "SMA200": "25.0%",
    }
    profile = FinvizTickerProfile("LEAD", finviz_raw)
    
    technicals = TechnicalMetrics(
        ticker="LEAD",
        current_price=120.0,
        sma50=108.0,
        sma200=95.0,
        is_rs_above_ma=True,
    )

    cand = ScoredCandidate(contract=contract, profile=profile, technicals=technicals, scan_date=scan_date)
    assert cand.is_passed_hard_filters is True
    assert cand.rs_adj_pts == 5      # RS > MA
    assert cand.sales_adj_pts == 5   # Growing
    assert cand.eps_adj_pts == 5     # Accelerating
    assert cand.final_score >= 80.0
