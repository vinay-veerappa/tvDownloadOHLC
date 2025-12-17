"""Check data coverage and gaps for 5m/15m timeframes"""
import pandas as pd
from pathlib import Path

data_dir = Path("data")
tickers = ["ES1", "NQ1", "CL1"]
tfs = ["1m", "5m", "15m", "1h", "4h"]

print("=" * 70)
print("DATA COVERAGE ANALYSIS - Do you need to download 5m/15m?")
print("=" * 70)
print()

for ticker in tickers:
    print(f"## {ticker}")
    print()
    
    data = {}
    for tf in tfs:
        f = data_dir / f"{ticker}_{tf}.parquet"
        if f.exists():
            df = pd.read_parquet(f)
            data[tf] = {
                "start": df.index.min(),
                "end": df.index.max(),
                "bars": len(df),
                "vol": (df["volume"] > 0).any() if "volume" in df.columns else False
            }
    
    # Print current coverage
    print("  Current data:")
    for tf in tfs:
        if tf in data:
            d = data[tf]
            vol = "✅" if d["vol"] else "❌"
            print(f"    {tf:4s}: {d['start'].date()} to {d['end'].date()} ({d['bars']:>8,} bars) vol={vol}")
        else:
            print(f"    {tf:4s}: MISSING")
    
    print()
    
    # Analyze gaps
    if "1m" in data and "5m" in data:
        m1_end = data["1m"]["end"]
        m5_start = data["5m"]["start"]
        
        if m1_end >= m5_start:
            print(f"  ✅ 5m: Fully covered! 1m ends {m1_end.date()} >= 5m starts {m5_start.date()}")
        else:
            print(f"  ⚠️ 5m: GAP from {m1_end.date()} to {m5_start.date()}")
            print(f"         If you resample 1m→5m, you'll only have data from {data['1m']['start'].date()}")
    
    if "1m" in data and "15m" in data:
        m1_end = data["1m"]["end"]
        m15_start = data["15m"]["start"]
        
        if m1_end >= m15_start:
            print(f"  ✅ 15m: Fully covered! 1m ends {m1_end.date()} >= 15m starts {m15_start.date()}")
        else:
            print(f"  ⚠️ 15m: GAP from {m1_end.date()} to {m15_start.date()}")
            print(f"          If you resample 1m→15m, you'll only have data from {data['1m']['start'].date()}")
    
    # Compare 5m end date with 1h start to see if there's value in 5m download
    if "5m" in data and "1h" in data:
        m5_end = data["5m"]["end"]
        h1_start = data["1h"]["start"]
        
        if m5_end >= h1_start:
            print(f"  ✅ 5m provides good bridge to 1h (5m ends {m5_end.date()}, 1h starts {h1_start.date()})")
        else:
            print(f"  📥 Consider downloading 5m: current 5m ends {m5_end.date()}, 1h starts {h1_start.date()}")
    
    print()

print("=" * 70)
print("RECOMMENDATION")
print("=" * 70)
print()
print("If 5m/15m already extend back far enough, you DON'T need to download.")
print("If there are gaps and you want continuous data, DOWNLOAD from TradingView.")
print()
print("TradingView data limits:")
print("  - 1m:  ~1 month history")
print("  - 5m:  ~1 year history") 
print("  - 15m: ~1 year history")
print("  - 1h+: Full history available")
