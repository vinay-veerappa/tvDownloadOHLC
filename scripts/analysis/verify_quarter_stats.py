"""
Independent verification of hourly_quarter_stats.py results.
Uses a brute-force per-hour iteration approach to cross-check the vectorized logic.
Now filters partial hours (< 4 quarters) to match the main script.
"""
import pandas as pd
import json
from pathlib import Path

def verify(ticker="NQ1"):
    # Load the saved JSON
    json_path = Path(f"data/derived/hourly_quarter_stats_{ticker}.json")
    with open(json_path) as f:
        saved = json.load(f)
    
    # Load raw data
    df = pd.read_parquet(f"data/{ticker}_1m.parquet")
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')
    
    df['hour'] = df.index.hour
    df['minute'] = df.index.minute
    df['date_key'] = df.index.date
    
    errors = []
    test_hours = [0, 8, 9, 10, 15, 16, 18]
    
    for h in test_hours:
        h_str = str(h)
        if h_str not in saved:
            print(f"  Hour {h} not in saved data, skipping")
            continue
            
        s = saved[h_str]
        h_data = df[df['hour'] == h]
        
        # Group by date to get hour-level high/low
        grouped = h_data.groupby('date_key')
        
        q1h_q4l_count = 0
        q1l_q4h_count = 0
        q1_high_count = 0
        q4_high_count = 0
        q1_low_count = 0
        q4_low_count = 0
        total = 0
        
        for date, g in grouped:
            # Check all 4 quarters present
            quarters = (g['minute'] // 15).unique()
            if len(quarters) < 4:
                continue
            total += 1
            
            high_minute = g['high'].idxmax().minute
            low_minute = g['low'].idxmin().minute
            
            high_q = high_minute // 15
            low_q = low_minute // 15
            
            if high_q == 0: q1_high_count += 1
            if high_q == 3: q4_high_count += 1
            if low_q == 0: q1_low_count += 1
            if low_q == 3: q4_low_count += 1
            
            if high_q == 0 and low_q == 3:
                q1h_q4l_count += 1
            if low_q == 0 and high_q == 3:
                q1l_q4h_count += 1
        
        print(f"\n=== Hour {h:02d}:00 ===")
        print(f"  Total sessions: saved={s['total_sessions']} vs verify={total} {'✓' if s['total_sessions'] == total else '✗ MISMATCH'}")
        
        saved_q1h = s['h_high_q'].get('Q1', 0)
        saved_q4h = s['h_high_q'].get('Q4', 0)
        saved_q1l = s['h_low_q'].get('Q1', 0)
        saved_q4l = s['h_low_q'].get('Q4', 0)
        
        print(f"  Q1 High: saved={saved_q1h} vs verify={q1_high_count} {'✓' if saved_q1h == q1_high_count else '✗ MISMATCH'}")
        print(f"  Q4 High: saved={saved_q4h} vs verify={q4_high_count} {'✓' if saved_q4h == q4_high_count else '✗ MISMATCH'}")
        print(f"  Q1 Low:  saved={saved_q1l} vs verify={q1_low_count} {'✓' if saved_q1l == q1_low_count else '✗ MISMATCH'}")
        print(f"  Q4 Low:  saved={saved_q4l} vs verify={q4_low_count} {'✓' if saved_q4l == q4_low_count else '✗ MISMATCH'}")
        
        saved_q1h_q4l = s['q1_q4_extremes']['q1_high_q4_low']
        saved_q1l_q4h = s['q1_q4_extremes']['q1_low_q4_high']
        
        print(f"  Q1H/Q4L: saved={saved_q1h_q4l} vs verify={q1h_q4l_count} {'✓' if saved_q1h_q4l == q1h_q4l_count else '✗ MISMATCH'}")
        print(f"  Q1L/Q4H: saved={saved_q1l_q4h} vs verify={q1l_q4h_count} {'✓' if saved_q1l_q4h == q1l_q4h_count else '✗ MISMATCH'}")
        
        # Verify mutual exclusivity sums to total
        ex = s['q1_exclusive']
        ex_sum = ex['high_only'] + ex['low_only'] + ex['both'] + ex['neither']
        print(f"  Exclusive sum: {ex_sum} vs total={s['total_sessions']} {'✓' if ex_sum == s['total_sessions'] else '✗ SUM MISMATCH'}")
        
        # Verify breakout sum = total
        bk = s['q_breakouts']['Q1']
        bk_h_sum = sum(bk['high_violated_in'].values())
        bk_l_sum = sum(bk['low_violated_in'].values())
        print(f"  Breakout H sum: {bk_h_sum} vs total={s['total_sessions']} {'✓' if bk_h_sum == s['total_sessions'] else '✗ SUM MISMATCH'}")
        print(f"  Breakout L sum: {bk_l_sum} vs total={s['total_sessions']} {'✓' if bk_l_sum == s['total_sessions'] else '✗ SUM MISMATCH'}")
        
        # Verify Q1 High 'Never' == Q1 High count
        bk_h_never = bk['high_violated_in']['Never']
        bk_l_never = bk['low_violated_in']['Never']
        print(f"  Q1H Never == Q1H dist: {bk_h_never} vs {saved_q1h} {'✓' if bk_h_never == saved_q1h else '✗ MISMATCH'}")
        print(f"  Q1L Never == Q1L dist: {bk_l_never} vs {saved_q1l} {'✓' if bk_l_never == saved_q1l else '✗ MISMATCH'}")
        
        # Check for any failure
        checks = [
            s['total_sessions'] == total,
            saved_q1h == q1_high_count, saved_q4h == q4_high_count,
            saved_q1l == q1_low_count, saved_q4l == q4_low_count,
            saved_q1h_q4l == q1h_q4l_count, saved_q1l_q4h == q1l_q4h_count,
            ex_sum == s['total_sessions'],
            bk_h_sum == s['total_sessions'], bk_l_sum == s['total_sessions'],
        ]
        if not all(checks):
            errors.append(f"Hour {h}")
    
    if errors:
        print(f"\n❌ ERRORS found in hours: {errors}")
    else:
        print(f"\n✅ All {len(test_hours)} spot-checked hours PASS verification")

if __name__ == "__main__":
    verify()
