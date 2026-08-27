"""
Master Initial Balance Trade Exporter (2019-2026)
Generates granular trade-by-trade records across:
- In-Sample (2019-01-01 to 2023-12-31)
- Out-of-Sample (2024-01-01 to 2026-08-05)
For all 3 plays (Breakout, Fib Retest, iFVG Fade)
Across all 4 sessions (NY RTH, London Open, Tokyo Asia, Globex Overnight)
For NQ1, ES1, YM1, GC1, CL1, RTY1.
Outputs both CSV and Parquet formats for dashboard integration.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

# Instrument Point Values (Mini / Micro)
POINT_VALUES = {
    'NQ1': {'mini': 20.0, 'micro': 2.0},
    'ES1': {'mini': 50.0, 'micro': 5.0},
    'YM1': {'mini': 5.0,  'micro': 0.5},
    'GC1': {'mini': 100.0,'micro': 10.0},
    'CL1': {'mini': 1000.0,'micro': 100.0},
    'RTY1':{'mini': 50.0, 'micro': 5.0}
}

SESSIONS = [
    {'name': 'NY_RTH',          'r_start': '09:30', 'r_end': '10:00', 's_end': '16:00', 'overnight': False},
    {'name': 'London_Open',     'r_start': '03:00', 'r_end': '03:30', 's_end': '11:30', 'overnight': False},
    {'name': 'Tokyo_Asia',      'r_start': '19:30', 'r_end': '20:00', 's_end': '02:00', 'overnight': True},
    {'name': 'Globex_Overnight','r_start': '18:00', 'r_end': '18:30', 's_end': '09:00', 'overnight': True}
]

def generate_master_dataset():
    data_dir = Path('data')
    derived_dir = Path('data/derived')
    derived_dir.mkdir(parents=True, exist_ok=True)
    
    all_master_trades = []
    trade_id_counter = 1
    
    tickers = ['NQ1', 'ES1', 'YM1', 'GC1', 'CL1', 'RTY1']
    
    for ticker in tickers:
        file_path = data_dir / f'{ticker}_1m.parquet'
        if not file_path.exists():
            print(f'[WARN] Skipping {ticker}: {file_path} not found.')
            continue
            
        print(f'\n[PROCESSING] Loading continuous data for {ticker}...')
        df = pd.read_parquet(file_path).sort_index()
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
            df.index = df.index.tz_convert('America/New_York')
            
        df['time'] = df.index.time
        df['date'] = df.index.date
        df = df[(df.index >= '2019-01-01') & (df.index <= '2026-08-05')].copy()
        
        # Resample 5m
        df_5m = df.resample('5min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
        df_5m['time'] = df_5m.index.time
        df_5m['date'] = df_5m.index.date
        
        # Daily ATR14
        daily = df.groupby('date').agg(d_high=('high', 'max'), d_low=('low', 'min'), d_close=('close', 'last'))
        daily['tr'] = np.maximum(daily['d_high'] - daily['d_low'], np.maximum((daily['d_high'] - daily['d_close'].shift(1)).abs(), (daily['d_low'] - daily['d_close'].shift(1)).abs()))
        daily['atr14'] = daily['tr'].rolling(14).mean()
        atr_map = daily['atr14'].to_dict()
        
        all_dates = sorted(df['date'].unique())
        pv = POINT_VALUES.get(ticker, {'mini': 20.0, 'micro': 2.0})
        
        for sess in SESSIONS:
            s_name = sess['name']
            r_start_t = datetime.strptime(sess['r_start'], '%H:%M').time()
            r_end_t = datetime.strptime(sess['r_end'], '%H:%M').time()
            s_end_t = datetime.strptime(sess['s_end'], '%H:%M').time()
            is_ovn = sess['overnight']
            
            for i, d in enumerate(all_dates):
                if not is_ovn:
                    day_bars = df[df['date'] == d]
                    day_5m = df_5m[df_5m['date'] == d]
                    if day_bars.empty or len(day_5m) < 6: continue
                    r_bars = day_bars[(day_bars['time'] >= r_start_t) & (day_bars['time'] < r_end_t)]
                    trade_bars = day_bars[(day_bars['time'] >= r_end_t) & (day_bars['time'] <= s_end_t)]
                    post_5m = day_5m[(day_5m['time'] >= r_end_t) & (day_5m['time'] <= s_end_t)]
                else:
                    if i >= len(all_dates) - 1: break
                    next_d = all_dates[i+1]
                    sess_bars = df[((df['date'] == d) & (df['time'] >= r_start_t)) | ((df['date'] == next_d) & (df['time'] <= s_end_t))]
                    sess_5m = df_5m[((df_5m['date'] == d) & (df_5m['time'] >= r_start_t)) | ((df_5m['date'] == next_d) & (df_5m['time'] <= s_end_t))]
                    if sess_bars.empty or len(sess_5m) < 6: continue
                    r_bars = sess_bars[(sess_bars['date'] == d) & (sess_bars['time'] >= r_start_t) & (sess_bars['time'] < r_end_t)]
                    trade_bars = sess_bars[~((sess_bars['date'] == d) & (sess_bars['time'] < r_end_t))]
                    post_5m = sess_5m[~((sess_5m['date'] == d) & (sess_5m['time'] < r_end_t))]

                if r_bars.empty or trade_bars.empty: continue
                
                r_high = r_bars['high'].max()
                r_low = r_bars['low'].min()
                r_mid = (r_high + r_low) / 2.0
                r_range = r_high - r_low
                if r_range <= 0: continue
                
                d_atr = atr_map.get(d, r_range)
                atr_ratio = r_range / d_atr if d_atr and d_atr > 0 else 1.0
                r_bps = (r_range / r_mid) * 10000.0
                
                # Detect 5m FVGs
                active_fvgs = []
                for j in range(2, len(post_5m)):
                    b0 = post_5m.iloc[j-2]; b2 = post_5m.iloc[j]
                    if b2['low'] > b0['high'] + (b0['high'] * 0.0002):
                        active_fvgs.append({'type': 'Bull', 'top': b2['low'], 'bottom': b0['high'], 'time': b2['time'], 'inverted': False})
                    elif b2['high'] < b0['low'] - (b0['low'] * 0.0002):
                        active_fvgs.append({'type': 'Bear', 'top': b0['low'], 'bottom': b2['high'], 'time': b2['time'], 'inverted': False})

                # Helper to create master trade record
                def make_record(play_name, direction, entry_bar, entry_p, stop_p, tp1_p, tp2_p, fwd_b):
                    nonlocal trade_id_counter
                    entry_t = entry_bar.name
                    pnl_bps, win, outcome, exit_p, exit_t, mfe_bps, mae_bps = eval_full_trade(fwd_b, entry_p, stop_p, tp1_p, tp2_p, direction, entry_t)
                    hold_min = int((exit_t - entry_t).total_seconds() / 60) if exit_t >= entry_t else 0
                    pnl_pts = (exit_p - entry_p) if direction == 1 else (entry_p - exit_p)
                    
                    sample_type = 'In-Sample' if d < datetime(2024, 1, 1).date() else 'Out-of-Sample'
                    
                    rec = {
                        'trade_id': f'TRD-{trade_id_counter:07d}',
                        'date': d.strftime('%Y-%m-%d'),
                        'year': d.year,
                        'month': d.month,
                        'day_of_week': d.strftime('%A'),
                        'ticker': ticker,
                        'session': s_name,
                        'sample_type': sample_type,
                        'strategy_play': play_name,
                        'direction': 'Long' if direction == 1 else 'Short',
                        'entry_time': entry_t.strftime('%Y-%m-%d %H:%M:%S'),
                        'exit_time': exit_t.strftime('%Y-%m-%d %H:%M:%S'),
                        'hold_duration_min': hold_min,
                        'entry_price': round(entry_p, 2),
                        'exit_price': round(exit_p, 2),
                        'stop_price': round(stop_p, 2),
                        'tp1_price': round(tp1_p, 2),
                        'tp2_price': round(tp2_p, 2),
                        'pnl_bps': round(pnl_bps, 2),
                        'pnl_points': round(pnl_pts, 2),
                        'pnl_dollar_micro': round(pnl_pts * pv['micro'], 2),
                        'pnl_dollar_mini': round(pnl_pts * pv['mini'], 2),
                        'is_win': win,
                        'outcome': outcome,
                        'mfe_bps': round(mfe_bps, 2),
                        'mae_bps': round(mae_bps, 2),
                        'mfe_mae_ratio': round(mfe_bps / mae_bps, 2) if mae_bps > 0 else 99.0,
                        'ib_range_points': round(r_range, 2),
                        'ib_range_bps': round(r_bps, 2),
                        'ib_atr_ratio': round(atr_ratio, 3),
                        'ib_mid': round(r_mid, 2)
                    }
                    trade_id_counter += 1
                    return rec

                # --- PLAY 1: BREAKOUT ---
                p1_done = False
                for idx, bar in trade_bars.iterrows():
                    valid_bull = [f for f in active_fvgs if f['type'] == 'Bull' and not f['inverted'] and f['time'] <= bar['time']]
                    if valid_bull and bar['close'] > r_high and bar['close'] > r_mid and not p1_done:
                        entry = bar['close']
                        sl = entry - min(entry - r_low, entry * 0.0012)
                        tp1 = entry + entry * 0.0010
                        tp2 = entry + entry * 0.0025
                        fwd = trade_bars.loc[idx:][1:]
                        all_master_trades.append(make_record('Play 1: Breakout', 1, bar, entry, sl, tp1, tp2, fwd))
                        p1_done = True
                        break
                    valid_bear = [f for f in active_fvgs if f['type'] == 'Bear' and not f['inverted'] and f['time'] <= bar['time']]
                    if valid_bear and bar['close'] < r_low and bar['close'] < r_mid and not p1_done:
                        entry = bar['close']
                        sl = entry + min(r_high - entry, entry * 0.0012)
                        tp1 = entry - entry * 0.0010
                        tp2 = entry - entry * 0.0025
                        fwd = trade_bars.loc[idx:][1:]
                        all_master_trades.append(make_record('Play 1: Breakout', -1, bar, entry, sl, tp1, tp2, fwd))
                        p1_done = True
                        break

                # --- PLAY 2: FIB RETEST ---
                p2_done = False
                f_dir = 0
                b_ext = 0.0
                for idx, bar in trade_bars.iterrows():
                    if f_dir == 0:
                        if bar['close'] > r_high: f_dir = 1; b_ext = bar['high']
                        elif bar['close'] < r_low: f_dir = -1; b_ext = bar['low']
                    else:
                        if f_dir == 1:
                            b_ext = max(b_ext, bar['high'])
                            wave = ((b_ext - r_high)/r_high)*10000.0
                            if wave >= 5.0 and not p2_done:
                                fib = b_ext - 0.382 * (b_ext - r_high)
                                valid_bull = [f for f in active_fvgs if f['type'] == 'Bull' and not f['inverted'] and f['time'] <= bar['time']]
                                if valid_bull and bar['low'] <= fib and bar['close'] >= fib and bar['close'] > r_mid:
                                    entry = bar['close']
                                    sl = entry - min(entry - r_low, entry * 0.0012)
                                    tp1 = entry + entry * 0.0010
                                    tp2 = entry + entry * 0.0025
                                    fwd = trade_bars.loc[idx:][1:]
                                    all_master_trades.append(make_record('Play 2: Fib Retest', 1, bar, entry, sl, tp1, tp2, fwd))
                                    p2_done = True
                                    break
                        elif f_dir == -1:
                            b_ext = min(b_ext, bar['low'])
                            wave = ((r_low - b_ext)/r_low)*10000.0
                            if wave >= 5.0 and not p2_done:
                                fib = b_ext + 0.382 * (r_low - b_ext)
                                valid_bear = [f for f in active_fvgs if f['type'] == 'Bear' and not f['inverted'] and f['time'] <= bar['time']]
                                if valid_bear and bar['high'] >= fib and bar['close'] <= fib and bar['close'] < r_mid:
                                    entry = bar['close']
                                    sl = entry + min(r_high - entry, entry * 0.0012)
                                    tp1 = entry - entry * 0.0010
                                    tp2 = entry - entry * 0.0025
                                    fwd = trade_bars.loc[idx:][1:]
                                    all_master_trades.append(make_record('Play 2: Fib Retest', -1, bar, entry, sl, tp1, tp2, fwd))
                                    p2_done = True
                                    break

                # --- PLAY 3: iFVG SWEEP FADE ---
                p3_done = False
                for idx, bar in trade_bars.iterrows():
                    for f in active_fvgs:
                        if f['type'] == 'Bull' and bar['close'] < f['bottom']: f['inverted'] = True
                        elif f['type'] == 'Bear' and bar['close'] > f['top']: f['inverted'] = True

                    inv_bull = [f for f in active_fvgs if f['type'] == 'Bull' and f['inverted'] and f['time'] <= bar['time']]
                    if inv_bull and not p3_done:
                        latest = inv_bull[-1]
                        if bar['high'] >= latest['bottom'] and bar['close'] <= latest['top'] and bar['close'] < r_mid:
                            entry = bar['close']
                            sl = latest['top'] + (entry * 0.0003)
                            tp1 = r_low
                            tp2 = r_low - (entry * 0.0015)
                            fwd = trade_bars.loc[idx:][1:]
                            all_master_trades.append(make_record('Play 3: iFVG Fade', -1, bar, entry, sl, tp1, tp2, fwd))
                            p3_done = True
                            break

                    inv_bear = [f for f in active_fvgs if f['type'] == 'Bear' and f['inverted'] and f['time'] <= bar['time']]
                    if inv_bear and not p3_done:
                        latest = inv_bear[-1]
                        if bar['low'] <= latest['top'] and bar['close'] >= latest['bottom'] and bar['close'] > r_mid:
                            entry = bar['close']
                            sl = latest['bottom'] - (entry * 0.0003)
                            tp1 = r_high
                            tp2 = r_high + (entry * 0.0015)
                            fwd = trade_bars.loc[idx:][1:]
                            all_master_trades.append(make_record('Play 3: iFVG Fade', 1, bar, entry, sl, tp1, tp2, fwd))
                            p3_done = True
                            break

    master_df = pd.DataFrame(all_master_trades)
    print('\n' + '='*95)
    print(f'MASTER DATASET GENERATED: {len(master_df):,d} Total Simulated Trades')
    print('='*95)
    
    # Save CSV and Parquet
    csv_path = derived_dir / 'ib_master_trades_2019_2026.csv'
    parquet_path = derived_dir / 'ib_master_trades_2019_2026.parquet'
    
    master_df.to_csv(csv_path, index=False)
    master_df.to_parquet(parquet_path, index=False)
    print(f'[SUCCESS] Saved CSV to {csv_path} ({csv_path.stat().st_size / 1024 / 1024:.2f} MB)')
    print(f'[SUCCESS] Saved Parquet to {parquet_path} ({parquet_path.stat().st_size / 1024 / 1024:.2f} MB)')
    
    # Print high-level breakdown
    print('\n[SUMMARY BREAKDOWN BY SAMPLE & PLAY]')
    print(master_df.groupby(['sample_type', 'strategy_play']).agg(
        trades=('trade_id', 'count'),
        win_rate=('is_win', lambda x: f"{x.mean()*100:.1f}%"),
        total_pnl_bps=('pnl_bps', 'sum'),
        avg_mfe_bps=('mfe_bps', 'mean'),
        avg_mae_bps=('mae_bps', 'mean')
    ))
    return master_df

def eval_full_trade(fwd_bars, entry, stop, tp1, tp2, direction, default_exit_t=None):
    if fwd_bars.empty:
        return 0.0, False, 'NO_DATA', entry, default_exit_t if default_exit_t is not None else datetime.now(), 0.0, 0.0
        
    tp1_hit = False
    tp2_hit = False
    stopped = False
    curr_stop = stop
    mfe_pts = 0.0
    mae_pts = 0.0
    exit_price = entry
    exit_time = fwd_bars.iloc[-1].name
    outcome = 'TIME_FLATTEN'
    
    for idx, bar in fwd_bars.iterrows():
        if direction == 1:
            mfe_pts = max(mfe_pts, bar['high'] - entry)
            mae_pts = max(mae_pts, entry - bar['low'])
            if bar['low'] <= curr_stop:
                stopped = True
                exit_price = curr_stop
                exit_time = idx
                outcome = 'STOP_LOSS' if not tp1_hit else 'SCRATCH_BE'
                break
            if not tp1_hit and bar['high'] >= tp1:
                tp1_hit = True
                curr_stop = entry # Move stop to Breakeven
            if tp1_hit and bar['high'] >= tp2:
                tp2_hit = True
                exit_price = tp2
                exit_time = idx
                outcome = 'WIN_TP2_RUNNER'
                break
        else:
            mfe_pts = max(mfe_pts, entry - bar['low'])
            mae_pts = max(mae_pts, bar['high'] - entry)
            if bar['high'] >= curr_stop:
                stopped = True
                exit_price = curr_stop
                exit_time = idx
                outcome = 'STOP_LOSS' if not tp1_hit else 'SCRATCH_BE'
                break
            if not tp1_hit and bar['low'] <= tp1:
                tp1_hit = True
                curr_stop = entry # Move stop to Breakeven
            if tp1_hit and bar['low'] <= tp2:
                tp2_hit = True
                exit_price = tp2
                exit_time = idx
                outcome = 'WIN_TP2_RUNNER'
                break
                
    entry_bps = entry * 0.0001
    mfe_bps = mfe_pts / entry_bps
    mae_bps = mae_pts / entry_bps
    
    if stopped and not tp1_hit:
        pnl = -(abs(entry - stop) / entry_bps)
        return pnl, False, outcome, exit_price, exit_time, mfe_bps, mae_bps
    elif stopped and tp1_hit:
        pnl = (abs(tp1 - entry) / entry_bps) / 2.0
        return pnl, True, outcome, exit_price, exit_time, mfe_bps, mae_bps
    elif tp2_hit:
        pnl = ((abs(tp1 - entry) + abs(tp2 - entry)) / 2.0) / entry_bps
        return pnl, True, outcome, exit_price, exit_time, mfe_bps, mae_bps
    else:
        last_p = fwd_bars.iloc[-1]['close']
        pnl = ((last_p - entry) * direction) / entry_bps
        return pnl, pnl > 0, outcome, last_p, exit_time, mfe_bps, mae_bps

if __name__ == '__main__':
    generate_master_dataset()
