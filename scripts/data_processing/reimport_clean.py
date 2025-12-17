import os
import shutil
from pathlib import Path
import subprocess
import glob

# Map Ticker to CSV Pattern
# We need to find the specific CSV file for each ticker
TICKERS = {
    "GC1": "GC Monday*",
    "CL1": "CL Monday*",
    "RTY1": "RTY Monday*",
    "YM1": "YM Monday*",
    "ES1": "ES Monday*",
    "NQ1": "NQ Monday*"
}

def find_csv(pattern):
    base_dir = Path("data/ninjatrader")
    files = list(base_dir.glob(pattern + ".csv"))
    if not files:
        return None
    # Return most recent if multiple (unlikely based on list_dir)
    return str(files[0])

def clean_reimport(ticker):
    print(f"\n=== CLEAN RE-IMPORT: {ticker} ===")
    
    # 1. Find CSV
    pattern = TICKERS.get(ticker)
    csv_file = find_csv(pattern)
    if not csv_file:
        print(f"❌ No CSV found for {ticker} (Pattern: {pattern})")
        return

    print(f"📄 Source CSV: {csv_file}")
    
    # 2. Delete Existing Parquet
    parquet_file = Path(f"data/{ticker}_1m.parquet")
    if parquet_file.exists():
        print(f"🗑️ Deleting corrupted file: {parquet_file}")
        try:
            os.remove(parquet_file)
        except Exception as e:
            print(f"Failed to delete: {e}")
            return
    else:
        print("⚠️ No existing file (Clean slate).")

    # 3. Run Import
    print(f"📥 Importing NinjaTrader Data...")
    cmd_import = ["python", "scripts/import_ninjatrader.py", csv_file, ticker, "1m"] 
    # Note: no --align because we want the CSV to be the master.
    # import_ninjatrader shifts to open check default? YES.
    subprocess.run(cmd_import, check=True)
    
    # 4. Run Regeneration (Upsample + Profiler + Web Chunks)
    print(f"🔄 Regenerating Derived Data (and fetching tail)...")
    cmd_regen = ["python", "scripts/regenerate_derived.py", ticker]
    subprocess.run(cmd_regen, check=True)
    
    print(f"✅ {ticker} Check Completed.")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="*", help="Specific tickers to re-import (default: all)")
    args = parser.parse_args()

    target_tickers = args.tickers if args.tickers else TICKERS.keys()

    for t in target_tickers:
        if t in TICKERS:
            clean_reimport(t)
        else:
            print(f"⚠️ Unknown ticker: {t}")

if __name__ == "__main__":
    main()
