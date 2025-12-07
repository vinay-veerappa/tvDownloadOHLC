"""
Convert parquet files to JSON format for faster loading.
This eliminates the need for Python subprocess during chart data loading.
"""
import pandas as pd
import json
from pathlib import Path
import os

def convert_parquet_to_json(parquet_path, json_path):
    """Convert a single parquet file to JSON format."""
    print(f"Converting {parquet_path.name}...")
    
    df = pd.read_parquet(parquet_path)
    
    # Reset index to move datetime from index to column
    df.reset_index(inplace=True)
    
    # Standardize column names
    df.columns = [c.lower() for c in df.columns]
    
    # Map time column names
    if 'datetime' in df.columns:
        df.rename(columns={'datetime': 'time'}, inplace=True)
    elif 'date' in df.columns:
        df.rename(columns={'date': 'time'}, inplace=True)
    
    # Convert time to Unix timestamp (seconds)
    if pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = (df['time'].astype('int64') // 10**9).astype(int)
    
    # Sort by time
    df.sort_values('time', inplace=True)
    
    # Select only OHLC columns (no volume to reduce size)
    df = df[['time', 'open', 'high', 'low', 'close']]
    
    # Convert to list of records
    data = df.to_dict(orient='records')
    
    # Save as JSON
    with open(json_path, 'w') as f:
        json.dump(data, f)
    
    # Get file sizes
    parquet_size = os.path.getsize(parquet_path) / (1024 * 1024)
    json_size = os.path.getsize(json_path) / (1024 * 1024)
    
    print(f"  {len(data):,} bars")
    print(f"  Parquet: {parquet_size:.1f} MB → JSON: {json_size:.1f} MB")
    
    return len(data)

def main():
    data_dir = Path("data")
    json_dir = Path("web/public/data")
    
    # Create output directory
    json_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all parquet files
    parquet_files = list(data_dir.glob("*.parquet"))
    
    print(f"Found {len(parquet_files)} parquet files\n")
    
    total_bars = 0
    for parquet_path in sorted(parquet_files):
        # Create corresponding JSON filename
        json_name = parquet_path.stem + ".json"
        json_path = json_dir / json_name
        
        bars = convert_parquet_to_json(parquet_path, json_path)
        total_bars += bars
        print()
    
    print(f"\n=== Done! ===")
    print(f"Total bars converted: {total_bars:,}")
    print(f"JSON files saved to: {json_dir}")

if __name__ == "__main__":
    main()
