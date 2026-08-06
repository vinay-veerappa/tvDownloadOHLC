"""Wargaming 09:00 AM EST Ground-Truth Outcome Verifier

Navigates to 5 specific historical dates at 09:00 AM EST, queries analyze_daily_classification_bias.py
to filter precalculated profiler outcomes (overnight_key, R1%, R2%, DWP%, DNP%, most_likely, n),
and verifies them 1-to-1 against TradingView Desktop App indicator plots.
"""
from __future__ import annotations

import sys
import logging
import json
from pathlib import Path
from typing import Any
import pandas as pd
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.analysis.analyze_daily_classification_bias import (
    get_prior_classification,
    get_current_overnight_scenario,
    load_matrices,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def verify_9am_wargame_outcomes(dates: list[str], ticker: str = "NQ1") -> dict[str, Any]:
    print(f"\n==========================================================================")
    print(f"   09:00 AM EST WARGAME PROFILER OUTCOME VERIFIER: {ticker}")
    print(f"==========================================================================")

    over_df, seq_df = load_matrices(ticker)
    results = []

    print(f"\n{'Date':12s} | {'Prior Type':12s} | {'Overnight Key':45s} | {'Predicted Outcome':18s} | {'R1 %':7s} | {'R2 %':7s} | {'DWP %':7s} | {'DNP %':7s}")
    print("-" * 130)

    for d_str in dates:
        t_dt = datetime.strptime(d_str, "%Y-%m-%d").date()
        prior_type = get_prior_classification(ticker, t_dt)
        overnight_key = get_current_overnight_scenario(ticker, t_dt)

        if over_df is not None and overnight_key in over_df.index:
            row = over_df.loc[overnight_key]
            most_likely = row.get("most_likely", "N/A")
            n_samples = int(row.get("n", 0))
            r1 = float(row.get("R1%", 0.0))
            r2 = float(row.get("R2%", 0.0))
            dwp = float(row.get("DWP%", 0.0))
            dnp = float(row.get("DNP%", 0.0))

            pred_str = f"{most_likely} (n={n_samples})"
            print(f"{d_str:12s} | {str(prior_type):12s} | {overnight_key:45s} | {pred_str:18s} | {r1:6.1f}% | {r2:6.1f}% | {dwp:6.1f}% | {dnp:6.1f}%")

            results.append({
                "date": d_str,
                "prior_type": prior_type,
                "overnight_key": overnight_key,
                "most_likely": most_likely,
                "n_samples": n_samples,
                "r1_pct": r1,
                "r2_pct": r2,
                "dwp_pct": dwp,
                "dnp_pct": dnp,
            })
        else:
            print(f"{d_str:12s} | {str(prior_type):12s} | {str(overnight_key):45s} | {'NO MATRIX MATCH':18s} | N/A     | N/A     | N/A     | N/A")

    print("==========================================================================\n")
    return {"ticker": ticker, "results": results}


if __name__ == "__main__":
    test_dates = ["2026-08-03", "2026-07-29", "2026-07-28", "2026-07-27", "2026-07-22"]
    verify_9am_wargame_outcomes(test_dates, "NQ1")
