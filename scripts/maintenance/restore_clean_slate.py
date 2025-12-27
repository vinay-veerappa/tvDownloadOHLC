
import pandas as pd
from pathlib import Path
import shutil
from datetime import datetime

DATA_DIR = Path("data")
BACKUP_DIR = Path("data/backup")

# Tickers to restore
TICKERS = ["ES1", "NQ1", "YM1", "RTY1", "GC1", "VVIX", "QQQ"]
TIMEFRAMES = ["1m", "5m", "1h", "1d"] # Priority on high-res, others are derived usually but good to check

def is_naive(p_path):
    try:
        df = pd.read_parquet(p_path)
        return df.index.tz is None
    except:
        return False

def restore_ticker(ticker, timeframe):
    target_file = DATA_DIR / f"{ticker}_{timeframe}.parquet"
    pattern = f"{ticker}_{timeframe}.parquet.*.bak"
    
    # 1. Find all backups
    backups = list(BACKUP_DIR.glob(pattern))
    if not backups:
        print(f"[{ticker} {timeframe}] No backups found.")
        return

    # 2. Filter for Naive (UTC)
    naive_backups = []
    print(f"[{ticker} {timeframe}] Checking {len(backups)} backups for clean (Naive) state...")
    
    # Sort closest to present first to find the most recent VALID backup efficiently
    backups_sorted = sorted(backups, key=lambda f: f.stat().st_mtime, reverse=True)
    
    for bk in backups_sorted:
        # Optimization: skip if modification date is very recent (post-contamination date of Dec 16)
        # But safer to check metadata.
        # Actually, let's just check metadata of the first few to find a hit.
        if is_naive(bk):
            naive_backups.append(bk)
            break # Found the most recent Naive one!
    
    if not naive_backups:
        print(f"[{ticker} {timeframe}] ❌ No clean Naive/UTC backup found!")
        return

    best_backup = naive_backups[0]
    
    # 3. Restore
    print(f"[{ticker} {timeframe}] ✅ Found clean backup: {best_backup.name}")
    print(f"    Timestamp: {datetime.fromtimestamp(best_backup.stat().st_mtime)}")
    
    try:
        # Backup current damaged file just in case (to a 'contaminated' folder? or just leave in backup dir with new timestamp)
        if target_file.exists():
            damaged_backup = BACKUP_DIR / f"DAMAGED_{target_file.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            shutil.copy(target_file, damaged_backup)
            print(f"    Archived current damaged file to {damaged_backup.name}")
            
        shutil.copy(best_backup, target_file)
        print(f"    ✅ Restored successfully.")
        
    except Exception as e:
        print(f"    ❌ Restore failed: {e}")

def main():
    print("=== CLEAN SLATE RESTORATION ===")
    print("Restoring all tickers to last known Naive (UTC) state.")
    
    for t in TICKERS:
        # Only focusing on 1m and 1d as primary sources. 
        # Intermediate (5m, 1h) can be regenerated from 1m.
        restore_ticker(t, "1m")
        restore_ticker(t, "1d") 
        # Also check Weekly if relevant
        restore_ticker(t, "1W")

if __name__ == "__main__":
    main()
