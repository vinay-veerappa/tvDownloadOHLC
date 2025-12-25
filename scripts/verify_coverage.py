
import pandas as pd
from pathlib import Path

def check(ticker):
    p = Path(f"data/{ticker}_1m.parquet")
    if not p.exists():
        print(f"{ticker}: File not found.")
        return
        
    df = pd.read_parquet(p)
    if df.empty:
        print(f"{ticker}: Empty.")
        return

    start = df.index.min()
    end = df.index.max()
    count = len(df)
    
    print(f"[{ticker}]")
    print(f"  Rows:  {count:,}")
    print(f"  Start: {start}")
    print(f"  End:   {end}")
    
    # Check max gap
    diffs = df.index.to_series().diff().dt.total_seconds() / 3600.0
    max_gap = diffs.max()
    
    print(f"  Max Gap: {max_gap:.2f} hours")
    
    if max_gap > 96:
        print("  ❌ WARNING: Found gap > 4 days!")
        # Show top 5 gaps
        gaps = diffs[diffs > 96].sort_values(ascending=False).head(5)
        for d, v in gaps.items():
            print(f"     {d}: {v:.1f} hours")
    else:
        print("  ✅ Continuous (No gap > 4 days).")

check("ES1")
check("NQ1")
