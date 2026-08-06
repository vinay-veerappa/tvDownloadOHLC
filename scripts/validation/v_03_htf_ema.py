"""Validation Script: HTF Weekly EMA(5) Excursion Engine (Step 0.3)

Tests compute_htf_ema_analysis() for NQ1 and ES1.
Verifies Weekly EMA(5) calculation, 52-week excursion percentiles (Mean, Median, Mode),
2%-3% magnet zone detection, and NFP Friday anomaly detection.
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.wargaming.htf_ema_analysis import (
    compute_htf_ema_analysis,
    format_htf_ema_block,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def validate_htf_ema_for_ticker(ticker: str) -> bool:
    print(f"\n==================================================")
    print(f"   VALIDATING HTF EMA ANALYSIS FOR TICKER: {ticker}")
    print(f"==================================================")

    res = compute_htf_ema_analysis(ticker=ticker)
    
    print(f"    Target Date: {res.get('target_date')}")
    print(f"    Weekly EMA(5): {res.get('weekly_ema5')}")
    print(f"    Current Distance %: {res.get('dist_pct')}%")
    print(f"    2%-3% Zone Active: {res.get('is_2to3_zone')}")
    print(f"    NFP Friday: {res.get('is_nfp_friday')}")
    print(f"    dUp Stats (Upward): {res.get('dup_stats')} (Bin: {res.get('binned_modes', {}).get('dup_mode_bin')})")
    print(f"    dDn Stats (Downward): {res.get('ddn_stats')} (Bin: {res.get('binned_modes', {}).get('ddn_mode_bin')})")

    if res.get("weekly_ema5") is None:
        print(f"❌ FAIL: Weekly EMA(5) returned None for {ticker}")
        return False

    print(f"✅ HTF EMA Pass for {ticker}")
    print("\nFormatted HTF EMA Block:")
    print("-" * 40)
    print(format_htf_ema_block(res))
    print("-" * 40)

    return True


def main():
    tickers = ["NQ1", "ES1"]
    all_passed = True

    for ticker in tickers:
        try:
            ok = validate_htf_ema_for_ticker(ticker)
            if not ok:
                all_passed = False
        except Exception as e:
            print(f"❌ ERROR validating HTF EMA for {ticker}: {e}")
            all_passed = False

    print("\n==================================================")
    if all_passed:
        print("🎉 ALL HTF EMA VALIDATION TESTS PASSED!")
    else:
        print("❌ HTF EMA VALIDATION FAILED FOR SOME TICKERS.")
    print("==================================================\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
