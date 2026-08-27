"""
Empirical Backtest: The 5m FVG / iFVG Respect Filter as the Master Chop Gate
Tests NQ1 (2019-2026) across 1,932 sessions.
Compares:
1. Raw IB Breakout / Retest / Fade (No FVG Gate)
2. Gated IB Suite (Require Respected 5m FVG for Continuation OR Respected 5m iFVG for Fade)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

def run_fvg_chop_study():
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

    # 1. 5-Minute Resampling
    df_5m = df.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    df_5m['time'] = df_5m.index.time
    df_5m['date'] = df_5m.index.date

    # 2. Extract Daily IB (09:30 - 10:00)
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

    print(f'[INFO] Extracted {len(ib_daily)} daily sessions. Running simulation...')

    raw_trades = []
    gated_trades = []
    chop_days_filtered = 0

    for d, ib_row in ib_daily.iterrows():
        day_1m = df[df['date'] == d]
        day_5m = df_5m[df_5m['date'] == d]
        if day_1m.empty or len(day_5m) < 12:
            continue

        ib_high = ib_row['ib_high']
        ib_low = ib_row['ib_low']
        ib_mid = ib_row['ib_mid']

        # -------------------------------------------------------------
        # A. Detect 5m FVGs formed post-10:00 AM (10:00 - 15:30)
        # -------------------------------------------------------------
        post10_5m = day_5m[(day_5m['time'] >= time(10, 0)) & (day_5m['time'] <= time(15, 30))]
        
        active_fvgs = [] # List of {'type': 'Bull'/'Bear', 'top': float, 'bottom': float, 'inverted': bool, 'time': t}
        
        for i in range(2, len(post10_5m)):
            b0 = post10_5m.iloc[i-2]
            b1 = post10_5m.iloc[i-1]
            b2 = post10_5m.iloc[i]
            
            # Bullish FVG
            if b2['low'] > b0['high'] + (b0['high'] * 0.0002):
                active_fvgs.append({'type': 'Bull', 'top': b2['low'], 'bottom': b0['high'], 'time': b2['time'], 'bar_idx': post10_5m.index[i], 'inverted': False})
            # Bearish FVG
            elif b2['high'] < b0['low'] - (b0['low'] * 0.0002):
                active_fvgs.append({'type': 'Bear', 'top': b0['low'], 'bottom': b2['high'], 'time': b2['time'], 'bar_idx': post10_5m.index[i], 'inverted': False})

        # -------------------------------------------------------------
        # B. Check 1-minute execution windows
        # -------------------------------------------------------------
        trade_window_1m = day_1m[(day_1m['time'] >= time(10, 30)) & (day_1m['time'] <= time(15, 30))]
        if trade_window_1m.empty:
            continue

        day_gated_trade_taken = False
        day_raw_trade_taken = False

        for idx, bar in trade_window_1m.iterrows():
            curr_p = bar['close']
            curr_t = bar['time']

            # Check RAW Breakout (Baseline)
            if not day_raw_trade_taken:
                if bar['close'] > ib_high:
                    entry = bar['close']
                    sl = entry - entry * 0.0012
                    tp1 = entry + entry * 0.0010
                    tp2 = entry + entry * 0.0025
                    fwd = day_1m.loc[idx:][1:]
                    pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                    raw_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                    day_raw_trade_taken = True
                elif bar['close'] < ib_low:
                    entry = bar['close']
                    sl = entry + entry * 0.0012
                    tp1 = entry - entry * 0.0010
                    tp2 = entry - entry * 0.0025
                    fwd = day_1m.loc[idx:][1:]
                    pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                    raw_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                    day_raw_trade_taken = True

            # Check GATED Execution: Require Respected 5m FVG or Respected iFVG
            if not day_gated_trade_taken and active_fvgs:
                # Find most recent FVG formed before current time
                valid_fvgs = [f for f in active_fvgs if f['time'] <= curr_t]
                if not valid_fvgs:
                    continue

                latest_fvg = valid_fvgs[-1]
                
                # Check Bullish FVG Respect (Continuation Long)
                if latest_fvg['type'] == 'Bull' and not latest_fvg['inverted']:
                    if bar['low'] <= latest_fvg['top'] and bar['close'] >= latest_fvg['bottom'] and bar['close'] > ib_mid:
                        entry = bar['close']
                        sl = latest_fvg['bottom'] - (entry * 0.0003)
                        tp1 = entry + entry * 0.0010
                        tp2 = entry + entry * 0.0025
                        fwd = day_1m.loc[idx:][1:]
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                        gated_trades.append({'date': d, 'type': 'Bull_FVG_Retest', 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                        day_gated_trade_taken = True
                        break

                # Check Bearish FVG Respect (Continuation Short)
                elif latest_fvg['type'] == 'Bear' and not latest_fvg['inverted']:
                    if bar['high'] >= latest_fvg['bottom'] and bar['close'] <= latest_fvg['top'] and bar['close'] < ib_mid:
                        entry = bar['close']
                        sl = latest_fvg['top'] + (entry * 0.0003)
                        tp1 = entry - entry * 0.0010
                        tp2 = entry - entry * 0.0025
                        fwd = day_1m.loc[idx:][1:]
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                        gated_trades.append({'date': d, 'type': 'Bear_FVG_Retest', 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                        day_gated_trade_taken = True
                        break

                # Check Inversion FVG (iFVG Fade)
                # Bullish FVG that was inverted (closed below) -> Now acting as Resistance for Short Fade
                elif latest_fvg['type'] == 'Bull' and latest_fvg['inverted']:
                    if bar['high'] >= latest_fvg['bottom'] and bar['close'] <= latest_fvg['top'] and bar['close'] < ib_mid:
                        entry = bar['close']
                        sl = latest_fvg['top'] + (entry * 0.0003)
                        tp1 = ib_low
                        tp2 = ib_low - (entry * 0.0015)
                        fwd = day_1m.loc[idx:][1:]
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                        gated_trades.append({'date': d, 'type': 'iFVG_Short_Fade', 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                        day_gated_trade_taken = True
                        break

                # Bearish FVG that was inverted (closed above) -> Now acting as Support for Long Fade
                elif latest_fvg['type'] == 'Bear' and latest_fvg['inverted']:
                    if bar['low'] <= latest_fvg['top'] and bar['close'] >= latest_fvg['bottom'] and bar['close'] > ib_mid:
                        entry = bar['close']
                        sl = latest_fvg['bottom'] - (entry * 0.0003)
                        tp1 = ib_high
                        tp2 = ib_high + (entry * 0.0015)
                        fwd = day_1m.loc[idx:][1:]
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                        gated_trades.append({'date': d, 'type': 'iFVG_Long_Fade', 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                        day_gated_trade_taken = True
                        break

                # Track if FVG gets inverted by current bar
                if latest_fvg['type'] == 'Bull' and bar['close'] < latest_fvg['bottom']:
                    latest_fvg['inverted'] = True
                elif latest_fvg['type'] == 'Bear' and bar['close'] > latest_fvg['top']:
                    latest_fvg['inverted'] = True

        if not day_gated_trade_taken:
            chop_days_filtered += 1

    df_raw = pd.DataFrame(raw_trades)
    df_gated = pd.DataFrame(gated_trades)

    def print_summary(title, res_df):
        wins = res_df[res_df['win']]
        losses = res_df[~res_df['win']]
        gw = wins['pnl_bps'].sum()
        gl = abs(losses['pnl_bps'].sum())
        pf = (gw / gl) if gl > 0 else 99.0
        wr = (len(wins) / len(res_df)) * 100.0
        net = res_df['pnl_bps'].sum()
        avg_mfe = res_df['mfe_bps'].mean()
        avg_mae = res_df['mae_bps'].mean()
        
        cum = res_df['pnl_bps'].cumsum()
        max_dd = abs((cum - cum.cummax()).min()) if not cum.empty else 0.0

        print(f'\n[{title}]')
        print(f'  Total Trades:     {len(res_df):,d}')
        print(f'  Win Rate:         {wr:5.1f}%')
        print(f'  Profit Factor:    {pf:5.2f}')
        print(f'  Net Return (bps): {net:+8.1f} bps')
        print(f'  Max Drawdown:     {max_dd:6.1f} bps')
        print(f'  Avg MFE / MAE:    {avg_mfe:5.1f} bps / {avg_mae:5.1f} bps')

    print('\n' + '='*90)
    print('5M FVG / iFVG CHOP GATE COMPARATIVE STUDY (2019-2026, 1,932 SESSIONS)')
    print('='*90)
    print_summary('BASELINE (Raw IB Breakout - No FVG Gate)', df_raw)
    print_summary('GATED (5m FVG / iFVG Respect Requirement)', df_gated)
    print(f'\n[CHOP FILTERING EFFECT] Filtered out {chop_days_filtered:,d} no-edge / chop sessions ({chop_days_filtered/len(ib_daily)*100:.1f}% of all days)!')

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
    run_fvg_chop_study()
