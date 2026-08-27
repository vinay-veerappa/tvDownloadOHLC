"""
Empirical Backtest: Pack Trading Quarters Theory Confluences across 7.5 Years (2019-2026, NQ1)
1. Hourly Time Quarters (Q1 :00-:15 Judas vs Q2/Q3 :15-:45 Ignition/Expansion)
2. Range / IB Quartiles (25% Discount vs 75% Premium Boundaries)
3. Price Grid Quarters (250 pt / 500 pt Major Quarters & Hesitation Zones)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

def run_quarters_study():
    data_path = Path('data/NQ1_1m.parquet')
    if not data_path.exists():
        print('Data not found')
        return

    print('[INFO] Loading NQ1 data (2019-2026)...')
    df = pd.read_parquet(data_path)
    df = df.sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')

    df['time'] = df.index.time
    df['date'] = df.index.date
    df['minute'] = df.index.minute
    df = df[df.index >= '2019-01-01'].copy()

    # 1. Study 1: Hourly Time Quarters in 10:00 AM Hour (10:00 - 11:00)
    # Classify which quarter the 10:00-11:00 hour set its High and Low
    h10_bars = df[(df['time'] >= time(10, 0)) & (df['time'] < time(11, 0))]
    
    hourly_quarter_stats = []
    for d, g in h10_bars.groupby('date'):
        if len(g) < 50: continue
        h_idx = g['high'].idxmax()
        l_idx = g['low'].idxmin()
        h_min = h_idx.minute
        l_min = l_idx.minute
        
        h_q = 'Q1 (00-15m)' if h_min < 15 else ('Q2 (15-30m)' if h_min < 30 else ('Q3 (30-45m)' if h_min < 45 else 'Q4 (45-60m)'))
        l_q = 'Q1 (00-15m)' if l_min < 15 else ('Q2 (15-30m)' if l_min < 30 else ('Q3 (30-45m)' if l_min < 45 else 'Q4 (45-60m)'))
        
        h10_open = g.iloc[0]['open']
        h10_close = g.iloc[-1]['close']
        is_green = h10_close > h10_open
        
        hourly_quarter_stats.append({
            'date': d, 'high_q': h_q, 'low_q': l_q,
            'is_green': is_green, 'h10_open': h10_open, 'h10_close': h10_close
        })

    df_hq = pd.DataFrame(hourly_quarter_stats)
    
    print('='*90)
    print('PACK TRADING QUARTERS THEORY EMPIRICAL STUDY (2019-2026, 1,958 SESSIONS)')
    print('='*90)
    print('\n[1. HOURLY TIME QUARTERS: 10:00-11:00 AM HOUR HIGH/LOW TIMING]')
    print(f'Total Analyzed 10:00 AM Hours: {len(df_hq):,d}')
    
    for q in ['Q1 (00-15m)', 'Q2 (15-30m)', 'Q3 (30-45m)', 'Q4 (45-60m)']:
        sub = df_hq[df_hq['high_q'] == q]
        red_prob = (~sub['is_green']).mean() * 100
        print(f'  • High formed in {q:12s}: {len(sub):4d} sessions ({len(sub)/len(df_hq)*100:4.1f}%) | Hour Closes RED: {red_prob:5.1f}%')

    print('\n[1.1 HOURLY TIME QUARTERS: LOW FORMATION TIMING]')
    for q in ['Q1 (00-15m)', 'Q2 (15-30m)', 'Q3 (30-45m)', 'Q4 (45-60m)']:
        sub = df_hq[df_hq['low_q'] == q]
        green_prob = (sub['is_green']).mean() * 100
        print(f'  • Low formed in  {q:12s}: {len(sub):4d} sessions ({len(sub)/len(df_hq)*100:4.1f}%) | Hour Closes GREEN: {green_prob:5.1f}%')

    # 2. Study 2: Price Grid Quarters (250 Pt Medium Quarters & 500/1000 Pt Major Quarters)
    # Check what happens when an IB Breakout is triggered within 25 points of a Major/Medium Quarter (Hesitation Zone)
    # Compute IB
    rth_1m = df[(df['time'] >= time(9, 30)) & (df['time'] < time(16, 0))]
    ib_1m = rth_1m[(rth_1m['time'] >= time(9, 30)) & (rth_1m['time'] < time(10, 0))]
    ib_daily = ib_1m.groupby('date').agg(
        ib_high=('high', 'max'),
        ib_low=('low', 'min'),
        ib_mid=('close', lambda x: (x.max() + x.min()) / 2.0)
    )

    q_price_trades = []
    for d, ib_row in ib_daily.iterrows():
        day_1m = df[df['date'] == d]
        if day_1m.empty: continue
        
        tw = day_1m[(day_1m['time'] >= time(10, 0)) & (day_1m['time'] <= time(15, 30))]
        if tw.empty: continue
        
        ib_high = ib_row['ib_high']
        ib_low = ib_row['ib_low']
        
        for idx, bar in tw.iterrows():
            if bar['close'] > ib_high:
                entry = bar['close']
                # Check distance to next 250 pt Quarter (e.g. 20000, 20250, 20500, 20750)
                dist_to_quarter = 250.0 - (entry % 250.0)
                in_hesitation_zone = dist_to_quarter <= 25.0 # Inside the 25 pt resistance wall
                
                fwd = day_1m.loc[idx:][1:]
                if not fwd.empty:
                    sl = entry - entry * 0.0012
                    tp1 = entry + entry * 0.0010
                    max_h = fwd['high'].max()
                    win = max_h >= tp1
                    q_price_trades.append({'date': d, 'dir': 'Long', 'in_hesitation': in_hesitation_zone, 'win': win, 'dist_to_q': dist_to_quarter})
                break
            elif bar['close'] < ib_low:
                entry = bar['close']
                dist_to_quarter = entry % 250.0 # Distance to lower 250 quarter
                in_hesitation_zone = dist_to_quarter <= 25.0
                
                fwd = day_1m.loc[idx:][1:]
                if not fwd.empty:
                    sl = entry + entry * 0.0012
                    tp1 = entry - entry * 0.0010
                    min_l = fwd['low'].min()
                    win = min_l <= tp1
                    q_price_trades.append({'date': d, 'dir': 'Short', 'in_hesitation': in_hesitation_zone, 'win': win, 'dist_to_q': dist_to_quarter})
                break

    df_qp = pd.DataFrame(q_price_trades)
    print('\n' + '-'*90)
    print('[2. PRICE GRID QUARTERS: 250-PT QUARTER HESITATION ZONE IMPACT]')
    print('-'*90)
    
    clean_trades = df_qp[~df_qp['in_hesitation']]
    hesitation_trades = df_qp[df_qp['in_hesitation']]
    
    print(f'Breakout with Clean Air (> 25 pts from 250-pt Quarter): {len(clean_trades):4d} trades | Win Rate: {(clean_trades["win"]).mean()*100:5.1f}%')
    print(f'Breakout Trapped inside 25-pt Quarter Hesitation Zone:  {len(hesitation_trades):4d} trades | Win Rate: {(hesitation_trades["win"]).mean()*100:5.1f}%')

if __name__ == '__main__':
    run_quarters_study()
