import pandas as pd
import json
import sys
import os
from pathlib import Path

def inspect_parquet(path):
    print(f"--- Inspecting Parquet: {path.name} ---")
    try:
        df = pd.read_parquet(path)
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print("\nData Types:")
        print(df.dtypes)
        
        # Check for Datetime index or column
        date_col = None
        if isinstance(df.index, pd.DatetimeIndex):
            print(f"\nIndex: DatetimeIndex ({df.index.min()} to {df.index.max()})")
        elif 'date' in df.columns:
            print(f"\nDate Range: {df['date'].min()} to {df['date'].max()}")
        elif 'time' in df.columns:
             print(f"\nTime Range: {df['time'].min()} to {df['time'].max()}")
             
        print("\nMissing Values:")
        print(df.isnull().sum()[df.isnull().sum() > 0])
        
        print("\nSample (Head):")
        print(df.head(3))
        
    except Exception as e:
        print(f"Error reading parquet: {e}")

def inspect_json(path):
    print(f"--- Inspecting JSON: {path.name} ---")
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            
        if isinstance(data, list):
            print(f"Type: List of {len(data)} items")
            if len(data) > 0:
                print(f"First Item Keys: {list(data[0].keys())}")
                print(f"First Item Sample: {data[0]}")
        elif isinstance(data, dict):
            print(f"Type: Dictionary with {len(data.keys())} keys")
            print(f"Keys: {list(data.keys())[:20]} {'...' if len(data) > 20 else ''}")
            # Check depth/structure of first value
            first_key = list(data.keys())[0]
            print(f"Sample Value ({first_key}): {str(data[first_key])[:100]}...")
        else:
            print(f"Type: {type(data)}")
            
    except Exception as e:
        print(f"Error reading json: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python inspect_dataset.py <path_to_file_or_directory>")
        return

    target = Path(sys.argv[1])
    
    if not target.exists():
        print(f"Error: Path {target} does not exist.")
        return

    if target.is_dir():
        print(f"Listing directory: {target}")
        for p in target.glob("*"):
            if p.suffix == '.parquet':
                print(f"[PARQUET] {p.name} ({p.stat().st_size / 1024 / 1024:.2f} MB)")
            elif p.suffix == '.json':
                print(f"[JSON]    {p.name} ({p.stat().st_size / 1024 / 1024:.2f} MB)")
    else:
        if target.suffix == '.parquet':
            inspect_parquet(target)
        elif target.suffix == '.json':
            inspect_json(target)
        else:
            print("Unsupported file type. Use .parquet or .json")

if __name__ == "__main__":
    main()
