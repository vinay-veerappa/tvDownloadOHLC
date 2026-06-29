import pandas as pd
import numpy as np
import pytz

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

# Load data
df = pd.read_parquet('data/live/live_storage_-NQ.parquet')
df['datetime'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.set_index('datetime')

et = pytz.timezone('America/New_York')

# 1100 BO parameters
OR_START = 1100
OR_END = 1115
CUTOFF = 1230

# Today's OR
or_high = 29735.00
bo_px = 29739.50

def run_for_range(start_date, end_date):
    df_hist = df[(df.index >= start_date) & (df.index < end_date)].copy()
    df_hist = df_hist[~df_hist.index.strftime('%Y-%m-%d').isin(['2026-05-25', '2026-06-19'])]
    
    df_hist['et_time'] = df_hist.index.tz_convert(et)
    df_hist['et_hhmm'] = df_hist['et_time'].dt.hour * 100 + df_hist['et_time'].dt.minute
    df_hist['date'] = df_hist['et_time'].dt.date
    
    sessions = []
    for date, day_1m in df_hist.groupby('date'):
        rth_1m = day_1m[(day_1m['et_hhmm'] >= 930) & (day_1m['et_hhmm'] < 1600)]
        if rth_1m.empty: continue
        
        or_bars = rth_1m[(rth_1m['et_hhmm'] >= OR_START) & (rth_1m['et_hhmm'] < OR_END)]
        if or_bars.empty: continue
        
        or_high_val = or_bars['high'].max()
        or_low_val = or_bars['low'].min()
        
        data_1m = rth_1m[(rth_1m['et_hhmm'] >= OR_END) & (rth_1m['et_hhmm'] < CUTOFF)]
        if data_1m.empty: continue
        
        bo_side = 0
        bo_px_val = None
        bo_idx = None
        for idx, row in data_1m.iterrows():
            if row['close'] > or_high_val:
                bo_side = 1
                bo_px_val = row['close']
                bo_idx = idx
                break
            elif row['close'] < or_low_val:
                bo_side = -1
                bo_px_val = row['close']
                bo_idx = idx
                break
                
        if bo_side == 0: continue
        
        post_bo = data_1m.loc[bo_idx:]
        if bo_side == 1:
            mfe = ((post_bo['high'].max() - bo_px_val) / bo_px_val) * 100
            mae = ((bo_px_val - post_bo['low'].min()) / bo_px_val) * 100
            session_mfe = ((data_1m['high'].max() - or_high_val) / or_high_val) * 100
            session_mae = ((or_high_val - data_1m['low'].min()) / or_high_val) * 100
        else:
            mfe = ((bo_px_val - post_bo['low'].min()) / bo_px_val) * 100
            mae = ((post_bo['high'].max() - bo_px_val) / bo_px_val) * 100
            session_mfe = ((or_low_val - data_1m['low'].min()) / or_low_val) * 100
            session_mae = ((data_1m['high'].max() - or_low_val) / or_low_val) * 100
            
        close_at_cutoff = data_1m['close'].iloc[-1]
        crossed = (bo_side == 1 and close_at_cutoff < or_low_val) or (bo_side == -1 and close_at_cutoff > or_high_val)
        
        sessions.append({
            'side': bo_side, 'mfe': mfe, 'mae': mae, 'session_mfe': session_mfe, 'session_mae': session_mae, 'crossed': crossed
        })
        
    bo = pd.DataFrame(sessions)
    bo['win'] = (bo['session_mfe'] > 0) & ~bo['crossed']
    bo['fake'] = bo['crossed']
    
    bulls = bo[bo['side'] == 1]
    bull_wins = bulls[bulls['win']]
    bull_fakes = bulls[bulls['fake']]
    
    p80_mae = p_nearest(bull_wins['mae'], 80)
    p25_mae = p_nearest(bulls['mae'], 25)
    p20_bo = p_nearest(bulls['mfe'], 20)
    p50_fake = p_nearest(bull_fakes['mfe'], 50)
    p75_fake = p_nearest(bull_fakes['mfe'], 75)
    p50_mfe = p_nearest(bull_wins['session_mfe'], 50)
    rev_p25 = p_nearest(bull_fakes['session_mae'], 25)
    rev_p50 = p_nearest(bull_fakes['session_mae'], 50)
    
    return {
        'n': len(bo),
        'p80_mae': p80_mae,
        'p25_mae': p25_mae,
        'p20_bo': p20_bo,
        'p50_fake': p50_fake,
        'p75_fake': p75_fake,
        'p50_mfe': p50_mfe,
        'rev_p25': rev_p25,
        'rev_p50': rev_p50
    }

ranges = [
    ('73 Sessions (Full)', '2026-03-16', '2026-06-29'),
    ('40 Sessions (Medium)', '2026-05-01', '2026-06-29'),
    ('10 Sessions (Short)', '2026-06-15', '2026-06-29')
]

print("======================================================================")
print("LOOKBACK RANGE SENSITIVITY VALIDATION (Today's Projected Price Levels)")
print("======================================================================")

for name, start, end in ranges:
    res = run_for_range(start, end)
    print(f"\nRange: {name} (N_breakouts = {res['n']})")
    print(f"  P80 MAE (Wins)       : {res['p80_mae']:.3f}% -> {bo_px * (1 - res['p80_mae']/100):,.2f}")
    print(f"  Pullback Act (P25)   : {res['p25_mae']:.3f}% -> {bo_px * (1 - res['p25_mae']/100):,.2f}")
    print(f"  BO Cashflow (P20)    : {res['p20_bo']:.3f}% -> {bo_px * (1 + res['p20_bo']/100):,.2f}")
    print(f"  Pivot Level (P50)    : {res['p50_fake']:.3f}% -> {bo_px * (1 + res['p50_fake']/100):,.2f}")
    print(f"  BO Confirm (P75)     : {res['p75_fake']:.3f}% -> {bo_px * (1 + res['p75_fake']/100):,.2f}")
    print(f"  Median MFE (P50)     : {res['p50_mfe']:.3f}% -> {or_high * (1 + res['p50_mfe']/100):,.2f}")
    print(f"  Reversal Top (P25)   : {res['rev_p25']:.3f}% -> {or_high * (1 - res['rev_p25']/100):,.2f}")
    print(f"  Reversal Bot (P50)   : {res['rev_p50']:.3f}% -> {or_high * (1 - res['rev_p50']/100):,.2f}")
