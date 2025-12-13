import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import shutil

# Load the new ES1 daily CSV
csv_path = Path("data/CME_MINI_ES1!, 1D_291eb.csv")
df = pd.read_csv(csv_path)

print(f"Loaded {len(df)} rows from {csv_path.name}")
print(f"Columns: {list(df.columns)}")
print(f"\nFirst 3 rows:")
print(df.head(3))
print(f"\nLast 3 rows:")
print(df.tail(3))

# Check for duplicates
df['date'] = pd.to_datetime(df['time'], unit='s').dt.date
date_counts = df.groupby('date').size()
dups = date_counts[date_counts > 1]
print(f"\nDuplicate dates: {len(dups)}")

if len(dups) == 0:
    print("\n✓ Clean data - no duplicate dates!")
    
    # Normalize column names
    df.columns = [c.lower() for c in df.columns]
    df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
    
    # Save as parquet (backup old one first)
    parquet_path = Path("data/ES1_1D.parquet")
    if parquet_path.exists():
        backup_path = Path("data/ES1_1D.parquet.bak")
        shutil.copy(parquet_path, backup_path)
        print(f"\nBacked up old parquet to {backup_path}")
    
    # Convert time to datetime for parquet
    df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('America/New_York')
    df = df.set_index('datetime')
    df = df[['open', 'high', 'low', 'close', 'volume']]
    df.to_parquet(parquet_path)
    print(f"Saved new parquet: {parquet_path} ({len(df)} bars)")
    
    # Also create JSON chunks directly
    CHUNK_SIZE = 20000
    output_dir = Path("web/public/data/ES1_1D")
    
    # Reload for JSON format
    df_json = pd.read_csv(csv_path)
    df_json.columns = [c.lower() for c in df_json.columns]
    df_json = df_json[['time', 'open', 'high', 'low', 'close']]
    df_json.sort_values('time', inplace=True)
    
    # Clear and create output dir
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    
    # Write chunk
    all_data = df_json.to_dict(orient='records')
    total_bars = len(all_data)
    
    chunk_path = output_dir / "chunk_0.json"
    with open(chunk_path, 'w') as f:
        json.dump(all_data, f)
    
    # Write meta
    meta = {
        "ticker": "ES1",
        "timeframe": "1D",
        "totalBars": total_bars,
        "chunkSize": CHUNK_SIZE,
        "numChunks": 1,
        "startTime": all_data[0]['time'],
        "endTime": all_data[-1]['time'],
    }
    with open(output_dir / "meta.json", 'w') as f:
        json.dump(meta, f, indent=2)
    
    print(f"Created JSON chunks: {output_dir} ({total_bars} bars)")
    
    # Verify
    print("\n=== Verification ===")
    data = json.load(open(output_dir / "chunk_0.json"))
    from collections import Counter
    import pytz
    
    nyc = pytz.timezone('America/New_York')
    hours = [datetime.fromtimestamp(bar['time'], tz=pytz.UTC).astimezone(nyc).hour for bar in data]
    print(f"Hour distribution: {dict(Counter(hours))}")
    
    dates = [datetime.fromtimestamp(bar['time'], tz=pytz.UTC).astimezone(nyc).strftime('%Y-%m-%d') for bar in data]
    date_counts = Counter(dates)
    multi_dates = {d: c for d, c in date_counts.items() if c > 1}
    print(f"Dates with multiple bars: {len(multi_dates)}")
    
    print("\nLast 5 bars:")
    for bar in data[-5:]:
        dt = datetime.fromtimestamp(bar['time'], tz=pytz.UTC).astimezone(nyc)
        print(f"  {dt.strftime('%Y-%m-%d %H:%M')} - O={bar['open']} C={bar['close']}")
