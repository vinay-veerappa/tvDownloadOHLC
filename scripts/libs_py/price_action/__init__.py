"""
Price Action & Leading Market Microstructure Library.
=====================================================
Public API exports:
- Rejection & Absorption: detect_level_rejection
- Break & Retest State Machine: detect_break_and_retest
- Al Brooks Microstructure: classify_brooks_bars, detect_h1_h2_l1_l2
- Leading Volatility & Efficiency: compute_kaufman_efficiency, compute_ttm_squeeze, compute_bar_overlap
"""
from __future__ import annotations

from scripts.libs_py.price_action.rejection_engine import detect_level_rejection
from scripts.libs_py.price_action.break_and_retest import detect_break_and_retest
from scripts.libs_py.price_action.al_brooks import classify_brooks_bars, detect_h1_h2_l1_l2
from scripts.libs_py.price_action.volatility_leading import (
    compute_kaufman_efficiency,
    compute_ttm_squeeze,
    compute_bar_overlap,
)

__all__ = [
    "detect_level_rejection",
    "detect_break_and_retest",
    "classify_brooks_bars",
    "detect_h1_h2_l1_l2",
    "compute_kaufman_efficiency",
    "compute_ttm_squeeze",
    "compute_bar_overlap",
]
