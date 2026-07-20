import pytest

from scripts.screener.core.funnel import fetch_finviz_candidates
from scripts.screener.core.float_validator import validate_float

def test_validate_float_cross_check():
    """Verify float cross-validation handles matching vs disparate share counts."""
    # Test matching float (<15% difference)
    match_res = validate_float(finviz_float=50e6, yf_float=52e6)
    assert match_res["is_valid"] is True
    assert match_res["discrepancy_pct"] < 15.0

    # Test disparate float (>15% difference)
    disparate_res = validate_float(finviz_float=50e6, yf_float=80e6)
    assert disparate_res["is_valid"] is False
    assert disparate_res["discrepancy_pct"] > 15.0

def test_finviz_funnel_fetch():
    """Verify Finviz funnel queries top candidates with rate-limit insulation."""
    candidates = fetch_finviz_candidates(limit=5)
    assert isinstance(candidates, list)
    if len(candidates) > 0:
        cand = candidates[0]
        assert "ticker" in cand
        assert "sector" in cand
        assert "industry" in cand
