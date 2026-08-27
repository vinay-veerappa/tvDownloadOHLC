"""
Comprehensive Confluence Verification Study across 7.5 Years (2019-2026) NQ1:
1. IB Midpoint Acceptance & Gravitational Bias
2. 10:00 AM Hourly Candle Sweep of 09:00 AM Liquidity
3. First 5m FVG Formed Post-10:00 AM (Directional Anchor vs. Inversion)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

def run_confluence_study():
    data_path = Path('data/NQ1_1m.parquet')
    if not data_path.exists():
        print('Data not found')
        return

    print('[INFO] Loading NQ1 1m data (2019-2026)...')
    df = pd.read_parquet(data_path)
    df = df.sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')

    df['time'] = df.index.time
    df['date'] = df.index.date
    df = df[df.index >= '2019-01-01'].copy()

    # 1. Compute Daily IB (09:30 - 10:00) & 09:00 AM Hourly Candle (09:00 - 10:00)
    rth = df[(df['time'] >= time(9, 0)) & (df['time'] < time(16, 0))]

    # 09:00 - 10:00 Hourly Candle
    h09_bars = rth[(rth['time'] >= time(9, 0)) & (rth['time'] < time(10, 0))]
    h09_daily = h09_bars.groupby('date').agg(
        h09_high=('high', 'max'),
        h09_low=('low', 'min'),
        h09_open=('open', 'first'),
        h09_close=('close', 'last')
    )

    # 09:30 - 10:00 IB
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

    # 10:00 - 11:00 Hourly Candle
    h10_bars = rth[(rth['time'] >= time(10, 0)) & (rth['time'] < time(11, 0))]
    h10_daily = h10_bars.groupby('date').agg(
        h10_high=('high', 'max'),
        h10_low=('low', 'min'),
        h10_open=('open', 'first'),
        h10_close=('close', 'last')
    )

    # Combine
    daily_matrix = ib_daily.join(h09_daily).join(h10_daily).dropna()

    # 2. Study 1: 10:00 AM Candle Sweep of 09:00 AM High/Low
    daily_matrix['swept_09_high'] = daily_matrix['h10_high'] > daily_matrix['h09_high']
    daily_matrix['swept_09_low'] = daily_matrix['h10_low'] < daily_matrix['h09_low']
    daily_matrix['h10_close_above_mid'] = daily_matrix['h10_close'] > daily_matrix['ib_mid']
    daily_matrix['h10_close_below_mid'] = daily_matrix['h10_close'] < daily_matrix['ib_mid']
    daily_matrix['day_closed_green'] = False # Will compute from 16:00 close
    
    # Get 16:00 Close
    d_close = rth.groupby('date')['close'].last()
    daily_matrix = daily_matrix.join(d_close.rename('session_close'))
    daily_matrix['net_move_bps'] = ((daily_matrix['session_close'] - daily_matrix['ib_mid']) / daily_matrix['ib_mid']) * 10000.0
    daily_matrix['day_green'] = daily_matrix['session_close'] > daily_matrix['ib_open']

    print('='*90)
    print('EMPIRICAL CONFLUENCE STUDY (2019-2026, 1,932 SESSIONS)')
    print('='*90)

    # -------------------------------------------------------------
    # CONFLUENCE 1: IB MIDPOINT ACCEPTANCE (10:00 - 10:30)
    # -------------------------------------------------------------
    print('\n[CONFLUENCE 1: IB MIDPOINT GRAVITATIONAL BIAS]')
    above_mid = daily_matrix[daily_matrix['h10_close_above_mid']]
    below_mid = daily_matrix[daily_matrix['h10_close_below_mid']]
    
    print(f'10:00 Hour Closed ABOVE IB Mid: {len(above_mid)} sessions ({len(above_mid)/len(daily_matrix)*100:.1f}%)')
    print(f'  --> Probability Session Closes Green: {(above_mid["day_green"]).mean()*100:.1f}%')
    print(f'  --> Average Net Session Move: {above_mid["net_move_bps"].mean():+.1f} bps')
    
    print(f'\n10:00 Hour Closed BELOW IB Mid: {len(below_mid)} sessions ({len(below_mid)/len(daily_matrix)*100:.1f}%)')
    print(f'  --> Probability Session Closes Red: {(~below_mid["day_green"]).mean()*100:.1f}%')
    print(f'  --> Average Net Session Move: {below_mid["net_move_bps"].mean():+.1f} bps')

    # -------------------------------------------------------------
    # CONFLUENCE 2: 10:00 AM HOURLY CANDLE SWEEPS 09:00 AM LIQUIDITY
    # -------------------------------------------------------------
    print('\n' + '-'*90)
    print('[CONFLUENCE 2: 10:00 AM HOURLY CANDLE LIQUIDITY SWEEP OF 09:00 AM]')
    print('-'*90)
    sweep_high_only = daily_matrix[daily_matrix['swept_09_high'] & ~daily_matrix['swept_09_low']]
    sweep_low_only = daily_matrix[daily_matrix['swept_09_low'] & ~daily_matrix['swept_09_high']]
    sweep_both = daily_matrix[daily_matrix['swept_09_high'] & daily_matrix['swept_09_low']]
    sweep_neither = daily_matrix[~daily_matrix['swept_09_high'] & ~daily_matrix['swept_09_low']]

    print(f'1. Swept 09:00 High ONLY: {len(sweep_high_only)} sessions ({len(sweep_high_only)/len(daily_matrix)*100:.1f}%)')
    print(f'   --> Session Closes Green (Continuation): {(sweep_high_only["day_green"]).mean()*100:.1f}%')
    print(f'   --> Session Closes Red (Judas Reversal): {(~sweep_high_only["day_green"]).mean()*100:.1f}%')
    print(f'   --> Average Net Move: {sweep_high_only["net_move_bps"].mean():+.1f} bps')

    print(f'\n2. Swept 09:00 Low ONLY: {len(sweep_low_only)} sessions ({len(sweep_low_only)/len(daily_matrix)*100:.1f}%)')
    print(f'   --> Session Closes Red (Continuation): {(~sweep_low_only["day_green"]).mean()*100:.1f}%')
    print(f'   --> Session Closes Green (Judas Reversal): {(sweep_low_only["day_green"]).mean()*100:.1f}%')
    print(f'   --> Average Net Move: {sweep_low_only["net_move_bps"].mean():+.1f} bps')

    print(f'\n3. Double Sweep (Both 09:00 High & Low Swept - R1 Whipsaw): {len(sweep_both)} sessions ({len(sweep_both)/len(daily_matrix)*100:.1f}%)')
    print(f'4. Inside Hour (Neither Swept - Consolidation): {len(sweep_neither)} sessions ({len(sweep_neither)/len(daily_matrix)*100:.1f}%)')

    # -------------------------------------------------------------
    # CONFLUENCE 3: FIRST 5M FVG FORMED POST-10:00 AM (10:00 - 10:30)
    # -------------------------------------------------------------
    print('\n' + '-'*90)
    print('[CONFLUENCE 3: FIRST 5-MINUTE FVG FORMED POST-10:00 AM]')
    print('-'*90)
    
    # Resample to 5m bars for FVG detection
    df_5m = df.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    df_5m['time'] = df_5m.index.time
    df_5m['date'] = df_5m.index.date

    fvg_results = []
    for d, ib_row in ib_daily.iterrows():
        day_5m = df_5m[df_5m['date'] == d]
        if len(day_5m) < 10: continue
        
        # Look for the first 5m FVG created between 10:00 and 10:30
        window_5m = day_5m[(day_5m['time'] >= time(10, 0)) & (day_5m['time'] <= time(10, 30))]
        if len(window_5m) < 3: continue
        
        # 3-bar FVG detection (b0, b1, b2)
        found_fvg = False
        fvg_type = None # 'Bullish' or 'Bearish'
        fvg_top = 0.0
        fvg_bottom = 0.0
        fvg_bar_idx = None
        
        for i in range(2, len(window_5m)):
            b0_high = window_5m.iloc[i-2]['high']
            b0_low = window_5m.iloc[i-2]['low']
            b2_high = window_5m.iloc[i]['high']
            b2_low = window_5m.iloc[i]['low']
            
            # Bullish FVG: b2_low > b0_high
            if b2_low > b0_high + (b0_high * 0.0002):
                fvg_type = 'Bullish'
                fvg_top = b2_low
                fvg_bottom = b0_high
                fvg_bar_idx = window_5m.index[i]
                found_fvg = True
                break
            # Bearish FVG: b2_high < b0_low
            elif b2_high < b0_low - (b0_low * 0.0002):
                fvg_type = 'Bearish'
                fvg_top = b0_low
                fvg_bottom = b2_high
                fvg_bar_idx = window_5m.index[i]
                found_fvg = True
                break
                
        if found_fvg:
            # Check what happens post-FVG until session close
            post_fvg = day_5m.loc[fvg_bar_idx:][1:]
            if post_fvg.empty: continue
            
            # Did price RESPECT the FVG or INVERT (IFVG)?
            if fvg_type == 'Bullish':
                # Respected: low held above fvg_bottom
                inverted = (post_fvg['close'] < fvg_bottom).any()
                session_gain = ((post_fvg.iloc[-1]['close'] - fvg_top) / fvg_top) * 10000.0
                fvg_results.append({'date': d, 'type': 'Bullish', 'inverted': inverted, 'gain_bps': session_gain, 'day_green': session_gain > 0})
            elif fvg_type == 'Bearish':
                inverted = (post_fvg['close'] > fvg_top).any()
                session_gain = ((fvg_bottom - post_fvg.iloc[-1]['close']) / fvg_bottom) * 10000.0
                fvg_results.append({'date': d, 'type': 'Bearish', 'inverted': inverted, 'gain_bps': session_gain, 'day_green': session_gain > 0})

    df_fvg = pd.DataFrame(fvg_results)
    print(f'Total Post-10:00 AM 5m FVGs Detected: {len(df_fvg)} across {len(ib_daily)} days ({len(df_fvg)/len(ib_daily)*100:.1f}% frequency)')
    
    bull_fvg = df_fvg[df_fvg['type'] == 'Bullish']
    bear_fvg = df_fvg[df_fvg['type'] == 'Bearish']
    
    print(f'\n1. BULLISH First 10:00 AM FVG ({len(bull_fvg)} cases):')
    respected_bull = bull_fvg[~bull_fvg['inverted']]
    inverted_bull = bull_fvg[bull_fvg['inverted']]
    print(f'   --> Respected (Holds above FVG): {len(respected_bull)} ({len(respected_bull)/len(bull_fvg)*100:.1f}%) | Win Rate: {(respected_bull["day_green"]).mean()*100:.1f}% | Avg Gain: {respected_bull["gain_bps"].mean():+.1f} bps')
    print(f'   --> Inverted (Closed below FVG):  {len(inverted_bull)} ({len(inverted_bull)/len(bull_fvg)*100:.1f}%) | Long Failure Rate: {(~inverted_bull["day_green"]).mean()*100:.1f}% | Reversal Drop: {inverted_bull["gain_bps"].mean():+.1f} bps')

    print(f'\n2. BEARISH First 10:00 AM FVG ({len(bear_fvg)} cases):')
    respected_bear = bear_fvg[~bear_fvg['inverted']]
    inverted_bear = bear_fvg[bear_fvg['inverted']]
    print(f'   --> Respected (Holds below FVG): {len(respected_bear)} ({len(respected_bear)/len(bear_fvg)*100:.1f}%) | Win Rate: {(respected_bear["day_green"]).mean()*100:.1f}% | Avg Gain: {respected_bear["gain_bps"].mean():+.1f} bps')
    print(f'   --> Inverted (Closed above FVG):  {len(inverted_bear)} ({len(inverted_bear)/len(bear_fvg)*100:.1f}%) | Short Failure Rate: {(~inverted_bear["day_green"]).mean()*100:.1f}% | Reversal Rally: {inverted_bear["gain_bps"].mean():+.1f} bps')

if __name__ == '__main__':
    run_confluence_study()
