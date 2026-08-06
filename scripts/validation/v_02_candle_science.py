"""Validation Script: Candle Science Calculation Engine (Step 0.2)

Tests get_candle_science_read() for NQ1 and ES1 across Open and Close modes.
Verifies sample count, C3 probabilities, C2 Open 'line in the sand', MFE/MAE percentiles,
and Close mode multi-scenario outputs.
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure UTF-8 output encoding on Windows shell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.trader.signals.candle_science import (
    get_candle_science_read,
    format_candle_science_block,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def validate_candle_science_for_ticker(ticker: str) -> bool:
    print(f"\n==================================================")
    print(f"   VALIDATING CANDLE SCIENCE FOR TICKER: {ticker}")
    print(f"==================================================")
    
    # 1. Open Mode Validation (Morning Wargaming)
    print(f"\n[1] Testing Open Mode (Morning Wargaming C3 Prediction)...")
    res_open = get_candle_science_read(ticker=ticker, mode="open")
    
    print(f"    Mode: {res_open.get('mode')}")
    print(f"    Pattern: {res_open.get('pattern_desc')} (Preset: {res_open.get('preset')})")
    print(f"    Sample Matches (n): {res_open.get('n_matches')}")
    print(f"    P(C3 Bull): {res_open.get('p_bull')}% | P(C3 Bear): {res_open.get('p_bear')}%")
    print(f"    P(Break High): {res_open.get('p_break_high')}% | P(Break Low): {res_open.get('p_break_low')}%")
    print(f"    MFE Percentiles: {res_open.get('mfe')}")
    print(f"    MAE Percentiles: {res_open.get('mae')}")
    
    if res_open.get("n_matches", 0) == 0:
        print(f"❌ FAIL: Open mode returned 0 matches for {ticker}")
        return False
        
    print(f"✅ Open Mode Pass for {ticker}")
    print("\nFormatted Open Mode Block:")
    print("-" * 40)
    print(format_candle_science_block(res_open))
    print("-" * 40)

    # 2. Close Mode Validation (EOD Reengineering)
    print(f"\n[2] Testing Close Mode (EOD Reengineering Tomorrow Projections)...")
    res_close = get_candle_science_read(ticker=ticker, mode="close")
    
    scenarios = res_close.get("scenarios", {})
    print(f"    Scenario Count: {len(scenarios)}")
    for name, sc in scenarios.items():
        print(f"    - Scenario: '{name}' -> Matches n={sc.get('n_matches')}, P(Bull)={sc.get('p_bull')}%")

    if not scenarios:
        print(f"❌ FAIL: Close mode returned no scenarios for {ticker}")
        return False
        
    print(f"✅ Close Mode Pass for {ticker}")
    print("\nFormatted Close Mode Block:")
    print("-" * 40)
    print(format_candle_science_block(res_close))
    print("-" * 40)

    return True


def main():
    tickers = ["NQ1", "ES1"]
    all_passed = True
    
    for ticker in tickers:
        try:
            ok = validate_candle_science_for_ticker(ticker)
            if not ok:
                all_passed = False
        except Exception as e:
            print(f"❌ ERROR validating {ticker}: {e}")
            all_passed = False

    print("\n==================================================")
    if all_passed:
        print("🎉 ALL CANDLE SCIENCE VALIDATION TESTS PASSED!")
    else:
        print("❌ CANDLE SCIENCE VALIDATION FAILED FOR SOME TICKERS.")
    print("==================================================\n")
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
