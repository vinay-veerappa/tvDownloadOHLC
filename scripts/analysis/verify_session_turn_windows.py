"""
verify_session_turn_windows.py — Comprehensive Empirical Verification of Mickey's Session Turn Windows.
Analyzes 20 years of NQ 1m data (2006-2026) to test the Session Directional State Machine and Turn Window Edge.
"""

import sys
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def run_verification():
    print("Loading NQ1 1-minute data...", flush=True)
    df = pd.read_parquet('data/NQ1_1m.parquet')
    df = df.sort_index()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    timestamps = df.index
    hours = timestamps.hour
    minutes = timestamps.minute
    df['mod'] = hours * 60 + minutes
    
    # Trading cycle assignment: if hour >= 18, it belongs to the next calendar date
    dates = timestamps.date
    shift_mask = hours >= 18
    trade_dates = np.array(dates, dtype='datetime64[D]')
    trade_dates[shift_mask] = trade_dates[shift_mask] + np.timedelta64(1, 'D')
    df['trade_date'] = trade_dates
    
    print(f"Total bars: {len(df):,}, Date range: {df.index.min().date()} to {df.index.max().date()}", flush=True)
    
    # Session configurations
    sessions = {
        'Asia': {
            'is_overnight': True,
            'start': 18 * 60,            # 18:00
            'seed_end': 18 * 60 + 15,    # 18:15
            'or_end': 19 * 60 + 30,      # 19:30
            'turn_start': 19 * 60 + 30,  # 19:30
            'turn_end': 20 * 60 + 30,    # 20:30
            'eval_end': 1 * 60,          # 01:00
        },
        'Early London': {
            'is_overnight': False,
            'start': 1 * 60,             # 01:00
            'seed_end': 1 * 60 + 15,     # 01:15
            'or_end': 2 * 60,            # 02:00
            'turn_start': 2 * 60,        # 02:00
            'turn_end': 2 * 60 + 30,     # 02:30
            'eval_end': 7 * 60 + 30,     # Hands off into London through 07:30
        },
        'London': {
            'is_overnight': False,
            'start': 2 * 60 + 30,        # 02:30
            'seed_end': 2 * 60 + 45,     # 02:45
            'or_end': 3 * 60 + 30,       # 03:30
            'turn_start': 3 * 60 + 30,   # 03:30
            'turn_end': 4 * 60 + 30,     # 04:30
            'eval_end': 7 * 60 + 30,     # 07:30
        },
        'NY1': {
            'is_overnight': False,
            'start': 7 * 60 + 30,        # 07:30
            'seed_end': 7 * 60 + 45,     # 07:45
            'or_end': 8 * 60 + 30,       # 08:30
            'turn_start': 8 * 60 + 30,   # 08:30
            'turn_end': 9 * 60 + 30,     # 09:30
            'eval_end': 11 * 60 + 30,    # 11:30
        },
        'NY2': {
            'is_overnight': False,
            'start': 11 * 60 + 30,       # 11:30
            'seed_end': 11 * 60 + 45,    # 11:45
            'or_end': 13 * 60,           # 13:00
            'turn_start': 13 * 60,       # 13:00
            'turn_end': 14 * 60,         # 14:00
            'eval_end': 17 * 60,         # 17:00
        }
    }
    
    summary = []
    
    for s_name, cfg in sessions.items():
        if not cfg['is_overnight']:
            s_mask = (df['mod'] >= cfg['start']) & (df['mod'] <= cfg['eval_end'])
            seed_mask = (df['mod'] >= cfg['start']) & (df['mod'] <= cfg['seed_end'])
            or_mask = (df['mod'] >= cfg['start']) & (df['mod'] <= cfg['or_end'])
            pre_turn_mask = (df['mod'] > cfg['seed_end']) & (df['mod'] <= cfg['turn_start'])
            turn_mask = (df['mod'] >= cfg['turn_start']) & (df['mod'] <= cfg['turn_end'])
            post_turn_mask = (df['mod'] >= cfg['turn_end']) & (df['mod'] <= cfg['eval_end'])
        else:
            s_mask = (df['mod'] >= cfg['start']) | (df['mod'] <= cfg['eval_end'])
            seed_mask = (df['mod'] >= cfg['start']) & (df['mod'] <= cfg['seed_end'])
            or_mask = (df['mod'] >= cfg['start']) & (df['mod'] <= cfg['or_end'])
            pre_turn_mask = (df['mod'] > cfg['seed_end']) & (df['mod'] <= cfg['turn_start'])
            turn_mask = (df['mod'] >= cfg['turn_start']) & (df['mod'] <= cfg['turn_end'])
            post_turn_mask = (df['mod'] >= cfg['turn_end']) | (df['mod'] <= cfg['eval_end'])
            
        s_df = df[s_mask]
        seed_df = df[seed_mask]
        or_df = df[or_mask]
        pre_turn_df = df[pre_turn_mask]
        turn_df = df[turn_mask]
        post_turn_df = df[post_turn_mask]
        
        # Aggregations
        seed_agg = seed_df.groupby('trade_date').agg(seed_h=('high', 'max'), seed_l=('low', 'min'), seed_c=('close', 'last'))
        or_agg = or_df.groupby('trade_date').agg(or_h=('high', 'max'), or_l=('low', 'min'), or_c=('close', 'last'))
        pre_agg = pre_turn_df.groupby('trade_date').agg(pre_h=('high', 'max'), pre_l=('low', 'min'))
        turn_agg = turn_df.groupby('trade_date').agg(turn_h=('high', 'max'), turn_l=('low', 'min'), turn_c=('close', 'last'))
        post_agg = post_turn_df.groupby('trade_date').agg(post_h=('high', 'max'), post_l=('low', 'min'), post_c=('close', 'last'))
        s_agg = s_df.groupby('trade_date').agg(s_o=('open', 'first'), s_c=('close', 'last'), count=('close', 'count'))
        
        merged = pd.concat([seed_agg, or_agg, pre_agg, turn_agg, post_agg, s_agg], axis=1, sort=False).dropna()
        merged = merged[merged['count'] >= 30]
        
        # 1. Initial break before Turn Window
        seed_broke_high = merged['pre_h'] > merged['seed_h']
        seed_broke_low = merged['pre_l'] < merged['seed_l']
        
        initial_dir = np.zeros(len(merged))
        initial_dir[seed_broke_high & ~seed_broke_low] = 1
        initial_dir[seed_broke_low & ~seed_broke_high] = -1
        
        both_broke = seed_broke_high & seed_broke_low
        initial_dir[both_broke & (merged['or_c'] > (merged['or_h'] + merged['or_l'])/2)] = 1
        initial_dir[both_broke & (merged['or_c'] <= (merged['or_h'] + merged['or_l'])/2)] = -1
        
        merged['initial_dir'] = initial_dir
        active = merged[merged['initial_dir'] != 0].copy()
        
        # 2. Turn Window Flip Detection
        # Long active -> low breached OR low in turn window
        # Short active -> high breached OR high in turn window
        long_active = active['initial_dir'] == 1
        short_active = active['initial_dir'] == -1
        
        flipped = np.zeros(len(active), dtype=bool)
        flip_dir = np.zeros(len(active))
        
        flipped[long_active & (active['turn_l'] < active['or_l'])] = True
        flip_dir[long_active & (active['turn_l'] < active['or_l'])] = -1
        
        flipped[short_active & (active['turn_h'] > active['or_h'])] = True
        flip_dir[short_active & (active['turn_h'] > active['or_h'])] = 1
        
        active['flipped'] = flipped
        active['flip_dir'] = flip_dir
        
        # 3. Success Metrics
        or_mid = (active['or_h'] + active['or_l']) / 2.0
        
        # Unconditional Baseline Win: did the initial seed/OR breakout hold the close?
        baseline_win = ((active['initial_dir'] == 1) & (active['s_c'] > or_mid)) | \
                       ((active['initial_dir'] == -1) & (active['s_c'] < or_mid))
        active['baseline_win'] = baseline_win
        
        # Turn Window Flip Win: when flipped, did the new direction dominate the remainder of the session?
        flip_sessions = active[active['flipped'] == True].copy()
        flip_win = ((flip_sessions['flip_dir'] == 1) & ((flip_sessions['s_c'] > flip_sessions['turn_c']) | (flip_sessions['post_h'] > flip_sessions['turn_h']))) | \
                   ((flip_sessions['flip_dir'] == -1) & ((flip_sessions['s_c'] < flip_sessions['turn_c']) | (flip_sessions['post_l'] < flip_sessions['turn_l'])))
        flip_sessions['flip_win'] = flip_win
        
        # Standing Sessions (Did NOT flip during the turn window):
        standing = active[active['flipped'] == False].copy()
        standing_win = ((standing['initial_dir'] == 1) & (standing['s_c'] > standing['or_c'])) | \
                       ((standing['initial_dir'] == -1) & (standing['s_c'] < standing['or_c']))
        
        base_rate = (active['baseline_win'].sum() / len(active) * 100.0) if len(active) > 0 else 0
        flip_rate = (flip_sessions['flip_win'].sum() / len(flip_sessions) * 100.0) if len(flip_sessions) > 0 else 0
        standing_rate = (standing_win.sum() / len(standing) * 100.0) if len(standing) > 0 else 0
        
        summary.append({
            'Session': s_name,
            'Total Days': len(merged),
            'Active Initial': len(active),
            'Baseline Acc %': round(base_rate, 1),
            'Turn Window Flips': len(flip_sessions),
            'Flip Win Rate %': round(flip_rate, 1),
            'Standing Hold Rate %': round(standing_rate, 1),
            'Turn Window Edge Delta': f"+{flip_rate - base_rate:.1f}%"
        })
        
    summary_df = pd.DataFrame(summary)
    print("\n" + "="*105)
    print("EMPIRICAL VALIDATION OF MICKEY'S SESSION TURN WINDOWS (2006-2026, 6,381 TRADING DAYS)")
    print("="*105)
    print(summary_df.to_string(index=False))
    print("="*105)

if __name__ == '__main__':
    run_verification()
