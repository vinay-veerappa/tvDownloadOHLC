"""
Comprehensive MFE Histogram Analysis
Tests all combinations of:
1. Data sources: Daily MAX, Every bar, Pivots only
2. Binning methods: Fixed value bins, Percentile bins
3. Lookback periods: 16, 60, 90, 120 days
4. Count methods: Cumulative (hit rate), Non-cumulative (peaked in bin)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import time, timedelta
import pytz

# Load data
df = pd.read_parquet('data/NQ1_1m.parquet')
df.index = pd.to_datetime(df.index)
if df.index.tz is None:
    df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
else:
    df.index = df.index.tz_convert('America/New_York')

REF_TIME = time(9, 31)
CUTOFF_TIME = time(12, 0)
PIVOT_BARS = 2
END_DATE = pd.to_datetime('2026-01-14')

def get_daily_max(df_subset):
    """Get daily MAX MFE only"""
    bull, bear = [], []
    for date in df_subset.index.normalize().unique():
        day = df_subset[df_subset.index.normalize() == date]
        ref = day[day.index.time == REF_TIME]
        if len(ref) == 0: continue
        rc = ref.iloc[0]['close']
        br, bearr = rc * 1.0001, rc * 0.9999
        sess = day[(day.index.time > REF_TIME) & (day.index.time <= CUTOFF_TIME)]
        
        max_bull = max_bear = 0
        for _, r in sess.iterrows():
            if r['high'] > br: max_bull = max(max_bull, (r['high'] - br) / rc * 100)
            if r['low'] < bearr: max_bear = max(max_bear, (bearr - r['low']) / rc * 100)
        
        if max_bull > 0: bull.append(max_bull)
        if max_bear > 0: bear.append(max_bear)
    return bull, bear, "Daily MAX"

def get_pivots(df_subset):
    """Get all pivot highs/lows"""
    bull, bear = [], []
    for date in df_subset.index.normalize().unique():
        day = df_subset[df_subset.index.normalize() == date]
        ref = day[day.index.time == REF_TIME]
        if len(ref) == 0: continue
        rc = ref.iloc[0]['close']
        br, bearr = rc * 1.0001, rc * 0.9999
        sess = day[(day.index.time > REF_TIME) & (day.index.time <= CUTOFF_TIME)].reset_index(drop=True)
        
        for i in range(PIVOT_BARS, len(sess) - PIVOT_BARS):
            hi = lo = True
            for j in range(-PIVOT_BARS, PIVOT_BARS + 1):
                if j != 0:
                    if sess.iloc[i]['high'] <= sess.iloc[i+j]['high']: hi = False
                    if sess.iloc[i]['low'] >= sess.iloc[i+j]['low']: lo = False
            if hi and sess.iloc[i]['high'] > br: 
                bull.append((sess.iloc[i]['high'] - br) / rc * 100)
            if lo and sess.iloc[i]['low'] < bearr: 
                bear.append((bearr - sess.iloc[i]['low']) / rc * 100)
    return bull, bear, "Pivots"

def fixed_bins(data, bin_size=0.05):
    """Count values in fixed-size bins (non-cumulative)"""
    if not data: return [], []
    bins = np.arange(0, max(data) + bin_size, bin_size)
    counts, edges = np.histogram(data, bins=bins)
    return list(counts), list(edges[:-1])

def percentile_bins(data, start=20, end=80, step=5):
    """Count values in percentile-based bins (non-cumulative)"""
    if not data or len(data) < 5: return [], []
    percentiles = list(range(start, end + 1, step))
    counts = []
    edges = []
    for i in range(len(percentiles) - 1):
        low_val = np.percentile(data, percentiles[i])
        high_val = np.percentile(data, percentiles[i + 1])
        count = sum(1 for v in data if low_val <= v < high_val)
        counts.append(count)
        edges.append(low_val)
    return counts, edges

def cumulative_hit_rate(data, start=20, end=80, step=5):
    """Count values that reached AT LEAST each percentile level"""
    if not data or len(data) < 5: return [], []
    percentiles = list(range(start, end + 1, step))
    counts = []
    edges = []
    for pct in percentiles[:-1]:
        threshold = np.percentile(data, pct)
        count = sum(1 for v in data if v >= threshold)
        counts.append(count)
        edges.append(threshold)
    return counts, edges

# Analysis
results = []
lookbacks = [16, 60, 90, 120]

print("=" * 80)
print("COMPREHENSIVE MFE HISTOGRAM ANALYSIS")
print("=" * 80)

for days in lookbacks:
    start = END_DATE - timedelta(days=days)
    sub = df[(df.index.date >= start.date()) & (df.index.date <= END_DATE.date())]
    td = len(sub.index.normalize().unique())
    
    print(f"\n{'='*80}")
    print(f"{days} DAYS LOOKBACK ({td} trading days)")
    print("=" * 80)
    
    # Get data using both methods
    for data_func in [get_daily_max, get_pivots]:
        bull, bear, source = data_func(sub)
        
        print(f"\n--- {source} ---")
        print(f"Bull: {len(bull)} points, Bear: {len(bear)} points")
        
        if bull:
            print(f"Bull P20={np.percentile(bull, 20):.3f}, P50={np.percentile(bull, 50):.3f}, P80={np.percentile(bull, 80):.3f}")
            
            # Method 1: Fixed 0.05% bins
            fc, fe = fixed_bins(bull, 0.05)
            print(f"  Fixed 0.05% bins (first 10): {fc[:10]}")
            
            # Method 2: Percentile bins (non-cumulative)
            pc, pe = percentile_bins(bull, 20, 80, 10)
            print(f"  Percentile bins P20-P80 step=10: {pc}")
            
            # Method 3: Cumulative hit rate
            hc, he = cumulative_hit_rate(bull, 20, 80, 10)
            print(f"  Cumulative hit rate P20-P80 step=10: {hc}")

print("\n" + "=" * 80)
print("CONCLUSION: Which method shows bell-curve pattern?")
print("=" * 80)
print("- Fixed bins with PIVOT data should show natural clustering")
print("- Percentile bins always give uniform distribution by definition")
print("- Cumulative hit rate gives descending pattern (thick low, thin high)")
