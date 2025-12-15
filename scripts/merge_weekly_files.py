import os
import glob
import pandas as pd
import data_utils
from pathlib import Path

def merge_weekly_files():
    data_dir = Path(data_utils.DATA_DIR)
    
    # Find all 1W files
    old_files = list(data_dir.glob("*_1W.parquet"))
    
    print(f"Found {len(old_files)} legacy '_1W' files.")
    
    for old_path in old_files:
        ticker = old_path.name.split('_')[0]
        new_filename = f"{ticker}_1wk.parquet"
        new_path = data_dir / new_filename
        
        print(f"\nProcessing {ticker}...")
        
        # Load Old (1W)
        try:
            df_old = pd.read_parquet(old_path)
            print(f"  Legacy 1W: {len(df_old)} rows ({old_path.name})")
        except Exception as e:
            print(f"  Error reading {old_path.name}: {e}")
            continue

        # Load New (1wk) if exists
        df_new = pd.DataFrame()
        if new_path.exists():
            try:
                df_new = pd.read_parquet(new_path)
                print(f"  New 1wk:   {len(df_new)} rows ({new_path.name})")
            except Exception as e:
                print(f"  Error reading {new_path.name}: {e}")

        # Basic cleanup: Ensure index is datetime
        if not isinstance(df_old.index, pd.DatetimeIndex):
             if 'datetime' in df_old.columns: df_old.set_index('datetime', inplace=True)
             elif 'date' in df_old.columns: df_old.set_index(pd.to_datetime(df_old['date']), inplace=True)
             
        if not df_new.empty and not isinstance(df_new.index, pd.DatetimeIndex):
             # 1wk might be timezone aware, check script logic. Usually it is.
             # check_data_status uses 'datetime' column search, but here we expect index.
             pass

        # Timezone Alignment (Prioritize New/Yahoo TZ which is likely America/New_York via script or UTC)
        # Actually our update script makes it consistent.
        # Let's align Old to New if New exists.
        target_tz = None
        if not df_new.empty and df_new.index.tz is not None:
            target_tz = df_new.index.tz
        elif not df_old.empty and df_old.index.tz is not None:
             target_tz = df_old.index.tz
        
        # Convert both to target_tz if detected
        if target_tz:
             if df_old.index.tz is None: df_old.index = df_old.index.tz_localize("UTC").tz_convert(target_tz)
             else: df_old.index = df_old.index.tz_convert(target_tz)
             
             if not df_new.empty:
                 if df_new.index.tz is None: df_new.index = df_new.index.tz_localize("UTC").tz_convert(target_tz)
                 else: df_new.index = df_new.index.tz_convert(target_tz)

        # Merge
        if not df_new.empty:
            merged = pd.concat([df_old, df_new])
            # Deduplicate by Index
            merged = merged[~merged.index.duplicated(keep='last')]
            merged.sort_index(inplace=True)
            print(f"  Merged:    {len(merged)} rows")
        else:
            merged = df_old
            merged.sort_index(inplace=True)
            print(f"  Migrating 1W to 1wk (No existing 1wk found)")

        # Verify Integrity
        if len(merged) > 0:
            # Backup Old
            data_utils.create_backup(str(old_path))
            
            # Save to NEW path (1wk)
            data_utils.safe_save_parquet(merged, str(new_path))
            print(f"  ✅ Saved to {new_filename}")
            
            # Delete Old (1W)
            try:
                os.remove(old_path)
                print(f"  🗑️ Deleted legacy {old_path.name}")
            except Exception as e:
                print(f"  ⚠️ Could not delete {old_path.name}: {e}")

if __name__ == "__main__":
    merge_weekly_files()
