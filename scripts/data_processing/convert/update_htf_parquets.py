import pandas as pd
from pathlib import Path

import argparse
parser = argparse.ArgumentParser(description='Merge and back-adjust HTF TradingView CSVs')
parser.add_argument('--folder', type=str, default='data/TV_OHLC', help='Folder containing the CSVs')
args = parser.parse_args()
source_dir = Path(args.folder)
output_dir = Path("data")

ticker_map = {
    "CME_MINI_ES1!": "ES1",
    "CME_MINI_NQ1!": "NQ1",
    "CME_MINI_RTY1!": "RTY1",
    "CBOT_MINI_YM1!": "YM1",
    "COMEX_GC1!": "GC1",
    "NYMEX_CL1!": "CL1",
}

print("Scanning for HTF CSVs to merge and back-adjust...")

for csv_path in sorted(source_dir.glob("*.csv")):
    filename = csv_path.stem
    if ", " not in filename:
        continue
        
    tv_ticker = filename.split(", ")[0]
    interval_raw = filename.split(", ")[1].split("_")[0]
    
    ticker = ticker_map.get(tv_ticker)
    timeframe = interval_raw.lower()
    
    if not ticker or timeframe not in ["1d", "1w"]:
        continue
        
    print(f"\nProcessing {ticker} | {timeframe}...")
    
    # 1. Load New Data
    df_new = pd.read_csv(csv_path)
    df_new.columns = [c.lower() for c in df_new.columns]
    
    # Use the pure CSV UTC time as the index as the user requested
    df_new['datetime'] = pd.to_datetime(df_new['time'], unit='s', utc=True)
    df_new.set_index('datetime', inplace=True)
    
    # Create an artificial session_date just for overlapping math
    # +4 hours safely pushes 22:00 UTC into the next calendar day (the correct Trading Session)
    df_new['session_date'] = (df_new.index + pd.Timedelta(hours=4)).floor('d')
    df_new.drop(columns=['time'], inplace=True, errors='ignore')

    # 2. Load Old Data
    parquet_path = output_dir / f"{ticker}_{timeframe}.parquet"
    if not parquet_path.exists():
        print(f"  Parquet {parquet_path.name} not found! Saving isolated CSV as Parquet.")
        df_new.drop(columns=['session_date']).to_parquet(parquet_path)
        continue
        
    df_old = pd.read_parquet(parquet_path)
    # Give df_old the same artificial session_date mapping
    df_old['session_date'] = (df_old.index + pd.Timedelta(hours=4)).floor('d')
    
    # 3. Find Overlap & Retroadjust
    common_sessions = df_new['session_date'][df_new['session_date'].isin(df_old['session_date'])].unique()
    
    if len(common_sessions) > 0:
        first_session = common_sessions[0]
        
        # Get the rows matching the first overlapping session
        new_row = df_new[df_new['session_date'] == first_session].iloc[0]
        old_row = df_old[df_old['session_date'] == first_session].iloc[0]
        
        delta = new_row['close'] - old_row['close']
        print(f"  First Overlap Session: {first_session.date()}")
        print(f"  Old Close: {old_row['close']:.2f} | New Close: {new_row['close']:.2f} => Delta: {delta:.2f}")
        
        # Apply Delta backward to the old Parquet history
        # (This aligns the old continuous contract correctly with the newly downloaded rolling contract)
        mask_old = df_old['session_date'] < first_session
        
        if abs(delta) > 0.01:
            df_old.loc[mask_old, 'open'] += delta
            df_old.loc[mask_old, 'high'] += delta
            df_old.loc[mask_old, 'low'] += delta
            df_old.loc[mask_old, 'close'] += delta
            
        # Drop the overlapping/newer rows from df_old. 
        df_old_kept = df_old[mask_old].copy()
    else:
        print("  WARNING: No overlapping sessions found. Appending blindly.")
        df_old_kept = df_old.copy()

    # 4. Merge
    df_merged = pd.concat([df_old_kept, df_new])
    
    # Remove the artificial session_date so we strictly keep the user's raw UTC index
    df_merged = df_merged.drop(columns=['session_date'])
    
    # Final cleanup
    # We use stable sort_index() so they stay in sequential time order
    df_merged = df_merged[~df_merged.index.duplicated(keep="last")]
    df_merged = df_merged.sort_index()

    # Save
    df_merged.to_parquet(parquet_path)
    print(f"  Saved {parquet_path.name} ({len(df_merged):,} bars)")

print("\nDone! Parquets successfully aligned and updated.")
