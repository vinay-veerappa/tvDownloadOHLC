"""C4: ICT Context from HTF Parquet.

Computes PDH/PDL/midnight open/weekly H/L from 1d and 1W parquet files.
No full 1m historical needed — uses HTF parquet (~0.5s vs 3-5s).

.. note::
    As of ICT Phase 1, this module delegates to ``ict_data_loader.py``
    which reads from derived ICT parquets first and falls back to live
    computation. The original logic is preserved as a fallback path
    inside ``load_ict_context``.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
_REPO = Path(__file__).parent.parent.parent.parent

# ET session anchors
RTH_START_HOUR = 9
RTH_START_MIN = 30
RTH_END_HOUR = 16
MIDNIGHT_HOUR = 0


def compute_ict_from_htf(ticker: str = "NQ1", current_price: float = 0) -> dict:
    """Compute ICT levels from derived parquets with live fallback.

    Delegates to ``ict_data_loader.load_ict_context`` which reads from
    ``data/derived/ICT/{sym}_htf_levels.parquet`` first, falling back
    to direct 1d/1W parquet reads if the derived data is unavailable.

    Returns:
        dict with pdh, pdl, midnight_open, pwh, pwl, premium_discount, dealing_range_pct
    """
    from scripts.trader.signals.ict_data_loader import load_ict_context
    return load_ict_context(ticker=ticker, current_price=current_price)


def format_ict_block(ict: dict) -> str:
    lines = ["== ICT DEALING RANGE =="]
    if ict["pdh"] is None:
        return "== ICT DEALING RANGE ==\nNo daily parquet data"
    lines.append(f"PDH: {ict['pdh']:.2f} | PDL: {ict['pdl']:.2f} | PDC: {ict['pdc']:.2f}")
    if ict["midnight_open"]:
        lines.append(f"Midnight Open: {ict['midnight_open']:.2f}")
    if ict["dealing_range_pct"] is not None:
        lines.append(f"Price in {ict['premium_discount']} ({ict['dealing_range_pct']:.1f}% of PDH-PDL range)")
        lines.append(f"  R:R filter — {'longs poor R:R in premium' if ict['premium_discount'] == 'PREMIUM' else 'shorts poor R:R in discount'}")
    if ict["pwh"]:
        lines.append(f"Weekly: PWH {ict['pwh']:.2f} | PWL {ict['pwl']:.2f} | Position: {ict.get('weekly_range_pct', 'N/A')}%")
    lines.append(f"BSL: {ict.get('bsl_target', 'N/A')} | SSL: {ict.get('ssl_target', 'N/A')}")
    return "\n".join(lines)