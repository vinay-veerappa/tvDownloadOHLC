from __future__ import annotations

from datetime import date
import pytest
from scripts.market_data.discord_earnings_notifier import (
    parse_reactions,
    calculate_vol_edge,
    calculate_straddle_breakevens,
    calculate_iv_rank,
    calculate_expected_move_levels,
    build_eod_payload
)

def test_parse_reactions():
    reactions_str = "Feb26 (1d%): +2.2%, Nov25 (1d%): -0.5%, Aug25 (1d%): +3.7%"
    parsed = parse_reactions(reactions_str)
    assert len(parsed) == 3
    assert parsed[0] == pytest.approx(0.022)
    assert parsed[1] == pytest.approx(0.005)
    assert parsed[2] == pytest.approx(0.037)

    empty_str = "N/A"
    assert parse_reactions(empty_str) == []


def test_calculate_vol_edge_three_tiers():
    # 1. Edge >= 1.8 -> RICH
    reactions_str = "Mar26 (1d%): +5.0%, Dec25 (1d%): -5.0%"
    edge_ratio, avg_abs_realized, marker, tier = calculate_vol_edge(0.10, reactions_str)
    assert edge_ratio == pytest.approx(2.0)
    assert avg_abs_realized == pytest.approx(0.05)
    assert marker == "🟢"
    assert "RICH" in tier

    # Boundary Rich: Edge = 1.8 -> RICH
    edge_ratio, avg_abs_realized, marker, tier = calculate_vol_edge(0.09, reactions_str)
    assert edge_ratio == pytest.approx(1.8)
    assert marker == "🟢"
    assert "RICH" in tier

    # 2. 0.9 <= Edge < 1.8 -> FAIR
    edge_ratio, avg_abs_realized, marker, tier = calculate_vol_edge(0.05, reactions_str)
    assert edge_ratio == pytest.approx(1.0)
    assert marker == "🟡"
    assert tier == "FAIR"

    # Boundary Fair Low: Edge = 0.9 -> FAIR
    edge_ratio, avg_abs_realized, marker, tier = calculate_vol_edge(0.045, reactions_str)
    assert edge_ratio == pytest.approx(0.9)
    assert marker == "🟡"
    assert tier == "FAIR"

    # 3. Edge < 0.9 -> CHEAP
    edge_ratio, avg_abs_realized, marker, tier = calculate_vol_edge(0.025, reactions_str)
    assert edge_ratio == pytest.approx(0.5)
    assert marker == "🔵"
    assert "CHEAP" in tier


def test_calculate_straddle_breakevens():
    spot = 100.0
    call_mid = 3.50
    put_mid = 2.50
    straddle_cost, lower_be, upper_be, priced_move_pct = calculate_straddle_breakevens(spot, call_mid, put_mid)
    
    assert straddle_cost == 6.00
    assert lower_be == 94.00
    assert upper_be == 106.00
    assert priced_move_pct == pytest.approx(0.06)


def test_calculate_iv_rank():
    # Normal case: Current 50, low 20, high 80 -> Rank = 50%
    assert calculate_iv_rank(50.0, 80.0, 20.0) == pytest.approx(50.0)
    
    # Boundary: Current 80, low 20, high 80 -> Rank = 100%
    assert calculate_iv_rank(80.0, 80.0, 20.0) == pytest.approx(100.0)
    
    # Boundary: Range is zero
    assert calculate_iv_rank(50.0, 50.0, 50.0) == 0.0

    # Fallbacks
    assert calculate_iv_rank(None, 80.0, 20.0) is None
    assert calculate_iv_rank(50.0, None, 20.0) is None
    assert calculate_iv_rank(50.0, 80.0, None) is None


def test_calculate_expected_move_levels():
    spot = 200.0
    priced_move = 0.10
    lower, upper = calculate_expected_move_levels(spot, priced_move)
    assert lower == 183.0
    assert upper == 217.0


def test_magnitude_sort_order():
    # Tickers with different edges:
    # Ticker A: Edge = 2.0 (magnitude abs(2.0 - 1.0) = 1.0) (RICH)
    # Ticker B: Edge = 0.5 (magnitude abs(0.5 - 1.0) = 0.5) (CHEAP)
    # Ticker C: Edge = 1.0 (magnitude abs(1.0 - 1.0) = 0.0) (FAIR)
    # Ticker D: Edge = 1.5 (magnitude abs(1.5 - 1.0) = 0.5) (FAIR)
    # Target sort order (BMO/AMC): A (1.0) -> B (0.5) -> D (0.5) -> C (0.0)
    # Ticker B and D have the same magnitude (0.5). Under higher edge first: D (1.5) should sort before B (0.5).
    # So expected: A -> D -> B -> C.
    
    events = [
        {"ticker": "TICKERA", "beforeMarket": False},
        {"ticker": "TICKERB", "beforeMarket": False},
        {"ticker": "TICKERC", "beforeMarket": False},
        {"ticker": "TICKERD", "beforeMarket": False},
    ]
    
    metadata = {
        "TICKERA": {
            "spot": 100.0,
            "expected_move": 0.20,
            "straddle_cost": 20.0,
            "reactions": "Mar26 (1d%): +10.0%" # Avg realized 10.0%, Edge = 2.0x
        },
        "TICKERB": {
            "spot": 100.0,
            "expected_move": 0.05,
            "straddle_cost": 5.0,
            "reactions": "Mar26 (1d%): +10.0%" # Avg realized 10.0%, Edge = 0.5x
        },
        "TICKERC": {
            "spot": 100.0,
            "expected_move": 0.10,
            "straddle_cost": 10.0,
            "reactions": "Mar26 (1d%): +10.0%" # Avg realized 10.0%, Edge = 1.0x
        },
        "TICKERD": {
            "spot": 100.0,
            "expected_move": 0.15,
            "straddle_cost": 15.0,
            "reactions": "Mar26 (1d%): +10.0%" # Avg realized 10.0%, Edge = 1.5x
        }
    }
    
    payload = build_eod_payload(events, date(2026, 6, 3), metadata)
    
    # Check that AMC block exists and has fields
    assert len(payload["embeds"]) == 1
    fields = payload["embeds"][0]["fields"]
    amc_field = [f for f in fields if "AMC" in f["name"]][0]
    
    # Verify the order of tickers in the formatted AMC text
    # Should be TICKERA -> TICKERD -> TICKERB -> TICKERC
    value_text = amc_field["value"]
    pos_a = value_text.find("TICKERA")
    pos_d = value_text.find("TICKERD")
    pos_b = value_text.find("TICKERB")
    pos_c = value_text.find("TICKERC")
    
    assert pos_a != -1
    assert pos_d != -1
    assert pos_b != -1
    assert pos_c != -1
    
    assert pos_a < pos_d < pos_b < pos_c
