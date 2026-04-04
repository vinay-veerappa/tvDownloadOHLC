"""
Before/After verification: re-runs all nqstats verifiers and compares
output CSVs via MD5 hash to prove nothing changed.
"""
import pandas as pd
import os
import hashlib
import importlib
import sys

RESULTS_DIR = "scripts/nqstats/results"

SCRIPTS = {
    "Morning Judas":    ("scripts.nqstats.morning_judas.verify_judas",    "judas_verification.csv"),
    "Noon Curve":       ("scripts.nqstats.noon_curve.verify_noon_curve",  "noon_curve_verification.csv"),
    "1H Continuation":  ("scripts.nqstats.1h_continuation.verify_1h_continuation", "1h_continuation_verification.csv"),
    "Net Change SDevs": ("scripts.nqstats.net_change_sdevs.verify_sdevs", "sdev_verification.csv"),
    "IB Breaks":        ("scripts.nqstats.initial_balance.verify_ib_breaks", "ib_breaks_verification.csv"),
    "RTH Breaks":       ("scripts.nqstats.rth_breaks.verify_rth_breaks",  "rth_breaks_verification.csv"),
}


def file_hash(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def main():
    # 1. Snapshot BEFORE hashes
    before = {}
    for name, (_, csv) in SCRIPTS.items():
        path = os.path.join(RESULTS_DIR, csv)
        if os.path.exists(path):
            before[csv] = file_hash(path)
        else:
            before[csv] = None

    # 2. Re-run each script (overwrites the CSV)
    print("=== BEFORE/AFTER VERIFICATION ===")
    print("Re-running all verifier scripts...\n")

    for name, (mod_path, csv) in SCRIPTS.items():
        try:
            # Force reimport
            if mod_path in sys.modules:
                del sys.modules[mod_path]
            mod = importlib.import_module(mod_path)
            mod.main()
        except Exception as e:
            print(f"  ERROR running {name}: {e}")

    # 3. Compare hashes
    print("\n" + "=" * 60)
    print("COMPARISON RESULTS")
    print("=" * 60)

    all_pass = True
    for name, (_, csv) in SCRIPTS.items():
        path = os.path.join(RESULTS_DIR, csv)
        if not os.path.exists(path):
            print(f"  {name:20s}  MISSING (after)")
            all_pass = False
            continue

        after_hash = file_hash(path)
        before_hash = before.get(csv)

        if before_hash is None:
            print(f"  {name:20s}  NEW FILE (no before)")
        elif before_hash == after_hash:
            print(f"  {name:20s}  IDENTICAL  (hash: {before_hash[:12]})")
        else:
            print(f"  {name:20s}  CHANGED!")
            print(f"    before: {before_hash}")
            print(f"    after:  {after_hash}")
            all_pass = False

    print("=" * 60)
    if all_pass:
        print("RESULT: ALL OUTPUTS IDENTICAL - ZERO REGRESSIONS")
    else:
        print("RESULT: DIFFERENCES DETECTED - INVESTIGATE")
    print("=" * 60)


if __name__ == "__main__":
    main()
