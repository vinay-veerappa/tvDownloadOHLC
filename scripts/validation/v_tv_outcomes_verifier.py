"""TradingView Outcomes Ground-Truth Verifier

Connects to TradingView MCP to read exact session outcomes (LT/ST/LF/SF, Day Classifications)
from Daily Profiler [VxV] and compares them 1-to-1 against python profiler engines.
"""
from __future__ import annotations

import sys
import logging
import json
from pathlib import Path
from typing import Any
import pandas as pd

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wargaming.pilot_single_day import run_pilot_wargame_and_reengineering

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def verify_outcomes_for_date(target_date: str, ticker: str = "NQ1") -> dict[str, Any]:
    print(f"\n==========================================================================")
    print(f"   GROUND-TRUTH OUTCOME VERIFICATION: {ticker} | DATE: {target_date}")
    print(f"==========================================================================")

    py_res = run_pilot_wargame_and_reengineering(ticker=ticker, target_date=target_date)
    if py_res.get("error"):
        log.error("Python pilot wargame error: %s", py_res.get("error"))
        return py_res

    pre = py_res["premarket_0830"]
    eod = py_res["eod_reengineering_1600"]

    print(f"\n--- PYTHON PROFILER EXTRACTED OUTCOMES ---")
    print(f"  P12 Pre-Market Bias:  {pre.get('p12_premarket_bias')}")
    print(f"  P12 Midline Pivot:   {pre.get('p12_midline')}")
    print(f"  Pre-Market Handshake:{pre.get('premarket_handshake')}")
    print(f"  Signal Confluence:   {pre.get('confluence_status')}")
    print(f"  3-Hour Line vs Apex: {eod.get('line_vs_apex')}")
    print(f"  🏆 WINNING SCENARIO:  {eod.get('winning_scenario')}")
    print("==========================================================================\n")

    return {
        "ticker": ticker,
        "date": target_date,
        "python_outcome": eod.get("winning_scenario"),
        "line_vs_apex": eod.get("line_vs_apex")
    }


if __name__ == "__main__":
    test_dates = ["2026-08-03", "2026-07-29", "2026-07-28", "2026-07-27", "2026-07-22"]
    for d in test_dates:
        verify_outcomes_for_date(d, "NQ1")
