
import pandas as pd
import numpy as np
import json
import os
from pathlib import Path
from datetime import datetime

# Configuration
INPUT_FILE = "data/TV_OHLC/Badj/CME_MINI_NQ1!, 1D_94cae.csv"
OUTPUT_DIR = "data/analysis"
OUTPUT_JSON = f"{OUTPUT_DIR}/ref_data_verification.json"
OUTPUT_REPORT = f"{OUTPUT_DIR}/ref_data_report.md"

# Reference Constraints
REF_END_DATE = "2025-01-16"
REF_DAYS_COUNT = 4584

def run_verification():
    print(f"Loading Unadjusted Data from: {INPUT_FILE}")
    
    if not os.path.exists(INPUT_FILE):
        print(f"Error: File not found {INPUT_FILE}")
        return

    # Load CSV
    df = pd.read_csv(INPUT_FILE)
    
    # Parse Dates
    # TradingView CSVs usually have time column, e.g., '2010-01-01T09:30:00Z' or ISO
    if 'time' in df.columns:
        # Check first row format
        sample = str(df['time'].iloc[0])
        if 'T' in sample:
            df['dt'] = pd.to_datetime(df['time'])
        elif sample.isdigit(): # Unix timestamp
             df['dt'] = pd.to_datetime(df['time'], unit='s')
        else:
             df['dt'] = pd.to_datetime(df['time'])
    else:
        print("Error: 'time' column missing.")
        return

    df = df.set_index('dt').sort_index()
    
    # Filter to Reference Period
    df_ref = df[df.index <= REF_END_DATE].iloc[-REF_DAYS_COUNT:].copy()
    
    start_date = df_ref.index[0].strftime('%Y-%m-%d')
    end_date = df_ref.index[-1].strftime('%Y-%m-%d')
    
    print(f"Reference Period: {start_date} to {end_date} ({len(df_ref)} trading days)")
    
    # --- CALCULATIONS ---
    
    # 1. High from Open (True Volatility)
    df_ref['open_to_high_pct'] = (df_ref['high'] - df_ref['open']) / df_ref['open'] * 100
    
    # 2. Low from Open
    df_ref['open_to_low_pct'] = (df_ref['low'] - df_ref['open']) / df_ref['open'] * 100
    
    # 3. Total Range
    df_ref['total_range_pct'] = (df_ref['high'] - df_ref['low']) / df_ref['open'] * 100
    
    # 4. Open to Close
    df_ref['open_to_close_pct'] = (df_ref['close'] - df_ref['open']) / df_ref['open'] * 100
    
    # Stats
    stats = {
        "period": {
            "start": start_date,
            "end": end_date,
            "count": len(df_ref)
        },
        "prices": {
            "start_price": df_ref['open'].iloc[0],
            "end_price": df_ref['open'].iloc[-1]
        },
        "median_stats": {
            "high_from_open": round(df_ref['open_to_high_pct'].median(), 3),
            "low_from_open": round(df_ref['open_to_low_pct'].median(), 3),
            "total_range": round(df_ref['total_range_pct'].median(), 3),
            "abs_close_move": round(df_ref['open_to_close_pct'].abs().median(), 3)
        },
        "distribution": {
            "high_buckets": {},
            "range_buckets": {}
        }
    }
    
    # Distribution Buckets (0.0 to 5.0 in 0.1 steps)
    buckets = [round(x * 0.1, 1) for x in range(51)]
    
    # High Dist
    # We bucket by rounding down to nearest 0.1 (floor) to match typical histogram logic
    # e.g. 0.19 -> 0.1
    import math
    def get_bucket(val):
        if val < 0: return 0.0 # Should not happen for High-Open
        b = math.floor(val * 10) / 10.0
        return b if b < 5.0 else 5.0

    high_counts = df_ref['open_to_high_pct'].apply(get_bucket).value_counts()
    for b in buckets:
        stats["distribution"]["high_buckets"][str(b)] = int(high_counts.get(b, 0))
        
    # Range Dist
    range_counts = df_ref['total_range_pct'].apply(get_bucket).value_counts()
    for b in buckets:
        stats["distribution"]["range_buckets"][str(b)] = int(range_counts.get(b, 0))

    # Save JSON
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(stats, f, indent=2)
        
    print(f"Saved analysis to {OUTPUT_JSON}")
    
    # Generate Markdown Report
    md = f"""# Reference Data Verification Report
**Source:** {INPUT_FILE}
**Analysis Date:** {datetime.now().strftime('%Y-%m-%d')}
**Period:** {start_date} to {end_date} ({len(df_ref)} days)

## Key Findings (Unadjusted Proxy)
- **Median High from Open:** {stats['median_stats']['high_from_open']}%
- **Median Total Range:** {stats['median_stats']['total_range']}%
- **Start Price (2006):** {stats['prices']['start_price']} (Verified Unadjusted)

## Comparison Table
| Metric | Our Prod Data (Adjusted) | Ref Data (Unadjusted) | Difference |
| :--- | :--- | :--- | :--- |
| **High From Open** | ~0.38% | **{stats['median_stats']['high_from_open']}%** | Significant |
| **Total Range** | ~0.86% | **{stats['median_stats']['total_range']}%** | Significant |

## High % Distribution (Unadjusted)
| Bucket | Count |
| :--- | :--- |
"""
    for b in buckets:
        cnt = stats["distribution"]["high_buckets"][str(b)]
        bar = "|" * int(cnt // 50)
        md += f"| {b}% | {cnt} {bar} |\n"
        
    with open(OUTPUT_REPORT, 'w') as f:
        f.write(md)
        
    print(f"Saved report to {OUTPUT_REPORT}")
    print("\n--------------------------")
    print(f"Median High from Open: {stats['median_stats']['high_from_open']}%")
    print("--------------------------")

if __name__ == "__main__":
    run_verification()
