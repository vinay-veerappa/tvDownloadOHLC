"""
NQStats Daily Profiler CLI - Unified Engine for Institutional Statistics.
Provides Parity with ProfilerIndicator.pine for any ticker.
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from scripts.utils.fused_data_loader import load_fused_data
from scripts.libs.nqstats.engine import NQStatsEngine
from scripts.libs.nqstats.profiler import get_daily_profiler_data, filter_profiler_stats, get_followthrough_matrix

def main():
    parser = argparse.ArgumentParser(description="Institutional Daily Profiler Analysis")
    parser.add_argument("--ticker", default="NQ1", help="Target Ticker (e.g., NQ1, ES1, CL1)")
    parser.add_argument("--asia", help="Filter by Asia Status (LT, LF, ST, SF)")
    parser.add_argument("--london", help="Filter by London Status (LT, LF, ST, SF)")
    parser.add_argument("--ny1", help="Filter by NY1 Status (LT, LF, ST, SF)")
    parser.add_argument("--prev_ny1", help="Filter by Previous NY1 Status (LT, LF, ST, SF)")
    parser.add_argument("--days", type=int, default=252, help="Days of historical data to analyze")
    parser.add_argument("--csv", help="Save detailed daily results to CSV")
    args = parser.parse_args()

    print(f"🔍 Analyzing Daily Profiler for {args.ticker} (Last {args.days} days)...")

    # 1. Load Data
    df = load_fused_data(args.ticker, timeframe="1m", require_historical=True)
    if df.empty:
        print(f"❌ Error: No data found for {args.ticker}")
        return

    # 2. PERFORMANCE: Filter data to relevant window before heavy processing
    if args.days:
        cutoff_date = datetime.now() - pd.Timedelta(days=args.days + 10) # extra buffer for P12
        cutoff_ts = pd.Timestamp(cutoff_date)
        
        # Ensure cutoff matches index tz-awareness
        if df.index.tz is not None:
            cutoff_ts = cutoff_ts.tz_localize('UTC')
        elif cutoff_ts.tz is not None:
            cutoff_ts = cutoff_ts.tz_convert(None)
            
        df = df[df.index >= cutoff_ts]
        print(f"📉 Filtered data to last {args.days} days ({len(df)} rows)")

    # 3. Process through NQStats Engine
    engine = NQStatsEngine(df, ticker=args.ticker)
    stats = engine.process()
    
    # 4. Aggregate into Daily Profiler format
    daily_data = get_daily_profiler_data(df, stats)
    
    # Debug info (internal)
    lvl_valid = stats['pdh'].notna().mean() * 100
    print(f"DEBUG: Historical Levels PDH Presence: {lvl_valid:.1f}%")
    
    if args.csv:
        daily_data.to_csv(args.csv)
        print(f"✅ Detailed results saved to {args.csv}")

    # 4. Prepare Filters
    filters = {}
    if args.asia: filters['asiabox_status'] = args.asia
    if args.london: filters['londonbox_status'] = args.london
    if args.ny1: filters['ny1box_status'] = args.ny1
    if args.prev_ny1: filters['prev_ny1box_status'] = args.prev_ny1
    
    # 5. Calculate Probabilities
    summary = filter_profiler_stats(daily_data, filters)
    
    if summary.empty:
        print("⚠️ No historical matches found for the specified filters.")
        return

    s = summary.iloc[0]
    
    # 6. Display Results (Parity with UI Table)
    print("\n" + "="*50)
    print(f"📊 PROFILER STATS: {args.ticker}")
    print(f"Filters: {filters if filters else 'NONE (Base Rates)'}")
    print(f"Sample Size: {int(s['count'])} days")
    print("="*50)
    
    print(f"\n[ SESSION OUTCOMES (LT / ST / LF / SF) ]")
    print(f"London: {s['londonbox_status_LT']:.1f}% | {s['londonbox_status_ST']:.1f}% | {s['londonbox_status_LF']:.1f}% | {s['londonbox_status_SF']:.1f}%")
    print(f"NY1:    {s['ny1box_status_LT']:.1f}% | {s['ny1box_status_ST']:.1f}% | {s['ny1box_status_LF']:.1f}% | {s['ny1box_status_SF']:.1f}%")
    print(f"NY2:    {s['ny2box_status_LT']:.1f}% | {s['ny2box_status_ST']:.1f}% | {s['ny2box_status_LF']:.1f}% | {s['ny2box_status_SF']:.1f}%")
    
    print(f"\n[ LEVEL TOUCH PROBABILITIES ]")
    print(f"PDH:    {s.get('touch_pdh', 0):.1f}% | PDL:    {s.get('touch_pdl', 0):.1f}% | PDM:    {s.get('touch_pdm', 0):.1f}%")
    print(f"Settle: {s.get('touch_settle', 0):.1f}% | PWC:    {s.get('touch_pwc', 0):.1f}% | Globex: {s.get('touch_open_glob', 0):.1f}%")
    print(f"Midnight:{s.get('touch_open_mid', 0):.1f}% | 07:30:  {s.get('touch_open_0730', 0):.1f}%")
    
    print(f"\n[ P12 TOUCH PROBABILITIES ]")
    print(f"P12H:   {s.get('touch_p12h', 0):.1f}% | P12L:   {s.get('touch_p12l', 0):.1f}% | P12M:   {s.get('touch_p12m', 0):.1f}%")
    print(f"NY P12H:{s.get('touch_nyp12h', 0):.1f}% | NY P12L:{s.get('touch_nyp12l', 0):.1f}% | NY P12M:{s.get('touch_nyp12m', 0):.1f}%")

    print(f"\n[ HOD / LOD DISTANCES (MEDIAN %) ]")
    print(f"HOD Median Dist: {s.get('hod_dist_med', 0):.2f}%")
    print(f"LOD Median Dist: {s.get('lod_dist_med', 0):.2f}%")
    
    # Only show matrix if no active filter (base rates) or broad view
    if not filters:
        print(f"\n[ ASIA -> LONDON FOLLOW-THROUGH (%) ]")
        ft_mat = get_followthrough_matrix(daily_data, 'asiabox_status', 'londonbox_status')
        if not ft_mat.empty:
            # Print like the UI matrix
            # Sample: LT-LT: 43.14 % | LT-LF: 10.02% ...
            for key in ['LT-LT', 'LT-LF', 'ST-ST', 'ST-SF']:
                if key in ft_mat.index:
                    row = ft_mat.loc[key]
                    print(f"{key}: {row['prob']:.1f}% ({int(row['count'])} hits)", end=" | ")
            print()
    
    print("\n" + "="*50)

if __name__ == "__main__":
    main()
