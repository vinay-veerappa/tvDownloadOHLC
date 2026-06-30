"""
Find sessions where EV target (0.30%) was NOT hit on 5m but was close.
These are the sessions the user should verify on the chart to determine
if the Gunship uses 1m MFE (which would catch intrabar moves hidden by 5m compression).

Also compare: EV target hit count vs Gunship FULL count for each preset.
"""
import pandas as pd
import numpy as np
import pytz

df_1m = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df_1m['datetime'] = pd.to_datetime(df_1m['timestamp'], utc=True)
df_1m = df_1m.set_index('datetime')
df_1m = df_1m[['open', 'high', 'low', 'close', 'volume']].copy()

et = pytz.timezone('America/New_York')
df_1m['et_time'] = df_1m.index.tz_convert(et)
df_1m['et_hhmm'] = df_1m['et_time'].dt.hour * 100 + df_1m['et_time'].dt.minute
df_1m['et_dow'] = df_1m['et_time'].dt.dayofweek
df_1m['date'] = df_1m['et_time'].dt.date

df_1m = df_1m[df_1m['date'] <= pd.Timestamp('2026-06-26').date()]
HOLIDAYS = {pd.Timestamp('2026-04-03').date(), pd.Timestamp('2026-05-25').date(), pd.Timestamp('2026-06-19').date()}
df_1m = df_1m[~df_1m['date'].isin(HOLIDAYS)]
df_1m = df_1m[df_1m['date'] >= pd.Timestamp('2026-03-12').date()]

df_5m = df_1m.resample('5min', label='left', closed='left').agg(
    {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}).dropna()
df_5m['et_time'] = df_5m.index.tz_convert(et)
df_5m['et_hhmm'] = df_5m['et_time'].dt.hour * 100 + df_5m['et_time'].dt.minute
df_5m['et_dow'] = df_5m['et_time'].dt.dayofweek
df_5m['date'] = df_5m['et_time'].dt.date

def days_to_python_dow(days_str):
    pine_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    return set(pine_to_python[int(d)] for d in days_str)

PRESETS = {
    '1100 BO':     {'or_start': 1100, 'or_end': 1115, 'cutoff': 1230, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-13',
                    'target_full': 55, 'target_failed': 18},
    'MO Break':    {'or_start': 930,  'or_end': 935,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12',
                    'target_full': 32, 'target_failed': 42},
    '1800 Break':  {'or_start': 1800, 'or_end': 1815, 'cutoff': 300,  'days': '12345',
                    'crosses_midnight': True, 'start_date': '2026-03-12',
                    'target_full': 35, 'target_failed': 40},
    'Q1 Break':    {'or_start': 600,  'or_end': 830,  'cutoff': 1200, 'days': '23456',
                    'crosses_midnight': False, 'start_date': '2026-03-12',
                    'target_full': 44, 'target_failed': 29},
}

def build_sessions(cfg):
    valid_dows = days_to_python_dow(cfg['days'])
    start_date = pd.Timestamp(cfg['start_date']).date()
    sessions = []
    for date in sorted(df_1m['date'].unique()):
        if date < start_date: continue
        if date in HOLIDAYS: continue
        if date.weekday() not in valid_dows: continue
        if cfg['crosses_midnight']:
            next_date = date + pd.Timedelta(days=1)
            session_1m = pd.concat([
                df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= cfg['or_start'])],
                df_1m[(df_1m['date'] == next_date) & (df_1m['et_hhmm'] < cfg['cutoff'])]])
            session_5m = pd.concat([
                df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start'])],
                df_5m[(df_5m['date'] == next_date) & (df_5m['et_hhmm'] < cfg['cutoff'])]])
        else:
            session_1m = df_1m[(df_1m['date'] == date) & (df_1m['et_hhmm'] >= cfg['or_start']) & (df_1m['et_hhmm'] < cfg['cutoff'])]
            session_5m = df_5m[(df_5m['date'] == date) & (df_5m['et_hhmm'] >= cfg['or_start']) & (df_5m['et_hhmm'] < cfg['cutoff'])]
        if session_1m.empty or session_5m.empty: continue
        or_bars = session_1m[(session_1m['et_hhmm'] >= cfg['or_start']) & (session_1m['et_hhmm'] < cfg['or_end'])]
        if or_bars.empty: continue
        or_high = or_bars['high'].max()
        or_low = or_bars['low'].min()
        data_1m = session_1m[session_1m['et_hhmm'] >= cfg['or_end']]
        data_5m = session_5m[session_5m['et_hhmm'] >= cfg['or_end']]
        if data_1m.empty or data_5m.empty: continue
        
        bo_side = 0; bo_px = None; bo_idx = None
        for idx, row in data_1m.iterrows():
            if row['close'] > or_high:
                bo_side = 1; bo_px = row['close']; bo_idx = idx; break
            elif row['close'] < or_low:
                bo_side = -1; bo_px = row['close']; bo_idx = idx; break
        if bo_side == 0: continue
        
        bo_5m_idx = None
        for idx in data_5m.index:
            if idx >= bo_idx: bo_5m_idx = idx; break
        if bo_5m_idx is None: bo_5m_idx = data_5m.index[0]
        post_bo_5m = data_5m.loc[bo_5m_idx:]
        post_bo_1m = data_1m.loc[bo_idx:]
        
        # MFE from 5m bars
        if bo_side == 1:
            mfe_5m = ((post_bo_5m['high'].max() - bo_px) / bo_px) * 100
        else:
            mfe_5m = ((bo_px - post_bo_5m['low'].min()) / bo_px) * 100
        
        # MFE from 1m bars (catches intrabar moves hidden by 5m)
        if bo_side == 1:
            mfe_1m = ((post_bo_1m['high'].max() - bo_px) / bo_px) * 100
        else:
            mfe_1m = ((bo_px - post_bo_1m['low'].min()) / bo_px) * 100
        
        # EV target hit on 5m vs 1m
        target_px = bo_px * (1 + bo_side * 0.30 / 100)
        ev_hit_5m = False
        for idx, row in post_bo_5m.iterrows():
            if bo_side == 1 and row['high'] >= target_px:
                ev_hit_5m = True; break
            elif bo_side == -1 and row['low'] <= target_px:
                ev_hit_5m = True; break
        ev_hit_1m = False
        for idx, row in post_bo_1m.iterrows():
            if bo_side == 1 and row['high'] >= target_px:
                ev_hit_1m = True; break
            elif bo_side == -1 and row['low'] <= target_px:
                ev_hit_1m = True; break
        
        # R2/R3 for reference
        r2_fail = False
        for idx, row in post_bo_5m.iterrows():
            if bo_side == 1 and row['close'] < or_low:
                r2_fail = True; break
            elif bo_side == -1 and row['close'] > or_high:
                r2_fail = True; break
        r3_fail = False
        for idx, row in post_bo_5m.iterrows():
            if bo_side == 1 and row['low'] < or_low:
                r3_fail = True; break
            elif bo_side == -1 and row['high'] > or_high:
                r3_fail = True; break
        
        sessions.append({
            'date': date, 'side': bo_side, 'bo_px': bo_px,
            'or_high': or_high, 'or_low': or_low,
            'mfe_5m': mfe_5m, 'mfe_1m': mfe_1m,
            'ev_hit_5m': ev_hit_5m, 'ev_hit_1m': ev_hit_1m,
            'r2_fail': r2_fail, 'r3_fail': r3_fail,
        })
    return pd.DataFrame(sessions)

