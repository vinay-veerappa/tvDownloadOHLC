"""Matt Mickey Master Profiler Batch Verifier (30-Day Ground-Truth Verification)

Loops over historical sessions for NQ1 and ES1, extracting all pre-market profiler variables
(Asia/London LT/ST/LF/SF states, Firecracker vs Broken-Broken alignment, P12 levels, 06-07 rejections,
NY opening handshake, 3-hour Line vs Apex scores, winning scenario outcomes) and saving to markdown.
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.validation.v_mickey_profiler_master_verifier import extract_python_profiler_states
from scripts.wargaming.pilot_single_day import run_pilot_wargame_and_reengineering

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def run_batch_profiler_verification(ticker: str = "NQ1", max_days: int = 20) -> Path:
    print(f"\n==========================================================================")
    print(f"   MATT MICKEY MASTER PROFILER BATCH VERIFIER: {ticker} ({max_days} days)")
    print(f"==========================================================================")

    df_1d = pd.read_parquet(REPO_ROOT / "data" / f"{ticker}_1d.parquet")
    all_dates = sorted(list(set(df_1d.index.date)))
    selected_dates = [d.strftime("%Y-%m-%d") for d in all_dates[-max_days:]]

    out_path = REPO_ROOT / "scratch" / f"master_profiler_batch_report_{ticker}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Matt Mickey Master Profiler Ground-Truth Batch Report ({ticker})\n\n")
        f.write("| Date | Asia Profile | London Profile | Overnight Alignment | P12 Mid | Handshake | Line vs Apex | Winning Outcome |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")

        for date_str in selected_dates:
            try:
                prof = extract_python_profiler_states(ticker, date_str)
                pilot = run_pilot_wargame_and_reengineering(ticker, date_str)
                eod = pilot.get("eod_reengineering_1600", {})

                if prof.get("error") or pilot.get("error"):
                    continue

                f.write(
                    f"| {date_str} | {prof['asia_profile']} | {prof['london_profile']} | "
                    f"{prof['alignment']} | {prof['p12_mid']} | {prof['handshake']} | "
                    f"{eod.get('line_vs_apex')} | {eod.get('winning_scenario')} |\n"
                )
                f.flush()

            except Exception as e:
                log.warning("Skipping %s %s: %s", ticker, date_str, e)

    print(f"\n==========================================================================")
    print(f"🎉 MASTER PROFILER BATCH VERIFICATION COMPLETE!")
    print(f"  Report saved to: {out_path}")
    print(f"==========================================================================\n")

    return out_path


if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    days_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    run_batch_profiler_verification(ticker_arg, days_arg)
