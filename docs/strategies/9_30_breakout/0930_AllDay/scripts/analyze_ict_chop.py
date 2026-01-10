"""
ICT Chop Filter Analysis - Alternative Hypotheses
=================================================
Testing: Depth Pattern, Time Since Breakout, Prior Failure
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys

ROOT = Path(r"c:\Users\vinay\tvDownloadOHLC")
DATA_DIR = ROOT / "data"
RETEST_DIR = DATA_DIR / "derived" / "retests"

def load_and_flatten_retests(ticker):
    path = RETEST_DIR / f"or_retests_{ticker}_1m.parquet.jsonl"
    if not path.exists():
        return None
    
    df = pd.read_json(path, lines=True)
    
    all_retests = []
    for _, row in df.iterrows():
        day_date = pd.to_datetime(row['date']).date()
        or_high = row['or_high']
        or_low = row['or_low']
        or_height = row['or_height']
        breakout_dir = row['breakout_dir']
        breakout_time = row.get('breakout_time')
        
        retests = row.get('retests', [])
        if not retests:
            continue
        
        for i, retest in enumerate(retests):
            try:
                start_time_str = retest.get('start_time', '')
                if not start_time_str:
                    continue
                
                hours, mins = int(start_time_str.split(':')[0]), int(start_time_str.split(':')[1])
                retest_dt = datetime(day_date.year, day_date.month, day_date.day, hours, mins)
                
                mfe = retest.get('excursion_mfe_norm', 0) or 0
                mae = abs(retest.get('excursion_mae_norm', 0) or 0)
                depth_pct = retest.get('max_depth_pct_range', 0) or 0
                
                all_retests.append({
                    'date': day_date,
                    'retest_time': retest_dt,
                    'hour': hours,
                    'minute': mins,
                    'or_height': or_height,
                    'direction': breakout_dir,
                    'mfe': mfe,
                    'mae': mae,
                    'depth_pct': depth_pct,  # How deep into OR
                    'retest_index': i,  # 0 = first, 1 = second, etc.
                    'is_winner': mfe > mae
                })
            except:
                continue
    
    return pd.DataFrame(all_retests)


def analyze_filters(ticker="NQ1"):
    print(f"\n{'='*70}")
    print(f"ALTERNATIVE FILTER ANALYSIS: {ticker}")
    print(f"{'='*70}")
    
    df = load_and_flatten_retests(ticker)
    if df is None or len(df) == 0:
        return
    
    # Filter post-10AM, 2023+ for more data
    df = df[df['date'] >= datetime(2023, 1, 1).date()].copy()
    post_10am = df[df['hour'] >= 10].copy()
    
    print(f"Total retests (2023+, post-10AM): {len(post_10am):,}")
    print(f"Losers: {(~post_10am['is_winner']).sum():,} | Winners: {post_10am['is_winner'].sum():,}")
    
    # =========================================================================
    # FILTER 1: DEPTH PATTERN
    # =========================================================================
    print(f"\n{'='*70}")
    print("FILTER 1: RETEST DEPTH PATTERN")
    print("  Hypothesis: Deep retests (>50% into OR) fail more often")
    print(f"{'='*70}")
    
    depth_results = []
    for depth_thresh in [25, 50, 75, 100, 150]:
        deep = post_10am[post_10am['depth_pct'] > depth_thresh]
        shallow = post_10am[post_10am['depth_pct'] <= depth_thresh]
        
        deep_wr = deep['is_winner'].mean() * 100 if len(deep) > 0 else 0
        shallow_wr = shallow['is_winner'].mean() * 100 if len(shallow) > 0 else 0
        
        depth_results.append({
            'threshold': depth_thresh,
            'deep_count': len(deep),
            'deep_wr': deep_wr,
            'shallow_count': len(shallow),
            'shallow_wr': shallow_wr,
            'improvement': shallow_wr - deep_wr
        })
        
        print(f"  Depth > {depth_thresh}%: WR = {deep_wr:.1f}% ({len(deep)} trades)")
        print(f"  Depth ≤ {depth_thresh}%: WR = {shallow_wr:.1f}% ({len(shallow)} trades)")
        print(f"  → Improvement by skipping deep: {shallow_wr - deep_wr:+.1f}%")
        print()
    
    # =========================================================================
    # FILTER 2: RETEST INDEX (First vs Later)
    # =========================================================================
    print(f"\n{'='*70}")
    print("FILTER 2: RETEST INDEX (First vs Later Attempts)")
    print("  Hypothesis: Later retest attempts (2nd, 3rd) fail more")
    print(f"{'='*70}")
    
    for idx in [0, 1, 2]:
        subset = post_10am[post_10am['retest_index'] == idx]
        wr = subset['is_winner'].mean() * 100 if len(subset) > 0 else 0
        print(f"  Retest #{idx+1}: WR = {wr:.1f}% ({len(subset)} trades)")
    
    first_only = post_10am[post_10am['retest_index'] == 0]
    later = post_10am[post_10am['retest_index'] > 0]
    first_wr = first_only['is_winner'].mean() * 100 if len(first_only) > 0 else 0
    later_wr = later['is_winner'].mean() * 100 if len(later) > 0 else 0
    print(f"\n  First retest only: WR = {first_wr:.1f}%")
    print(f"  Later retests: WR = {later_wr:.1f}%")
    print(f"  → Skip later retests saves: {first_wr - later_wr:+.1f}%")
    
    # =========================================================================
    # FILTER 3: PRIOR RETEST OUTCOME
    # =========================================================================
    print(f"\n{'='*70}")
    print("FILTER 3: PRIOR RETEST OUTCOME")
    print("  Hypothesis: If first retest fails, skip the rest of day")
    print(f"{'='*70}")
    
    # Group by date, check if first retest won
    day_groups = post_10am.groupby('date')
    
    after_winner = []
    after_loser = []
    
    for date, group in day_groups:
        group = group.sort_values('retest_time')
        if len(group) < 2:
            continue
            
        first = group.iloc[0]
        rest = group.iloc[1:]
        
        if first['is_winner']:
            after_winner.extend(rest['is_winner'].tolist())
        else:
            after_loser.extend(rest['is_winner'].tolist())
    
    if after_winner:
        aw_wr = sum(after_winner) / len(after_winner) * 100
        print(f"  After WINNING first retest: WR = {aw_wr:.1f}% ({len(after_winner)} trades)")
    
    if after_loser:
        al_wr = sum(after_loser) / len(after_loser) * 100
        print(f"  After LOSING first retest: WR = {al_wr:.1f}% ({len(after_loser)} trades)")
        
    if after_winner and after_loser:
        print(f"  → Skip trades after losing first retest saves: {aw_wr - al_wr:+.1f}%")
    
    # =========================================================================
    # FILTER 4: HOUR OF DAY
    # =========================================================================
    print(f"\n{'='*70}")
    print("FILTER 4: HOUR OF DAY")
    print("  Win rate by entry hour")
    print(f"{'='*70}")
    
    for hour in range(10, 16):
        subset = post_10am[post_10am['hour'] == hour]
        wr = subset['is_winner'].mean() * 100 if len(subset) > 0 else 0
        count = len(subset)
        marker = " ★" if wr > 55 else " ⚠️" if wr < 40 else ""
        print(f"  {hour:02d}:00 - {hour:02d}:59: WR = {wr:.1f}% ({count} trades){marker}")
    
    # =========================================================================
    # COMBINED: BEST FILTERS
    # =========================================================================
    print(f"\n{'='*70}")
    print("COMBINED FILTER SIMULATION")
    print("  Applying best individual filters together")
    print(f"{'='*70}")
    
    # Base case
    base_wr = post_10am['is_winner'].mean() * 100
    base_count = len(post_10am)
    print(f"  Baseline: WR = {base_wr:.1f}% ({base_count} trades)")
    
    # Apply filters
    filtered = post_10am.copy()
    
    # Skip deep retests (>75% depth)
    filtered = filtered[filtered['depth_pct'] <= 75]
    depth_wr = filtered['is_winner'].mean() * 100 if len(filtered) > 0 else 0
    print(f"  + Skip depth > 75%: WR = {depth_wr:.1f}% ({len(filtered)} trades)")
    
    # Skip later retests
    filtered = filtered[filtered['retest_index'] == 0]
    first_wr = filtered['is_winner'].mean() * 100 if len(filtered) > 0 else 0
    print(f"  + First retest only: WR = {first_wr:.1f}% ({len(filtered)} trades)")
    
    print(f"\n  → Combined improvement: {first_wr - base_wr:+.1f}%")
    print(f"  → Trades reduced: {base_count - len(filtered)} ({(base_count - len(filtered))/base_count*100:.1f}%)")


if __name__ == "__main__":
    for ticker in ["NQ1", "ES1", "YM1"]:
        analyze_filters(ticker)
        print("\n" + "="*70 + "\n")
