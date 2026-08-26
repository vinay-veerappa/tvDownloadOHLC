"""
Hierarchical 6-Level Forensic Failure Analysis Engine for Initial Balance Suite
Analyzes 7.5 years of trade executions across NQ1 and ES1.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

def analyze_failures(ticker='NQ1', start_date='2019-01-01', end_date='2026-08-05'):
    data_path = Path(f'data/{ticker}_1m.parquet')
    if not data_path.exists():
        print(f'[ERROR] {data_path} not found')
        return

    print(f'[INFO] Loading {ticker} data...')
    df = pd.read_parquet(data_path)
    df = df.sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')

    df['time'] = df.index.time
    df['date'] = df.index.date
    df['day_name'] = df.index.day_name()
    df['month'] = df.index.month

    # Filter study period
    df_study = df[(df.index >= start_date) & (df.index <= end_date)].copy()

    # 1. Daily IB Metrics
    rth_bars = df_study[(df_study['time'] >= time(9, 30)) & (df_study['time'] < time(16, 0))].copy()
    ib_bars = rth_bars[(rth_bars['time'] >= time(9, 30)) & (rth_bars['time'] < time(10, 0))]
    
    ib_daily = ib_bars.groupby('date').agg(
        ib_high=('high', 'max'),
        ib_low=('low', 'min'),
        ib_open=('open', 'first'),
        ib_close=('close', 'last')
    )
    ib_daily['ib_range'] = ib_daily['ib_high'] - ib_daily['ib_low']
    ib_daily['ib_mid'] = (ib_daily['ib_high'] + ib_daily['ib_low']) / 2.0
    ib_daily['ib_range_bps'] = (ib_daily['ib_range'] / ib_daily['ib_mid']) * 10000.0

    daily_bars = df_study.groupby('date').agg(
        d_high=('high', 'max'),
        d_low=('low', 'min'),
        d_close=('close', 'last'),
        d_open=('open', 'first')
    )
    daily_bars['tr'] = np.maximum(
        daily_bars['d_high'] - daily_bars['d_low'],
        np.maximum(
            (daily_bars['d_high'] - daily_bars['d_close'].shift(1)).abs(),
            (daily_bars['d_low'] - daily_bars['d_close'].shift(1)).abs()
        )
    )
    daily_bars['atr14'] = daily_bars['tr'].rolling(14).mean()
    daily_bars['atr_bps'] = (daily_bars['atr14'] / daily_bars['d_close']) * 10000.0
    ib_daily = ib_daily.join(daily_bars[['atr14', 'atr_bps']])
    ib_daily['ib_atr_ratio'] = ib_daily['ib_range'] / ib_daily['atr14']

    # 2. Simulate All Trades and Track Failures with Rich Forensic Metadata
    trades = []
    
    for d, ib_row in ib_daily.iterrows():
        if pd.isna(ib_row['ib_range']) or ib_row['ib_range'] <= 0:
            continue
            
        day_data = df_study[df_study['date'] == d]
        if day_data.empty:
            continue
            
        trade_window = day_data[(day_data['time'] >= time(10, 0)) & (day_data['time'] <= time(15, 30))]
        if trade_window.empty:
            continue
            
        ib_high = ib_row['ib_high']
        ib_low = ib_row['ib_low']
        ib_mid = ib_row['ib_mid']
        ib_bps = ib_row['ib_range_bps']
        atr_ratio = ib_row['ib_atr_ratio']
        day_of_week = day_data.index[0].day_name()
        month = day_data.index[0].month
        
        # Check Breakout Trades
        long_entered = False
        short_entered = False
        
        for idx, bar in trade_window.iterrows():
            entry_t = bar['time']
            
            # Play 1 Breakout
            if not long_entered and bar['close'] > ib_high:
                entry_p = bar['close']
                sl_p = entry_p - min(entry_p - ib_low, entry_p * 0.0012)
                tp1_p = entry_p + entry_p * 0.0010
                tp2_p = entry_p + entry_p * 0.0025
                
                fwd = day_data.loc[idx:][1:]
                pnl, win, mfe, mae, duration, exit_reason, wick_sweep = eval_forensic(fwd, entry_p, sl_p, tp1_p, tp2_p, 1)
                trades.append({
                    'date': d, 'play': 'Play 1 Breakout', 'time': entry_t, 'dir': 'Long',
                    'day_of_week': day_of_week, 'month': month,
                    'ib_range_bps': ib_bps, 'ib_atr_ratio': atr_ratio,
                    'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae,
                    'duration_min': duration, 'exit_reason': exit_reason, 'wick_sweep': wick_sweep
                })
                long_entered = True
                break
                
            elif not short_entered and bar['close'] < ib_low:
                entry_p = bar['close']
                sl_p = entry_p + min(ib_high - entry_p, entry_p * 0.0012)
                tp1_p = entry_p - entry_p * 0.0010
                tp2_p = entry_p - entry_p * 0.0025
                
                fwd = day_data.loc[idx:][1:]
                pnl, win, mfe, mae, duration, exit_reason, wick_sweep = eval_forensic(fwd, entry_p, sl_p, tp1_p, tp2_p, -1)
                trades.append({
                    'date': d, 'play': 'Play 1 Breakout', 'time': entry_t, 'dir': 'Short',
                    'day_of_week': day_of_week, 'month': month,
                    'ib_range_bps': ib_bps, 'ib_atr_ratio': atr_ratio,
                    'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae,
                    'duration_min': duration, 'exit_reason': exit_reason, 'wick_sweep': wick_sweep
                })
                short_entered = True
                break

    df_trades = pd.DataFrame(trades)
    print(f'[INFO] Total Trades Simulated: {len(df_trades):,d}')
    losers = df_trades[df_trades['pnl_bps'] < 0].copy()
    winners = df_trades[df_trades['pnl_bps'] > 0].copy()
    print(f'[INFO] Winners: {len(winners)} ({len(winners)/len(df_trades)*100:.1f}%), Losers: {len(losers)} ({len(losers)/len(df_trades)*100:.1f}%)')

    return df_trades, losers

def eval_forensic(fwd_bars, entry, stop, tp1, tp2, direction):
    if fwd_bars.empty:
        return 0.0, False, 0.0, 0.0, 0, 'No_Data', False
        
    tp1_hit = False
    tp2_hit = False
    stopped = False
    wick_sweep = False
    curr_stop = stop
    
    mfe_pts = 0.0
    mae_pts = 0.0
    duration = 0
    exit_reason = 'EOD'
    
    for i, (_, bar) in enumerate(fwd_bars.iterrows()):
        duration = i + 1
        if direction == 1:
            mfe_pts = max(mfe_pts, bar['high'] - entry)
            mae_pts = max(mae_pts, entry - bar['low'])
            
            if bar['low'] <= curr_stop:
                stopped = True
                wick_sweep = (bar['close'] > curr_stop) # Wick penetrated stop but candle closed back above
                exit_reason = 'Stop_Loss'
                break
            if not tp1_hit and bar['high'] >= tp1:
                tp1_hit = True
                curr_stop = entry # Move to Breakeven
            if tp1_hit and bar['high'] >= tp2:
                tp2_hit = True
                exit_reason = 'Target_2'
                break
        else:
            mfe_pts = max(mfe_pts, entry - bar['low'])
            mae_pts = max(mae_pts, bar['high'] - entry)
            
            if bar['high'] >= curr_stop:
                stopped = True
                wick_sweep = (bar['close'] < curr_stop)
                exit_reason = 'Stop_Loss'
                break
            if not tp1_hit and bar['low'] <= tp1:
                tp1_hit = True
                curr_stop = entry
            if tp1_hit and bar['low'] <= tp2:
                tp2_hit = True
                exit_reason = 'Target_2'
                break
                
    entry_bps = entry * 0.0001
    mfe_bps = mfe_pts / entry_bps
    mae_bps = mae_pts / entry_bps
    
    if stopped and not tp1_hit:
        pnl = -(abs(entry - stop) / entry_bps)
        return pnl, False, mfe_bps, mae_bps, duration, exit_reason, wick_sweep
    elif stopped and tp1_hit:
        pnl = (abs(tp1 - entry) / entry_bps) / 2.0
        return pnl, True, mfe_bps, mae_bps, duration, 'TP1_Then_BE', wick_sweep
    elif tp2_hit:
        pnl = ((abs(tp1 - entry) + abs(tp2 - entry)) / 2.0) / entry_bps
        return pnl, True, mfe_bps, mae_bps, duration, exit_reason, wick_sweep
    else:
        last_p = fwd_bars.iloc[-1]['close']
        pnl = ((last_p - entry) * direction) / entry_bps
        return pnl, pnl > 0, mfe_bps, mae_bps, duration, exit_reason, wick_sweep

if __name__ == '__main__':
    df_trades, losers = analyze_failures('NQ1')
    
    print('\n' + '='*80)
    print('LEVEL 1: MACRO & REGIME-LEVEL FAILURE ANALYSIS')
    print('='*80)
    print('1.1 Failures by Day of Week:')
    print(losers['day_of_week'].value_counts(normalize=True)*100)
    print('\n1.2 Failures by Month of Year:')
    print(losers['month'].value_counts(normalize=True).sort_index()*100)
    print('\n1.3 Failures by ATR Regime (IB / ATR Ratio):')
    losers['atr_regime'] = pd.cut(losers['ib_atr_ratio'], bins=[0, 0.35, 0.50, 0.75, 1.5, 99], labels=['Severe Compress (<0.35)', 'Moderate Compress (0.35-0.50)', 'Normal (0.50-0.75)', 'Expanded (0.75-1.5)', 'Extreme (>1.5)'])
    print(losers['atr_regime'].value_counts(normalize=True)*100)

    print('\n' + '='*80)
    print('LEVEL 2: STRUCTURAL & SESSION GEOMETRY FAILURE ANALYSIS')
    print('='*80)
    print('2.1 Failures by IB Range Size (bps):')
    losers['ib_size_bin'] = pd.cut(losers['ib_range_bps'], bins=[0, 40, 70, 100, 150, 999], labels=['Tiny (<40 bps)', 'Normal (40-70 bps)', 'Wide (70-100 bps)', 'Very Wide (100-150 bps)', 'Huge (>150 bps)'])
    print(losers['ib_size_bin'].value_counts(normalize=True)*100)
    print('\n2.2 Failures by Direction (Asymmetry):')
    print(losers['dir'].value_counts(normalize=True)*100)

    print('\n' + '='*80)
    print('LEVEL 3: TEMPORAL / INTRADAY MICRO-WINDOW FAILURE ANALYSIS')
    print('='*80)
    losers['time_window'] = losers['time'].apply(lambda t: 
        '10:00-10:15 (Immediate Break)' if t < time(10, 15) else
        '10:15-10:30 (London Fix / Macro)' if t < time(10, 30) else
        '10:30-11:30 (Morning Expansion)' if t < time(11, 30) else
        '11:30-13:30 (Lunch Doldrums)' if t < time(13, 30) else
        '13:30-15:00 (PM Session)' if t < time(15, 0) else '15:00-16:00 (Power Hour)'
    )
    print(losers['time_window'].value_counts(normalize=True)*100)

    print('\n' + '='*80)
    print('LEVEL 4: SIGNAL & PATTERN FORMATION QUALITY FAILURE ANALYSIS')
    print('='*80)
    print('4.1 Immediate Reversal / Flash Stopouts (Duration <= 5 mins):')
    flash = (losers['duration_min'] <= 5).mean() * 100
    print(f'Immediate Flash Reversals (<= 5 min): {flash:.1f}%')
    print('\n4.2 Slow Bleed Grindouts (Duration > 60 mins):')
    slow = (losers['duration_min'] > 60).mean() * 100
    print(f'Slow Bleed Grindouts (> 60 min): {slow:.1f}%')

    print('\n' + '='*80)
    print('LEVEL 5: TRADE MANAGEMENT & EXECUTION BRACKET DYNAMICS')
    print('='*80)
    print('5.1 Unrealized Favorable Excursion on Losers (Round-Trip Traps):')
    print(f'MFE >= 3.0 bps before dying:  {(losers["mfe_bps"] >= 3.0).mean()*100:.1f}%')
    print(f'MFE >= 5.0 bps before dying:  {(losers["mfe_bps"] >= 5.0).mean()*100:.1f}%')
    print(f'MFE >= 8.0 bps before dying:  {(losers["mfe_bps"] >= 8.0).mean()*100:.1f}%')
    print(f'MFE >= 10.0 bps before dying: {(losers["mfe_bps"] >= 10.0).mean()*100:.1f}%')

    print('\n' + '='*80)
    print('LEVEL 6: ORDERFLOW, DELTA & TICK-LEVEL MICROSTRUCTURE')
    print('='*80)
    print(f'Wick Sweep Stopouts (Intrabar breach, closed back above stop): {losers["wick_sweep"].mean()*100:.1f}%')
    print(f'Full Candle Body Breaches (Clean liquidation): {(~losers["wick_sweep"]).mean()*100:.1f}%')
