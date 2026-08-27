"""
Comprehensive Empirical Analysis: Size of Initial Balance (IB) vs. Play Performance
Analyzes Play 1 (Breakout), Play 2 (Retest), and Play 3 (Fade) across IB Size Quintiles & ATR Ratios.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time

def run_ib_size_study():
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
    df = df[df.index >= '2019-01-01'].copy()

    # Compute Daily IB (09:30 - 10:00)
    rth = df[(df['time'] >= time(9, 30)) & (df['time'] < time(16, 0))]
    ib_bars = rth[(rth['time'] >= time(9, 30)) & (rth['time'] < time(10, 0))]

    ib_daily = ib_bars.groupby('date').agg(
        ib_high=('high', 'max'),
        ib_low=('low', 'min'),
        ib_open=('open', 'first'),
        ib_close=('close', 'last')
    )
    ib_daily['ib_range'] = ib_daily['ib_high'] - ib_daily['ib_low']
    ib_daily['ib_mid'] = (ib_daily['ib_high'] + ib_daily['ib_low']) / 2.0
    ib_daily['ib_bps'] = (ib_daily['ib_range'] / ib_daily['ib_mid']) * 10000.0

    daily = df.groupby('date').agg(d_high=('high', 'max'), d_low=('low', 'min'), d_close=('close', 'last'))
    daily['tr'] = np.maximum(daily['d_high'] - daily['d_low'], np.maximum((daily['d_high'] - daily['d_close'].shift(1)).abs(), (daily['d_low'] - daily['d_close'].shift(1)).abs()))
    daily['atr14'] = daily['tr'].rolling(14).mean()
    ib_daily = ib_daily.join(daily[['atr14']])
    ib_daily['ib_atr_ratio'] = ib_daily['ib_range'] / ib_daily['atr14']

    ib_clean = ib_daily.dropna().copy()
    ib_clean['size_bin'] = pd.qcut(ib_clean['ib_bps'], q=5, labels=['Q1: Tiny (<45 bps)', 'Q2: Small (45-60 bps)', 'Q3: Normal (60-80 bps)', 'Q4: Large (80-115 bps)', 'Q5: Huge (>115 bps)'])
    ib_clean['atr_bin'] = pd.cut(ib_clean['ib_atr_ratio'], bins=[0, 0.35, 0.50, 0.75, 1.0, 99], labels=['Severe Compress (<0.35x)', 'Moderate Compress (0.35-0.50x)', 'Normal (0.50-0.75x)', 'Expanded (0.75-1.0x)', 'Extreme (>1.0x)'])

    p1_list = []
    p2_list = []
    p3_list = []

    for d, row in ib_clean.iterrows():
        day_data = df[df['date'] == d]
        if day_data.empty: continue
        
        tw = day_data[(day_data['time'] >= time(10, 0)) & (day_data['time'] <= time(15, 30))]
        if tw.empty: continue
        
        ib_high = row['ib_high']
        ib_low = row['ib_low']
        ib_mid = row['ib_mid']
        bps_bin = row['size_bin']
        atr_bin = row['atr_bin']
        ib_bps = row['ib_bps']
        
        # 1. Play 1 Breakout
        p1_done = False
        for idx, bar in tw.iterrows():
            if not p1_done and bar['close'] > ib_high:
                fwd = day_data.loc[idx:][1:]
                if not fwd.empty:
                    entry = bar['close']
                    sl = entry - min(entry - ib_low, entry * 0.0012)
                    tp1 = entry + entry * 0.0010
                    max_high = fwd['high'].max()
                    mfe_bps = ((max_high - entry)/entry)*10000.0
                    win = max_high >= tp1
                    pnl = tp1 - entry if win else -(entry - sl)
                    pnl_bps = (pnl / entry) * 10000.0
                    p1_list.append({'bps_bin': bps_bin, 'atr_bin': atr_bin, 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'ib_bps': ib_bps})
                    p1_done = True
                    break
            elif not p1_done and bar['close'] < ib_low:
                fwd = day_data.loc[idx:][1:]
                if not fwd.empty:
                    entry = bar['close']
                    sl = entry + min(ib_high - entry, entry * 0.0012)
                    tp1 = entry - entry * 0.0010
                    min_low = fwd['low'].min()
                    mfe_bps = ((entry - min_low)/entry)*10000.0
                    win = min_low <= tp1
                    pnl = entry - tp1 if win else -(sl - entry)
                    pnl_bps = (pnl / entry) * 10000.0
                    p1_list.append({'bps_bin': bps_bin, 'atr_bin': atr_bin, 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'ib_bps': ib_bps})
                    p1_done = True
                    break

        # 2. Play 2 Retest (Fib 38.2%)
        p2_done = False
        f_dir = 0
        b_ext = 0.0
        for idx, bar in tw.iterrows():
            if f_dir == 0:
                if bar['close'] > ib_high:
                    f_dir = 1; b_ext = bar['high']
                elif bar['close'] < ib_low:
                    f_dir = -1; b_ext = bar['low']
            else:
                if f_dir == 1:
                    b_ext = max(b_ext, bar['high'])
                    wave = ((b_ext - ib_high)/ib_high)*10000.0
                    if wave >= 5.0 and not p2_done:
                        fib = b_ext - 0.382 * (b_ext - ib_high)
                        if bar['low'] <= fib and bar['close'] >= fib:
                            fwd = day_data.loc[idx:][1:]
                            if not fwd.empty:
                                entry = bar['close']
                                sl = entry - min(entry - ib_low, entry * 0.0012)
                                tp1 = entry + entry * 0.0010
                                max_high = fwd['high'].max()
                                mfe_bps = ((max_high - entry)/entry)*10000.0
                                win = max_high >= tp1
                                pnl = tp1 - entry if win else -(entry - sl)
                                pnl_bps = (pnl / entry) * 10000.0
                                p2_list.append({'bps_bin': bps_bin, 'atr_bin': atr_bin, 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'ib_bps': ib_bps})
                                p2_done = True
                                break
                elif f_dir == -1:
                    b_ext = min(b_ext, bar['low'])
                    wave = ((ib_low - b_ext)/ib_low)*10000.0
                    if wave >= 5.0 and not p2_done:
                        fib = b_ext + 0.382 * (ib_low - b_ext)
                        if bar['high'] >= fib and bar['close'] <= fib:
                            fwd = day_data.loc[idx:][1:]
                            if not fwd.empty:
                                entry = bar['close']
                                sl = entry + min(ib_high - entry, entry * 0.0012)
                                tp1 = entry - entry * 0.0010
                                min_low = fwd['low'].min()
                                mfe_bps = ((entry - min_low)/entry)*10000.0
                                win = min_low <= tp1
                                pnl = entry - tp1 if win else -(sl - entry)
                                pnl_bps = (pnl / entry) * 10000.0
                                p2_list.append({'bps_bin': bps_bin, 'atr_bin': atr_bin, 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'ib_bps': ib_bps})
                                p2_done = True
                                break

        # 3. Play 3 Sweep Fade (Midday/PM 11:30 - 15:30)
        p3_done = False
        tw_p3 = day_data[(day_data['time'] >= time(11, 30)) & (day_data['time'] <= time(15, 30))]
        for idx, bar in tw_p3.iterrows():
            if not p3_done and bar['high'] > ib_high and bar['close'] < ib_high:
                fwd = day_data.loc[idx:][1:]
                if not fwd.empty:
                    entry = bar['close']
                    sl = bar['high'] + entry * 0.0003
                    tp1 = ib_mid
                    min_low = fwd['low'].min()
                    win = min_low <= tp1
                    pnl = entry - tp1 if win else -(sl - entry)
                    pnl_bps = (pnl / entry) * 10000.0
                    mfe_bps = ((entry - min_low)/entry)*10000.0
                    p3_list.append({'bps_bin': bps_bin, 'atr_bin': atr_bin, 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'ib_bps': ib_bps})
                    p3_done = True
                    break
            elif not p3_done and bar['low'] < ib_low and bar['close'] > ib_low:
                fwd = day_data.loc[idx:][1:]
                if not fwd.empty:
                    entry = bar['close']
                    sl = bar['low'] - entry * 0.0003
                    tp1 = ib_mid
                    max_high = fwd['high'].max()
                    win = max_high >= tp1
                    pnl = tp1 - entry if win else -(entry - sl)
                    pnl_bps = (pnl / entry) * 10000.0
                    mfe_bps = ((max_high - entry)/entry)*10000.0
                    p3_list.append({'bps_bin': bps_bin, 'atr_bin': atr_bin, 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'ib_bps': ib_bps})
                    p3_done = True
                    break

    df_p1 = pd.DataFrame(p1_list)
    df_p2 = pd.DataFrame(p2_list)
    df_p3 = pd.DataFrame(p3_list)

    def print_matrix(name, df_res, group_col):
        print('\n' + '='*95)
        print(f'{name} BY {group_col.upper()}')
        print('='*95)
        categories = df_res[group_col].cat.categories if hasattr(df_res[group_col], 'cat') else df_res[group_col].unique()
        for b in categories:
            sub = df_res[df_res[group_col] == b]
            if sub.empty: continue
            wins = sub[sub['win']]
            losses = sub[~sub['win']]
            gw = wins['pnl_bps'].sum()
            gl = abs(losses['pnl_bps'].sum())
            pf = gw / gl if gl > 0 else 0
            wr = len(wins)/len(sub)*100
            net = sub['pnl_bps'].sum()
            mfe = sub['mfe_bps'].mean()
            print(f'{str(b):32s} | Trades: {len(sub):4d} | WR: {wr:5.1f}% | PF: {pf:5.2f} | Net: {net:+8.1f} bps | Avg MFE: {mfe:5.1f} bps')

    print_matrix('PLAY 1 (BREAKOUT)', df_p1, 'bps_bin')
    print_matrix('PLAY 1 (BREAKOUT)', df_p1, 'atr_bin')
    print_matrix('PLAY 2 (FIB RETEST)', df_p2, 'bps_bin')
    print_matrix('PLAY 2 (FIB RETEST)', df_p2, 'atr_bin')
    print_matrix('PLAY 3 (SWEEP FADE)', df_p3, 'bps_bin')
    print_matrix('PLAY 3 (SWEEP FADE)', df_p3, 'atr_bin')

if __name__ == '__main__':
    run_ib_size_study()
