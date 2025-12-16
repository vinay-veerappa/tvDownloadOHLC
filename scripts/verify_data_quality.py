import pandas as pd
import numpy as np
import argparse
from pathlib import Path
import os
from datetime import timedelta

# Configuration
ANOMALY_STD_DEV = 4.0  # Flag candles > 4 sigma from recent ATR
MIN_WICK_SIZE = 2.0    # Min points to even consider as a "wick"
CHECK_TAIL_ROWS = 10000 # Check last N rows for anomalies

def load_data(parquet_path):
    print(f"Loading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    if 'time' in df.columns:
        # Standardize index
        df['datetime'] = pd.to_datetime(df['time'], unit='s')
    elif isinstance(df.index, pd.DatetimeIndex):
        df['datetime'] = df.index
    
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    return df

def scan_anomalies(df, ticker):
    print(f"\n--- Scanning {ticker} for Anomalies (Last {CHECK_TAIL_ROWS} bars) ---")
    
    recent = df.tail(CHECK_TAIL_ROWS).copy()
    
    # metrics
    recent['body'] = (recent['close'] - recent['open']).abs()
    recent['range'] = recent['high'] - recent['low']
    recent['upper_wick'] = recent['high'] - np.maximum(recent['open'], recent['close'])
    recent['lower_wick'] = np.minimum(recent['open'], recent['close']) - recent['low']
    
    # ATR-like volatility (Last 100 bars rolling)
    recent['vol_ma'] = recent['range'].rolling(100).mean()
    recent['vol_std'] = recent['range'].rolling(100).std()
    
    # Find Anomalies
    # Condition 1: Range > mean + N*std
    recent['is_volatile'] = recent['range'] > (recent['vol_ma'] + ANOMALY_STD_DEV * recent['vol_std'])
    
    # Condition 2: Wick > 3x Body (Pinbar/Doji with huge wicks)
    recent['is_wicky'] = (recent['upper_wick'] > 3 * recent['body']) | (recent['lower_wick'] > 3 * recent['body'])
    
    # Condition 3: Zero Volume (if volume exists)
    if 'volume' in recent.columns:
        recent['is_flat'] = (recent['volume'] == 0) & (recent['range'] > 0.05)
    else:
        recent['is_flat'] = False

    anomalies = recent[recent['is_volatile'] | (recent['is_wicky'] & (recent['range'] > MIN_WICK_SIZE))]
    
    if not anomalies.empty:
        print(f"Found {len(anomalies)} potential anomalies.")
        print("Top 10 Deviation Candidates:")
        # sort by deviation size
        anomalies['deviation'] = (anomalies['range'] - anomalies['vol_ma']) / anomalies['vol_std']
        
        top_10 = anomalies.sort_values('deviation', ascending=False).head(10)
        for ts, row in top_10.iterrows():
            type_lbl = []
            if row['is_wicky']: type_lbl.append("WICK")
            if row['is_volatile']: type_lbl.append("VOLATILE")
            
            print(f"  {ts}: Range={row['range']:.2f}, Body={row['body']:.2f}, VolMA={row['vol_ma']:.2f} [{', '.join(type_lbl)}]")
    else:
        print("No significant anomalies found in recent data.")

def verify_against_csv(parquet_path, csv_path, ticker):
    print(f"\n--- Verifying {ticker} against NinjaTrader CSV ---")
    
    # 1. Load Parquet
    df_pq = load_data(parquet_path)
    
    # 2. Load CSV (Using import logic for robust parsing)
    # Simplified CSV Load
    try:
        with open(csv_path, 'r') as f:
             if ';' in f.readline(): sep = ';'
             else: sep = ','
        
        df_csv = pd.read_csv(csv_path, sep=sep)
        df_csv.columns = [c.lower() for c in df_csv.columns]
        
        # Parse Dates (NinjaTrader often: 20241209 000000)
        # Or US Format: 12/9/2024
        # Reuse import logic or simple try/except
        
        if 'time' in df_csv.columns: # NT export sometimes has 'Time' col implies date is separate? 
             # NT standard: Date, Time, Open, High...
             # Let's assume standard NT format from earlier
             pass
        
        # Quick hack: We know headers are Open,High,Low,Close,Volume
        # If headers are missing, we might have issues.
        # Let's rely on common NT output
        rename_map = {'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'vol': 'volume', 'volume': 'volume'}
        df_csv.rename(columns=rename_map, inplace=True)
        
        # Build datetime
        # Assuming format from Peek: 20241209;000000
        # Check first row
        first_row = df_csv.iloc[0]
        # Detect if we need to parse date/time cols
        
        if 'date' in df_csv.columns:
             date_col = 'date'
        elif 'time' in df_csv.columns and len(str(first_row['time'])) > 8: # Time contains date?
             date_col = 'time'
        else:
             # Basic column indexing 0=Date, 1=Time
             col0 = df_csv.columns[0]
             col1 = df_csv.columns[1]
             df_csv['datetime_str'] = df_csv[col0].astype(str) + ' ' + df_csv[col1].astype(str).str.zfill(6)
             df_csv['datetime'] = pd.to_datetime(df_csv['datetime_str'], format='%Y%m%d %H%M%S') # Guess
             
        # Set Index
        if 'datetime' not in df_csv.columns:
             # Try fallback
             df_csv['datetime'] = pd.to_datetime(df_csv.iloc[:,0].astype(str) + ' ' + df_csv.iloc[:,1].astype(str).str.zfill(6))
             
        df_csv.set_index('datetime', inplace=True)
        
        # Timezone Shift (US/Central -> NY)
        # NT Export 'Time' is usually Exchange Time (Central)
        # However, our peek showed '15:34:00'.
        # Let's assume input text is naive.
        
        # 3. Standardize Timezones for Comparison
        # Parquet (df_pq) is already in NY time (Naive, implied) or Aware
        if df_pq.index.tz is None:
             df_pq.index = df_pq.index.tz_localize('America/New_York')
        else:
             df_pq.index = df_pq.index.tz_convert('America/New_York')

        # CSV (df_csv)
        # We need to recreate the index carefully
        if df_csv.index.tz is None:
             # Assume Central if from NT
             df_csv.index = df_csv.index.tz_localize('US/Central').tz_convert('America/New_York')
        else:
             df_csv.index = df_csv.index.tz_convert('America/New_York')
        
        # Timestamp Shift (-1m) for Close->Open convention?
        # Only if we suspect NT is close time. Usually yes.
        # Let's try matching WITHOUT shift first, or check correlation?
        # Actually, let's keep the shift as default since we use it in import.
        # But wait, if we shift, we might misalign if import logic changed.
        # Let's stick to the script logic: import shifts by default. So verification should too.
        df_csv.index = df_csv.index - timedelta(minutes=1)
        
        # Truncate seconds if needed (sometimes parquet has 00, csv has 00)
        
        # Debug: Print ranges after TZ fix
        print(f"   Parquet Range (NY): {df_pq.index[0]} - {df_pq.index[-1]}")
        print(f"   CSV Range (NY):     {df_csv.index[0]} - {df_csv.index[-1]}")

        # Intersect
        # Round to nearest minute to handle float seconds issues
        df_pq.index = df_pq.index.round('1min')
        df_csv.index = df_csv.index.round('1min')
        
        common_idx = df_pq.index.intersection(df_csv.index)
        
        if len(common_idx) == 0:
            print("❌ No overlap found between Parquet and CSV.")
            print(f"   Parquet Range: {df_pq.index[0]} - {df_pq.index[-1]}")
            print(f"   CSV Range:     {df_csv.index[0]} - {df_csv.index[-1]}")
            return
            
        print(f"Comparing {len(common_idx)} overlapping bars...")
        
        aligned_pq = df_pq.loc[common_idx]
        aligned_csv = df_csv.loc[common_idx]
        
        # Check High/Low differences
        hl_diff = (aligned_pq['high'] - aligned_pq['low']) - (aligned_csv['high'] - aligned_csv['low'])
        
        # Filter significant discrepancies (> 0.5 points)
        bad_bars = hl_diff[hl_diff.abs() > 0.5]
        
        if not bad_bars.empty:
            print(f"⚠️ Found {len(bad_bars)} bars with Range Mismatch (> 0.5pts):")
            print(bad_bars.sort_values(ascending=False).head(5))
        else:
            print("✅ High/Low Ranges match perfectly (within 0.5pts).")
            
        # Check Close Price
        close_diff = aligned_pq['close'] - aligned_csv['close']
        if close_diff.abs().max() > 0.5:
             print(f"⚠️ Price Offset Detected! Max Diff: {close_diff.abs().max()}")
        else:
             print("✅ Prices are aligned.")

    except Exception as e:
        print(f"Comparision failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="e.g. GC1")
    parser.add_argument("--csv", help="Optional path to NT CSV for verification")
    args = parser.parse_args()
    
    pq_path = Path(f"data/{args.ticker}_1m.parquet")
    if not pq_path.exists():
        print(f"Parquet not found: {pq_path}")
        return

    df = load_data(pq_path)
    
    # 1. Anomaly Scan (Recent Data - Yahoo Check)
    scan_anomalies(df, args.ticker)
    
    # 2. CSV Verification (Historical Check)
    if args.csv:
        verify_against_csv(pq_path, args.csv, args.ticker)

if __name__ == "__main__":
    main()
