import pandas as pd
import numpy as np
import os
import json
import glob
from pathlib import Path

# Configuration
DATA_DIR = Path("data")
PUBLIC_DATA_DIR = Path("web/public/data")
CHUNK_SIZE = 20000

TARGET_TICKERS = ["SPY", "QQQ", "SPX"]

def save_chunked(df, ticker, timeframe):
    # Create directory
    out_dir = PUBLIC_DATA_DIR / f"{ticker}_{timeframe}"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Sort
    df = df.sort_index()
    
    # Metadata
    total_bars = len(df)
    if total_bars == 0: return

    start_ts = int(df.index[0].timestamp())
    end_ts = int(df.index[-1].timestamp())
    
    chunks_meta = []
    
    # Chunking
    num_chunks = (total_bars + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    for i in range(num_chunks):
        start_idx = i * CHUNK_SIZE
        end_idx = min((i + 1) * CHUNK_SIZE, total_bars)
        
        chunk_df = df.iloc[start_idx:end_idx].copy()
        
        # Format for lightweight-charts
        # time (seconds), open, high, low, close, volume?
        # df index is datetime
        
        chunk_data = []
        for time, row in chunk_df.iterrows():
            bar = {
                "time": int(time.timestamp()),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
            }
            if 'volume' in row:
                bar['volume'] = float(row['volume'])
            chunk_data.append(bar)
            
        # Save Chunk
        chunk_path = out_dir / f"chunk_{i}.json"
        with open(chunk_path, 'w') as f:
            json.dump(chunk_data, f)
            
        chunks_meta.append({
            "index": i,
            "startTime": chunk_data[0]['time'],
            "endTime": chunk_data[-1]['time'],
            "bars": len(chunk_data)
        })
        
    # Save Meta
    meta = {
        "ticker": ticker,
        "timeframe": timeframe,
        "totalBars": total_bars,
        "chunkSize": CHUNK_SIZE,
        "numChunks": num_chunks,
        "startTime": start_ts,
        "endTime": end_ts,
        "chunks": chunks_meta
    }
    
    with open(out_dir / "meta.json", 'w') as f:
        json.dump(meta, f, indent=2)
        
    print(f"  Saved {ticker} {timeframe}: {total_bars} bars → {num_chunks} chunks")

def main():
    print(f"Targeted Conversion for: {TARGET_TICKERS}")
    
    # Find Parquet files matching targets
    files = list(DATA_DIR.glob("*.parquet"))
    
    for f in files:
        # Check if file starts with target ticker
        # e.g. SPY_15m.parquet
        parts = f.stem.split('_')
        if len(parts) < 2: continue
        
        ticker = "_".join(parts[:-1])
        timeframe = parts[-1]
        
        if ticker in TARGET_TICKERS:
            print(f"Processing {f.name}...")
            try:
                df = pd.read_parquet(f)
                
                # Check index
                if not isinstance(df.index, pd.DatetimeIndex):
                    if 'datetime' in df.columns:
                        df = df.set_index('datetime')
                    elif 'time' in df.columns:
                         # assume unix or string
                         df['datetime'] = pd.to_datetime(df['time'], unit='s') if pd.api.types.is_numeric_dtype(df['time']) else pd.to_datetime(df['time'])
                         df = df.set_index('datetime')
                
                save_chunked(df, ticker, timeframe)
                
            except Exception as e:
                print(f"Error converting {f.name}: {e}")

if __name__ == "__main__":
    main()