# Build sessions for all presets
for name, cfg in PRESETS.items():
    df_p = build_sessions(cfg)
    
    ev_5m = df_p['ev_hit_5m'].sum()
    ev_1m = df_p['ev_hit_1m'].sum()
    not_r3 = (~df_p['r3_fail']).sum()
    not_r2 = (~df_p['r2_fail']).sum()
    
    print("=" * 80)
    print(f"{name} (target FULL={cfg['target_full']}, FAILED={cfg['target_failed']})")
    print("=" * 80)
    print(f"  N={len(df_p)}")
    print(f"  EV target hit (5m): {ev_5m}  (target FULL={cfg['target_full']}) Δ={ev_5m - cfg['target_full']}")
    print(f"  EV target hit (1m): {ev_1m}  (target FULL={cfg['target_full']}) Δ={ev_1m - cfg['target_full']}")
    print(f"  Not R3 fail:        {not_r3}")
    print(f"  Not R2 fail:        {not_r2}")
    print()
    
    # Show sessions where 5m didn't hit EV but 1m did (1m vs 5m discrepancy)
    discrep = df_p[(~df_p['ev_hit_5m']) & (df_p['ev_hit_1m'])]
    if len(discrep) > 0:
        print(f"  Sessions where 1m hit EV but 5m didn't ({len(discrep)} sessions):")
        for _, r in discrep.iterrows():
            print(f"    {r['date']} side={'bull' if r['side']==1 else 'bear'} "
                  f"BO={r['bo_px']:.2f} MFE5m={r['mfe_5m']:.3f}% MFE1m={r['mfe_1m']:.3f}%")
        print()
    
    # Show sessions where NEITHER 5m nor 1m hit EV, sorted by MFE (closest to 0.30% first)
    # These are the sessions the user should check on the chart
    no_ev = df_p[(~df_p['ev_hit_5m']) & (~df_p['ev_hit_1m'])].copy()
    if len(no_ev) > 0:
        no_ev['mfe_max'] = no_ev[['mfe_5m', 'mfe_1m']].max(axis=1)
        no_ev = no_ev.sort_values('mfe_max', ascending=False)
        print(f"  Sessions where EV NOT hit (any TF), closest to 0.30% first (top 15):")
        print(f"  {'Date':<12} {'Side':>4} {'BO px':>10} {'MFE 5m':>8} {'MFE 1m':>8} {'R2':>4} {'R3':>4}")
        for _, r in no_ev.head(15).iterrows():
            print(f"  {str(r['date']):<12} {'bull' if r['side']==1 else 'bear':>4} {r['bo_px']:>10.2f} "
                  f"{r['mfe_5m']:>7.3f}% {r['mfe_1m']:>7.3f}% {'Y' if r['r2_fail'] else 'N':>4} {'Y' if r['r3_fail'] else 'N':>4}")
        print()
    
    # Also show: sessions where EV WAS hit but R2/R3 fail (these would be wins by EV but fails by R-rule)
    ev_hit_but_r3 = df_p[df_p['ev_hit_5m'] & df_p['r3_fail']]
    if len(ev_hit_but_r3) > 0:
        print(f"  Sessions where EV hit BUT R3 fail ({len(ev_hit_but_r3)} sessions):")
        for _, r in ev_hit_but_r3.iterrows():
            print(f"    {r['date']} side={'bull' if r['side']==1 else 'bear'} "
                  f"MFE5m={r['mfe_5m']:.3f}% R3={'fail' if r['r3_fail'] else 'win'}")
        print()
    
    print()