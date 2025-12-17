"""
Analyze data and recommend resampling vs downloading
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

data_dir = Path("data")

# Get all parquet files and analyze
files = {}
for f in sorted(data_dir.glob("*.parquet")):
    parts = f.stem.split("_")
    ticker = parts[0]
    tf = parts[1] if len(parts) > 1 else "Unknown"
    
    df = pd.read_parquet(f)
    start = df.index.min()
    end = df.index.max()
    has_vol = "volume" in df.columns and (df["volume"] > 0).any()
    
    if ticker not in files:
        files[ticker] = {}
    files[ticker][tf] = {
        "start": start,
        "end": end,
        "bars": len(df),
        "volume": has_vol
    }

# Analyze resampling potential
tf_hierarchy = ["1m", "5m", "15m", "1h", "4h", "1D", "1W"]
tf_names = {"1m": "1 minute", "5m": "5 minute", "15m": "15 minute", 
            "1h": "1 hour", "4h": "4 hour", "1D": "Daily", "1W": "Weekly"}

print("=" * 60)
print("DATA RESAMPLING ANALYSIS")
print("=" * 60)
print()

resample_actions = []

for ticker, tfs in sorted(files.items()):
    print(f"## {ticker}")
    
    # Show what we have
    for tf in tf_hierarchy:
        if tf in tfs:
            info = tfs[tf]
            vol = "✅" if info["volume"] else "❌"
            print(f"  {tf}: {info['start'].date()} to {info['end'].date()} ({info['bars']:,} bars, vol={vol})")
    
    # Determine what can be resampled
    if "1m" in tfs:
        source_tf = "1m"
        can_derive = ["5m", "15m", "1h", "4h", "1D", "1W"]
    elif "5m" in tfs:
        source_tf = "5m"
        can_derive = ["15m", "1h", "4h", "1D", "1W"]
    elif "15m" in tfs:
        source_tf = "15m"
        can_derive = ["1h", "4h", "1D", "1W"]
    elif "1h" in tfs:
        source_tf = "1h"
        can_derive = ["4h", "1D", "1W"]
    elif "4h" in tfs:
        source_tf = "4h"
        can_derive = ["1D", "1W"]
    elif "1D" in tfs:
        source_tf = "1D"
        can_derive = ["1W"]
    else:
        source_tf = None
        can_derive = []
    
    if source_tf:
        source = tfs[source_tf]
        print(f"  -> Can resample from {source_tf} to: {', '.join(can_derive)}")
        
        for target_tf in can_derive:
            existing = tfs.get(target_tf)
            should_resample = False
            reason = ""
            
            if not existing:
                should_resample = True
                reason = "missing"
            elif not existing["volume"] and source["volume"]:
                should_resample = True
                reason = "add volume"
            elif source["end"] > existing["end"]:
                should_resample = True
                reason = "update to newer"
            
            if should_resample:
                resample_actions.append((ticker, source_tf, target_tf, reason))
    
    print()

print("=" * 60)
print("RECOMMENDED ACTIONS")
print("=" * 60)
print()

if resample_actions:
    print("### Resample (no download needed):")
    for ticker, src, tgt, reason in resample_actions:
        print(f"  {ticker}: {src} -> {tgt} ({reason})")
else:
    print("No resampling needed - all data is up to date!")

print()
print("### Download Recommendations:")
print()
print("For BEST data quality, download these directly from TradingView:")
print("  - 1m data: Only ~1 month history available (TradingView limit)")
print("  - 5m/15m data: ~1 year history available")
print("  - 1h data: Several years history available")
print("  - 4h/1D/1W: Full history available")
print()
print("Resampling is SUFFICIENT when:")
print("  - You only need recent data (within source timeframe range)")
print("  - Volume accuracy is not critical")
print()
print("Download is RECOMMENDED when:")
print("  - You need longer history than your source timeframe provides")
print("  - You need tick-accurate OHLC (resampling may differ slightly)")
