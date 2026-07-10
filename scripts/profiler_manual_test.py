"""
NQStats Profiler Manual Tester & Performance Verification Agent.
Unified Tool for institutional briefing and live performance extraction.

DOCS & USAGE:
1. Historical Mode:  python profiler_manual_test.py --target NY1 --asia LT --london ST --asia_broken True
2. Live Data Mode:    python profiler_manual_test.py --live --date 2024-03-26 --target London
3. Common Tickers:   ES, NQ, CL, GC, BTC

Logic Standard: 
- Ranges: [min(Mode, Median), max(Mode, Median)] logic from web UI.
- Reach: Joins historical level_touches.json with session-specific time windows.
- Parquet: Uses high-performance vectorized reading (filtered columns).
"""

import sys
import os
import argparse
import pandas as pd
from datetime import datetime
from tabulate import tabulate

# Core Library Imports
from scripts.libs_py.nqstats.engine import NQStatsEngine
from scripts.libs_py.nqstats.profiler import ProfilerAnalyzer

# Silence Pandas warnings globally
pd.set_option('future.no_silent_downcasting', True)

def get_arg_parser():
    parser = argparse.ArgumentParser(description="NQStats Profiler Verification Tool")
    parser.add_argument("--ticker", default="NQ", help="Symbol (ES, NQ, etc)")
    parser.add_argument("--target", default="NY1", help="Target Session (London, NY1, NY2)")
    parser.add_argument("--asia", help="Asia Status (LT, ST, LF, SF)")
    parser.add_argument("--london", help="London Status (LT, ST, LF, SF)")
    parser.add_argument("--asia_broken", type=str, help="Asia Broken (True/False)")
    parser.add_argument("--london_broken", type=str, help="London Broken (True/False)")
    parser.add_argument("--live", action="store_true", help="Enable live verification from Parquet")
    parser.add_argument("--date", help="Date for verification (YYYY-MM-DD)")
    parser.add_argument("--data_dir", default="data")
    parser.add_argument("--live_dir", default="data/live")
    return parser

def print_institutional_report(briefing, ticker, target_session, filters):
    """
    Renders the beautiful institutional briefing matrix.
    """
    if not briefing:
        print(f"\n[!] No historical matches found for {ticker} | {target_session} with criteria: {filters}")
        return

    print(f"\n{'='*145}")
    print(f" NQSTATS INSTITUTIONAL BRIEFING: {ticker} {target_session}")
    print(f" Context: {filters}")
    print(f" Sample Size: {briefing['total_matches']} matching days")
    print(f"{'='*145}")

    table_data = []
    shorthand = {'Long True': 'LT', 'Short True': 'ST', 'Long False': 'LF', 'Short False': 'SF'}
    
    for row in briefing['outcomes']:
        s_out = shorthand.get(row['outcome'], row['outcome'])
        r = row['reach_pcts']
        
        table_data.append([
            f"{s_out} ({row['pct']:.1f}%)",
            row['count'],
            row['lod_time_range'],
            row['hod_time_range'],
            row['lod_dist_range'],
            row['hod_dist_range'],
            f"{row['rev_pct']:.0f}%",
            f"{r.get('pdh',0):.0f}%", f"{r.get('pdl',0):.0f}%", f"{r.get('pdm',0):.0f}%",
            f"{r.get('midnight_open',0):.0f}%", f"{r.get('open_0730',0):.0f}%",
            f"{r.get('p12h',0):.0f}%", f"{r.get('p12m',0):.0f}%", f"{r.get('p12l',0):.0f}%"
        ])

    headers = [
        "Outcome (%)", "Days", "LOD Time", "HOD Time", "LOD Dist", "HOD Dist", "Rev%",
        "PDH", "PDL", "PDM", "MNO", "07:30", "P12H", "P12M", "P12L"
    ]
    print(tabulate(table_data, headers=headers, tablefmt="outline"))
    
    # Interpretation Summary
    top = briefing['outcomes'][0]
    rev_msg = ""
    if top['rev_pct'] > 50:
        rev_msg = f" | High Reversion chance: {top['rev_pct']:.1f}%"
    
    print(f"\n Primary Bias:    {top['outcome']} ({top['pct']:.1f}%){rev_msg}")
    print(f" Time Targets:    HOD Area: {top['hod_time_range']} | LOD Area: {top['lod_time_range']}")
    print(f" Summary:         Consistent with {top['outcome']} profile. Watch for expansion into HOD {top['hod_time_range']}.")
    print(f"{'='*145}\n")

