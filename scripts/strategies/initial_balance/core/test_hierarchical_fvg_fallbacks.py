"""
Empirical Study: Hierarchical 3-Tier FVG Anchor Engine
1. Tier 1: First 5m FVG post-10:00 AM (10:00 - 10:30)
2. Tier 2 Fallback: First 5m FVG in 09:00 - 10:00 AM window (09:00 Pre-Open / Opening Thrust)
3. Tier 3 Fallback: First 1m FVG at 09:30 - 09:35 AM (RTH Cash Open Catalyst)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

def run_hierarchical_fvg_study():
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

    # Resample 5m
    df_5m = df.resample('5min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    df_5m['time'] = df_5m.index.time
    df_5m['date'] = df_5m.index.date

    # Daily IB
    rth_1m = df[(df['time'] >= time(9, 30)) & (df['time'] < time(16, 0))]
    ib_1m = rth_1m[(rth_1m['time'] >= time(9, 30)) & (rth_1m['time'] < time(10, 0))]
    ib_daily = ib_1m.groupby('date').agg(
        ib_high=('high', 'max'),
        ib_low=('low', 'min'),
        ib_open=('open', 'first'),
        ib_close=('close', 'last')
    )
    ib_daily['ib_range'] = ib_daily['ib_high'] - ib_daily['ib_low']
    ib_daily['ib_mid'] = (ib_daily['ib_high'] + ib_daily['ib_low']) / 2.0

    print(f'[INFO] Extracted {len(ib_daily)} sessions. Analyzing 3-Tier FVG Coverage...')

    tier1_found = 0
    tier2_found = 0
    tier3_found = 0
    no_fvg_found = 0

    tier1_trades = []
    tier2_trades = []
    tier3_trades = []
    all_hierarchical_trades = []

    for d, ib_row in ib_daily.iterrows():
        day_1m = df[df['date'] == d]
        day_5m = df_5m[df_5m['date'] == d]
        if day_1m.empty or len(day_5m) < 12:
            continue

        ib_high = ib_row['ib_high']
        ib_low = ib_row['ib_low']
        ib_mid = ib_row['ib_mid']

        # -------------------------------------------------------------
        # Tier 1: First 5m FVG post-10:00 AM (10:00 - 10:30)
        # -------------------------------------------------------------
        t1_fvg = None
        w_10 = day_5m[(day_5m['time'] >= time(10, 0)) & (day_5m['time'] <= time(10, 30))]
        for i in range(2, len(w_10)):
            b0 = w_10.iloc[i-2]; b2 = w_10.iloc[i]
            if b2['low'] > b0['high'] + (b0['high'] * 0.0002):
                t1_fvg = {'tier': 'Tier 1 (10:00 5m)', 'type': 'Bull', 'top': b2['low'], 'bottom': b0['high'], 'time': b2['time'], 'bar_idx': w_10.index[i], 'inverted': False}
                break
            elif b2['high'] < b0['low'] - (b0['low'] * 0.0002):
                t1_fvg = {'tier': 'Tier 1 (10:00 5m)', 'type': 'Bear', 'top': b0['low'], 'bottom': b2['high'], 'time': b2['time'], 'bar_idx': w_10.index[i], 'inverted': False}
                break

        # -------------------------------------------------------------
        # Tier 2: First 5m FVG in 09:00 - 10:00 AM Window
        # -------------------------------------------------------------
        t2_fvg = None
        w_09 = day_5m[(day_5m['time'] >= time(9, 0)) & (day_5m['time'] < time(10, 0))]
        for i in range(2, len(w_09)):
            b0 = w_09.iloc[i-2]; b2 = w_09.iloc[i]
            if b2['low'] > b0['high'] + (b0['high'] * 0.0002):
                t2_fvg = {'tier': 'Tier 2 (09:00 5m)', 'type': 'Bull', 'top': b2['low'], 'bottom': b0['high'], 'time': b2['time'], 'bar_idx': w_09.index[i], 'inverted': False}
                break
            elif b2['high'] < b0['low'] - (b0['low'] * 0.0002):
                t2_fvg = {'tier': 'Tier 2 (09:00 5m)', 'type': 'Bear', 'top': b0['low'], 'bottom': b2['high'], 'time': b2['time'], 'bar_idx': w_09.index[i], 'inverted': False}
                break

        # -------------------------------------------------------------
        # Tier 3: First 1m FVG at 09:30 - 09:35 Open
        # -------------------------------------------------------------
        t3_fvg = None
        w_open1m = day_1m[(day_1m['time'] >= time(9, 30)) & (day_1m['time'] <= time(9, 35))]
        for i in range(2, len(w_open1m)):
            b0 = w_open1m.iloc[i-2]; b2 = w_open1m.iloc[i]
            if b2['low'] > b0['high'] + (b0['high'] * 0.0002):
                t3_fvg = {'tier': 'Tier 3 (09:30 1m)', 'type': 'Bull', 'top': b2['low'], 'bottom': b0['high'], 'time': b2['time'], 'bar_idx': w_open1m.index[i], 'inverted': False}
                break
            elif b2['high'] < b0['low'] - (b0['low'] * 0.0002):
                t3_fvg = {'tier': 'Tier 3 (09:30 1m)', 'type': 'Bear', 'top': b0['low'], 'bottom': b2['high'], 'time': b2['time'], 'bar_idx': w_open1m.index[i], 'inverted': False}
                break

        # Assign Active FVG Anchor based on Tier Hierarchy
        active_fvg = None
        if t1_fvg is not None:
            active_fvg = t1_fvg
            tier1_found += 1
        elif t2_fvg is not None:
            active_fvg = t2_fvg
            tier2_found += 1
        elif t3_fvg is not None:
            active_fvg = t3_fvg
            tier3_found += 1
        else:
            no_fvg_found += 1

        # Simulate Trade using Active FVG from 10:00 onwards
        if active_fvg is not None:
            trade_w = day_1m[(day_1m['time'] >= time(10, 0)) & (day_1m['time'] <= time(15, 30))]
            for idx, bar in trade_w.iterrows():
                # Bullish Respect
                if active_fvg['type'] == 'Bull' and not active_fvg['inverted']:
                    if bar['low'] <= active_fvg['top'] and bar['close'] >= active_fvg['bottom'] and bar['close'] > ib_mid:
                        entry = bar['close']
                        sl = active_fvg['bottom'] - (entry * 0.0003)
                        tp1 = entry + entry * 0.0010
                        tp2 = entry + entry * 0.0025
                        fwd = day_1m.loc[idx:][1:]
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                        res = {'date': d, 'tier': active_fvg['tier'], 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae}
                        all_hierarchical_trades.append(res)
                        if active_fvg['tier'].startswith('Tier 1'): tier1_trades.append(res)
                        elif active_fvg['tier'].startswith('Tier 2'): tier2_trades.append(res)
                        elif active_fvg['tier'].startswith('Tier 3'): tier3_trades.append(res)
                        break

                # Bearish Respect
                elif active_fvg['type'] == 'Bear' and not active_fvg['inverted']:
                    if bar['high'] >= active_fvg['bottom'] and bar['close'] <= active_fvg['top'] and bar['close'] < ib_mid:
                        entry = bar['close']
                        sl = active_fvg['top'] + (entry * 0.0003)
                        tp1 = entry - entry * 0.0010
                        tp2 = entry - entry * 0.0025
                        fwd = day_1m.loc[idx:][1:]
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                        res = {'date': d, 'tier': active_fvg['tier'], 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae}
                        all_hierarchical_trades.append(res)
                        if active_fvg['tier'].startswith('Tier 1'): tier1_trades.append(res)
                        elif active_fvg['tier'].startswith('Tier 2'): tier2_trades.append(res)
                        elif active_fvg['tier'].startswith('Tier 3'): tier3_trades.append(res)
                        break

                # Inversion Tracking
                if active_fvg['type'] == 'Bull' and bar['close'] < active_fvg['bottom']:
                    active_fvg['inverted'] = True
                elif active_fvg['type'] == 'Bear' and bar['close'] > active_fvg['top']:
                    active_fvg['inverted'] = True

    print('\n' + '='*90)
    print('HIERARCHICAL FVG ANCHOR COVERAGE (2019-2026, 1,958 SESSIONS)')
    print('='*90)
    total_sess = len(ib_daily)
    print(f'Tier 1 (10:00 5m FVG Found):    {tier1_found:4d} sessions ({tier1_found/total_sess*100:5.1f}%)')
    print(f'Tier 2 (09:00 5m FVG Fallback): {tier2_found:4d} sessions ({tier2_found/total_sess*100:5.1f}%)')
    print(f'Tier 3 (09:30 1m FVG Fallback): {tier3_found:4d} sessions ({tier3_found/total_sess*100:5.1f}%)')
    print(f'Total Covered with Valid Anchor: {tier1_found+tier2_found+tier3_found:4d} sessions ({(tier1_found+tier2_found+tier3_found)/total_sess*100:5.1f}%)')
    print(f'No Anchor Formed (Pure Chop):   {no_fvg_found:4d} sessions ({no_fvg_found/total_sess*100:5.1f}%)')

    def print_tier_metrics(name, t_list):
        if not t_list: return
        df_t = pd.DataFrame(t_list)
        wins = df_t[df_t['win']]
        losses = df_t[~df_t['win']]
        gw = wins['pnl_bps'].sum()
        gl = abs(losses['pnl_bps'].sum())
        pf = gw / gl if gl > 0 else 99.0
        wr = len(wins) / len(df_t) * 100
        net = df_t['pnl_bps'].sum()
        cum = df_t['pnl_bps'].cumsum()
        max_dd = abs((cum - cum.cummax()).min()) if not cum.empty else 0.0
        print(f'\n[{name}]')
        print(f'  Trades Taken:     {len(df_t):4d}')
        print(f'  Win Rate:         {wr:5.1f}%')
        print(f'  Profit Factor:    {pf:5.2f}')
        print(f'  Net Return (bps): {net:+8.1f} bps')
        print(f'  Max Drawdown:     {max_dd:6.1f} bps')

    print_tier_metrics('TIER 1 (10:00 5m FVG Primary Anchor)', tier1_trades)
    print_tier_metrics('TIER 2 (09:00 5m FVG Fallback)', tier2_trades)
    print_tier_metrics('TIER 3 (09:30 1m FVG Fallback)', tier3_trades)
    print_tier_metrics('COMBINED HIERARCHICAL ENGINE (All 3 Tiers)', all_hierarchical_trades)

def eval_pack(fwd_bars, entry, stop, tp1, tp2, direction):
    if fwd_bars.empty:
        return 0.0, False, 0.0, 0.0
    tp1_hit = False
    tp2_hit = False
    stopped = False
    curr_stop = stop
    mfe_pts = 0.0
    mae_pts = 0.0
    
    for _, bar in fwd_bars.iterrows():
        if direction == 1:
            mfe_pts = max(mfe_pts, bar['high'] - entry)
            mae_pts = max(mae_pts, entry - bar['low'])
            if bar['low'] <= curr_stop:
                stopped = True; break
            if not tp1_hit and bar['high'] >= tp1:
                tp1_hit = True; curr_stop = entry
            if tp1_hit and bar['high'] >= tp2:
                tp2_hit = True; break
        else:
            mfe_pts = max(mfe_pts, entry - bar['low'])
            mae_pts = max(mae_pts, bar['high'] - entry)
            if bar['high'] >= curr_stop:
                stopped = True; break
            if not tp1_hit and bar['low'] <= tp1:
                tp1_hit = True; curr_stop = entry
            if tp1_hit and bar['low'] <= tp2:
                tp2_hit = True; break
                
    entry_bps = entry * 0.0001
    mfe_bps = mfe_pts / entry_bps
    mae_bps = mae_pts / entry_bps
    
    if stopped and not tp1_hit:
        return -(abs(entry - stop) / entry_bps), False, mfe_bps, mae_bps
    elif stopped and tp1_hit:
        return (abs(tp1 - entry) / entry_bps) / 2.0, True, mfe_bps, mae_bps
    elif tp2_hit:
        return ((abs(tp1 - entry) + abs(tp2 - entry)) / 2.0) / entry_bps, True, mfe_bps, mae_bps
    else:
        last_p = fwd_bars.iloc[-1]['close']
        pnl = ((last_p - entry) * direction) / entry_bps
        return pnl, pnl > 0, mfe_bps, mae_bps

if __name__ == '__main__':
    run_hierarchical_fvg_study()
