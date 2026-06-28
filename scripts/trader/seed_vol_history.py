import os
import sys

# Ensure repository root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.append(root_dir)

import io
# Force standard output and error to use utf-8 on Windows to prevent emoji encoding crashes
if sys.platform == 'win32' and not hasattr(sys.stdout, '_wrapped_utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.stdout._wrapped_utf8 = True
if sys.platform == 'win32' and not hasattr(sys.stderr, '_wrapped_utf8'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)
    sys.stderr._wrapped_utf8 = True

from scripts.trader.macro_storage import process_volatility_storage
from scripts.trader.update_friction_matrix import update_centralized_friction_matrix

tickers = ["SPX", "SPY", "QQQ"]

print("⚡ Starting Post-Deployment Verification Seed script...")

for ticker in tickers:
    print(f"\n🔄 Seeding historical features for {ticker}...")
    
    # 1. Backfill the Prisma DB MacroSnapshot table
    try:
        success = process_volatility_storage(ticker, backfill=True)
        if success:
            print(f"✅ DB Backfill complete for {ticker}")
        else:
            print(f"⚠️ DB Backfill returned False for {ticker}")
    except Exception as e:
        print(f"❌ DB Backfill failed for {ticker}: {e}")
        
    # 2. Build the asset-agnostic friction parquets under data/derived/
    try:
        success = update_centralized_friction_matrix(ticker)
        if success:
            print(f"✅ Parquet feature matrix update complete for {ticker}")
        else:
            print(f"⚠️ Parquet feature matrix returned False for {ticker}")
    except Exception as e:
        print(f"❌ Parquet feature matrix failed for {ticker}: {e}")

print("\n✨ Feature store backfill complete. Derived parquets compiled.")