def verify_live_data(args):
    """
    Extracts actual market performance for a specific date from Parquet storage.
    """
    ticker = args.ticker
    target_date = args.date
    target_session = args.target
    
    if not target_date:
        print("[!] Error: --date YYYY-MM-DD is required for live verification.")
        return
    
    # Performance optimized column reading
    cols = ['open', 'high', 'low', 'close', 'timestamp']
    pattern = f"-{ticker}.parquet"
    path = os.path.join(args.live_dir, f"live_storage_{pattern}")
    
    if not os.path.exists(path):
        print(f"[!] Live storage not found: {path}")
        return

    print(f"\n[+] Extracting Live Reality: {ticker} | {target_date}...")
    df = pd.read_parquet(path, columns=cols)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp', inplace=False)
    
    # Filter to the specific day (+/- buffer for 18:00 start)
    target_dt = pd.to_datetime(target_date).date()
    mask = (df.index.date >= target_dt) # Include the day and after for session extraction
    day_df = df[mask].copy()

    if day_df.empty:
        print(f"[!] No data found for {target_date} in storage.")
        return

    engine = NQStatsEngine(day_df, ticker=ticker)
    engine.process()
    
    # Extract session results for the target date
    day_stats = engine.stats[engine.stats.index.date == target_dt].copy()
    if day_stats.empty:
        print(f"[!] Engine failed to classify {target_date}.")
        return

    row = day_stats.iloc[-1]
    
    # Get session OHLC for touch verification
    # Matches box times from profiler.py logic
    box_times = {
        'Asia': ('18:00', '19:30'),
        'London': ('02:30', '03:30'),
        'NY1': ('07:30', '08:30'),
        'NY2': ('11:15', '12:15')
    }
    s_start, s_end = box_times.get(target_session, ('07:30', '08:30'))
    session_df = day_df.between_time(s_start, s_end)
    
    if not session_df.empty:
        s_hod_time = session_df['high'].idxmax().strftime("%H:%M")
        s_lod_time = session_df['low'].idxmin().strftime("%H:%M")
        s_high = session_df['high'].max()
        s_low = session_df['low'].min()
        s_open = session_df['open'].iloc[0]
        s_h_pct = (s_high / s_open - 1) * 100
        s_l_pct = (s_low / s_open - 1) * 100
        
        # Check touches
        touches = {}
        for lvl in ['pdh', 'pdl', 'pdm', 'p12h', 'p12m', 'p12l', 'midnight_open', 'open_0730']:
            key = 'open_mid' if lvl == 'midnight_open' else lvl
            val = row.get(key)
            if val and not pd.isna(val):
                touched = (session_df['low'] <= val).any() and (session_df['high'] >= val).any()
                touches[lvl] = "HIT" if touched else "MISS"
            else:
                touches[lvl] = "N/A"

        print(f"\n{'='*145}")
        print(f" LIVE REALITY SUMMARY: {target_date} | {ticker} {target_session}")
        print(f"{'='*145}")
        print(f" Status:        {row.get(f'{target_session.lower()}box_status', 'Unknown'):<15} (Broken: {row.get(f'{target_session.lower()}box_broken', False)})")
        print(f" Outcome:       HOD {s_hod_time} ({s_h_pct:>+.2f}%) | LOD {s_lod_time} ({s_l_pct:>+.2f}%)")
        print(f" Level Hits:    PDH: {touches.get('pdh','?'):<5} | PDL: {touches.get('pdl','?'):<5} | PDM: {touches.get('pdm','?'):<5}")
        print(f" Institutional: MNO: {touches.get('midnight_open','?'):<5} | 07:30: {touches.get('open_0730','?'):<5}")
        print(f" P12 Levels:    H:   {touches.get('p12h','?'):<5} | M:   {touches.get('p12m','?'):<5} | L:   {touches.get('p12l','?'):<5}")
        print(f"{'='*145}\n")

def main():
    parser = get_arg_parser()
    args = parser.parse_args()
    
    # 1. Live Data Verification (If requested)
    if args.live:
        verify_live_data(args)
        return

    # 2. Historical Probability Analysis
    filters = {}
    if args.asia: filters['Asia'] = args.asia
    if args.london: filters['London'] = args.london
    if args.asia_broken: filters['Asia_broken'] = args.asia_broken == "True"
    if args.london_broken: filters['London_broken'] = args.london_broken == "True"

    analyzer = ProfilerAnalyzer(args.ticker, args.data_dir)
    briefing = analyzer.get_briefing(args.target, filters)
    
    print_institutional_report(briefing, args.ticker, args.target, filters)

if __name__ == "__main__":
    main()