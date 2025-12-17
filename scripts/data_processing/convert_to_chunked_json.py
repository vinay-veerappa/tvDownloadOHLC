"""
Convert parquet files to chunked JSON files for efficient lazy loading.
Creates multiple JSON files per ticker/timeframe, each containing a fixed number of bars.
This allows loading data in chunks without reading the entire file.

Structure:
  web/public/data/{ticker}_{timeframe}/
    meta.json     - Contains total bars, chunk size, number of chunks
    chunk_0.json  - Most recent data
    chunk_1.json  - Older data
    ...
"""
import pandas as pd
import json
from pathlib import Path
import shutil
import os

CHUNK_SIZE = 20000  # Bars per chunk file

def convert_parquet_to_chunked_json(parquet_path, output_dir):
    """Convert a parquet file to chunked JSON format."""
    name = parquet_path.stem  # e.g., "NQ1_1m"
    ticker_dir = output_dir / name
    
    print(f"Converting {parquet_path.name}...")
    
    # Load data
    try:
        df = pd.read_parquet(parquet_path)
    except Exception as e:
        print(f"FAILED to read {parquet_path}: {e}")
        return 0, 0
    
    # Normalize columns to lowercase
    df.columns = [c.lower() for c in df.columns]
    
    # Check if 'time' (or variant) is already a column
    has_time_col = False
    for col in ['time', 'date', 'datetime']:
        if col in df.columns:
            has_time_col = True
            break
            
    if has_time_col:
        # If time column exists, we can drop the index to avoid conflicts
        df.reset_index(drop=True, inplace=True)
    else:
        # If no time column, the index likely holds the time
        df.reset_index(inplace=True)
        # Re-normalize columns because reset_index might have introduced a capitalized column (e.g. 'Datetime')
        df.columns = [c.lower() for c in df.columns]
    
    if 'datetime' in df.columns:
        df.rename(columns={'datetime': 'time'}, inplace=True)
    elif 'date' in df.columns:
        df.rename(columns={'date': 'time'}, inplace=True)
    elif 'index' in df.columns:
        df.rename(columns={'index': 'time'}, inplace=True)
    
    
    if pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = (df['time'].astype('int64') // 10**9).astype(int)
    
    df.sort_values('time', inplace=True)
    
    # Extract timeframe from filename for deduplication logic
    timeframe = parquet_path.stem.split('_')[-1]  # e.g., "1D" from "ES1_1D"
    
    # For daily (1D) timeframes, deduplicate to keep only one bar per calendar day
    # This fixes the double candle issue where both overnight and regular session bars exist
    if timeframe in ['1D', '1W']:
        # Convert time to datetime with NYSE timezone for proper trading day grouping
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert('America/New_York')
        
        if timeframe == '1D':
            df['period'] = df['datetime'].dt.date

        else:  # 1W - use year-week tuple for grouping
            df['period'] = df['datetime'].dt.isocalendar().week.astype(str) + '-' + df['datetime'].dt.isocalendar().year.astype(str)

        
        # Keep the bar with highest volume per period, or last bar if no volume
        if 'volume' in df.columns and df['volume'].notna().any():
            # Fill NaN volumes with 0 so idxmax() doesn't fail
            df['volume_filled'] = df['volume'].fillna(0)
            # Group by period and keep the row with max volume
            idx = df.groupby('period')['volume_filled'].idxmax()
            df = df.loc[idx].drop(columns=['volume_filled'])

        else:
            # No volume data - keep the last bar for each period
            df = df.groupby('period').last().reset_index()
        
        # Sort again after deduplication
        df.sort_values('time', inplace=True)
        df = df.drop(columns=['datetime', 'period'])
        
        print(f"  Deduplicated {timeframe}: {len(df)} bars (1 per {'day' if timeframe == '1D' else 'week'})")
    
    df = df[['time', 'open', 'high', 'low', 'close']]
    
    # Sanitize: Drop NaNs in critical columns
    before_drop = len(df)
    df.dropna(subset=['time', 'close'], inplace=True)
    after_time_drop = len(df)
    if before_drop != after_time_drop:
        print(f"  WARNING: Dropped {before_drop - after_time_drop} rows due to NaN time/close")

    # Ensure time is int (Unix timestamp)
    if not pd.api.types.is_integer_dtype(df['time']):
         # Try converting to int, coercing errors
         df['time'] = pd.to_numeric(df['time'], errors='coerce')
         df.dropna(subset=['time'], inplace=True)
         after_coerce = len(df)
         if after_time_drop != after_coerce:
            print(f"  WARNING: Dropped {after_time_drop - after_coerce} rows due to invalid Time format")
         df['time'] = df['time'].astype(int)
         
    # Final sort
    df.sort_values('time', inplace=True)

    
    total_bars = len(df)
    num_chunks = (total_bars + CHUNK_SIZE - 1) // CHUNK_SIZE  # Ceiling division
    
    # Create output directory
    if ticker_dir.exists():
        shutil.rmtree(ticker_dir)
    ticker_dir.mkdir(parents=True)
    
    # Write chunks (chunk 0 = most recent, chunk N = oldest)
    # Data is sorted oldest to newest, so we reverse for chunking
    all_data = df.to_dict(orient='records')
    
    # Track per-chunk time ranges for accurate lookup
    chunk_ranges = []
    
    for i in range(num_chunks):
        # Calculate slice from END (most recent first)
        end_idx = total_bars - (i * CHUNK_SIZE)
        start_idx = max(0, end_idx - CHUNK_SIZE)
        chunk_data = all_data[start_idx:end_idx]
        
        # Store chunk time range
        chunk_ranges.append({
            "index": i,
            "startTime": chunk_data[0]['time'],
            "endTime": chunk_data[-1]['time'],
            "bars": len(chunk_data)
        })
        
        chunk_path = ticker_dir / f"chunk_{i}.json"
        with open(chunk_path, 'w') as f:
            json.dump(chunk_data, f)
    
    # Write metadata with per-chunk time ranges
    meta = {
        "ticker": name.split('_')[0],
        "timeframe": name.split('_')[1],
        "totalBars": total_bars,
        "chunkSize": CHUNK_SIZE,
        "numChunks": num_chunks,
        "startTime": all_data[0]['time'],
        "endTime": all_data[-1]['time'],
        "chunks": chunk_ranges  # Per-chunk time ranges for accurate lookup
    }
    with open(ticker_dir / "meta.json", 'w') as f:
        json.dump(meta, f, indent=2)
    
    # Calculate total size
    total_size = sum(f.stat().st_size for f in ticker_dir.glob("*.json"))
    
    print(f"  {total_bars:,} bars → {num_chunks} chunks ({total_size / (1024*1024):.1f} MB)")
    
    return total_bars, num_chunks

def main():
    data_dir = Path("data")
    output_dir = Path("web/public/data")
    
    # Clear old single-file JSONs
    for f in output_dir.glob("*.json"):
        f.unlink()
    
    import sys
    
    # Check for specific tickers
    specific_tickers = sys.argv[1:]
    
    # Find all parquet files
    all_parquet_files = list(data_dir.glob("*.parquet"))
    
    if specific_tickers:
        parquet_files = []
        for pat in specific_tickers:
            # Handle "YM1" -> match "YM1_*.parquet"
            # We need to be careful not to match "YM1" vs "YM1_1m" overlapping.
            # glob search likely safer.
            # Actually just filter the list.
            for p in all_parquet_files:
                if p.name.startswith(pat + "_"):
                    parquet_files.append(p)
        print(f"Filtering for {specific_tickers} -> Found {len(parquet_files)} files")
    else:
        parquet_files = all_parquet_files
    
    print(f"Found {len(parquet_files)} parquet files")
    print(f"Chunk size: {CHUNK_SIZE:,} bars per chunk\n")
    
    total_bars = 0
    total_chunks = 0
    for parquet_path in sorted(parquet_files):
        bars, chunks = convert_parquet_to_chunked_json(parquet_path, output_dir)
        total_bars += bars
        total_chunks += chunks
    
    print(f"\n=== Done! ===")
    print(f"Total bars: {total_bars:,}")
    print(f"Total chunks: {total_chunks}")
    print(f"Output: {output_dir}")

if __name__ == "__main__":
    main()
