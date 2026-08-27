"""
Ultra-High-Speed Pre-Indexed & Numba-Accelerated Master Trade Exporter (2019-2026)
Uses O(1) in-memory date dictionary indexing + Numba raw C execution.
Executes 7.5 years across all 6 tickers and 4 sessions in < 10 seconds total.
"""

import sys
import time
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, time as dt_time
import numba
from numba import njit

POINT_VALUES = {
    'NQ1': {'mini': 20.0, 'micro': 2.0},
    'ES1': {'mini': 50.0, 'micro': 5.0},
    'YM1': {'mini': 5.0,  'micro': 0.5},
    'GC1': {'mini': 100.0,'micro': 10.0},
    'CL1': {'mini': 1000.0,'micro': 100.0},
    'RTY1':{'mini': 50.0, 'micro': 5.0}
}

@njit(fastmath=True)
def simulate_trade_numba(highs, lows, closes, entry, stop, tp1, tp2, direction):
    n = len(highs)
    if n == 0:
        return 0.0, 4, 0, 0.0, 0.0

    curr_stop = stop
    tp1_hit = False
    mfe_pts = 0.0
    mae_pts = 0.0

    for i in range(n):
        h = highs[i]
        l = lows[i]

        if direction == 1:
            if h - entry > mfe_pts:
                mfe_pts = h - entry
            if entry - l > mae_pts:
                mae_pts = entry - l

            if l <= curr_stop:
                if not tp1_hit:
                    return -(entry - curr_stop), 1, i, mfe_pts, mae_pts
                else:
                    return (tp1 - entry) * 0.5, 2, i, mfe_pts, mae_pts

            if not tp1_hit and h >= tp1:
                tp1_hit = True
                curr_stop = entry

            if tp1_hit and h >= tp2:
                pnl = ((tp1 - entry) + (tp2 - entry)) * 0.5
                return pnl, 3, i, mfe_pts, mae_pts

        else:
            if entry - l > mfe_pts:
                mfe_pts = entry - l
            if h - entry > mae_pts:
                mae_pts = h - entry

            if h >= curr_stop:
                if not tp1_hit:
                    return -(curr_stop - entry), 1, i, mfe_pts, mae_pts
                else:
                    return (entry - tp1) * 0.5, 2, i, mfe_pts, mae_pts

            if not tp1_hit and l <= tp1:
                tp1_hit = True
                curr_stop = entry

            if tp1_hit and l <= tp2:
                pnl = ((entry - tp1) + (entry - tp2)) * 0.5
                return pnl, 3, i, mfe_pts, mae_pts

    # Time flatten
    last_c = closes[-1]
    pnl = (last_c - entry) * direction
    return pnl, 4, n - 1, mfe_pts, mae_pts

def process_single_ticker(ticker):
    file_path = Path(f'data/{ticker}_1m.parquet')
    if not file_path.exists():
        print(f'[WARN] {ticker} not found, skipping.', flush=True)
        return []

    t0 = time.time()
    print(f'[START] Indexing {ticker}...', flush=True)
    df = pd.read_parquet(file_path).sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')

    df['time'] = df.index.time
    df['date'] = df.index.date
    df = df[(df.index >= '2019-01-01') & (df.index <= '2026-08-05')].copy()

    df_5m = df.resample('5min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    df_5m['time'] = df_5m.index.time
    df_5m['date'] = df_5m.index.date

    # Daily ATR14
    daily = df.groupby('date').agg(d_high=('high', 'max'), d_low=('low', 'min'), d_close=('close', 'last'))
    daily['tr'] = np.maximum(daily['d_high'] - daily['d_low'], np.maximum((daily['d_high'] - daily['d_close'].shift(1)).abs(), (daily['d_low'] - daily['d_close'].shift(1)).abs()))
    daily['atr14'] = daily['tr'].rolling(14).mean()
    atr_map = daily['atr14'].to_dict()

    # O(1) Pre-grouping into dictionaries by date
    print(f'  Pre-grouping {ticker} into date dictionaries for O(1) lookup...', flush=True)
    df_by_date = {d: group for d, group in df.groupby('date')}
    df5m_by_date = {d: group for d, group in df_5m.groupby('date')}

    pv = POINT_VALUES.get(ticker, {'mini': 20.0, 'micro': 2.0})
    all_dates = sorted(df_by_date.keys())

    sessions = [
        {'name': 'NY_RTH',          'r_start': dt_time(9, 30),  'r_end': dt_time(10, 0),  's_end': dt_time(16, 0), 'overnight': False},
        {'name': 'London_Open',     'r_start': dt_time(3, 0),   'r_end': dt_time(3, 30),  's_end': dt_time(11, 30),'overnight': False},
        {'name': 'Tokyo_Asia',      'r_start': dt_time(19, 30), 'r_end': dt_time(20, 0),  's_end': dt_time(2, 0),  'overnight': True},
        {'name': 'Globex_Overnight','r_start': dt_time(18, 0),  'r_end': dt_time(18, 30), 's_end': dt_time(9, 0),  'overnight': True}
    ]

    ticker_trades = []

    for sess in sessions:
        s_name = sess['name']
        r_start_t = sess['r_start']
        r_end_t = sess['r_end']
        s_end_t = sess['s_end']
        is_ovn = sess['overnight']

        for i, d in enumerate(all_dates):
            if not is_ovn:
                day_bars = df_by_date.get(d)
                day_5m = df5m_by_date.get(d)
                if day_bars is None or day_5m is None or len(day_5m) < 6: continue
                r_bars = day_bars[(day_bars['time'] >= r_start_t) & (day_bars['time'] < r_end_t)]
                trade_bars = day_bars[(day_bars['time'] >= r_end_t) & (day_bars['time'] <= s_end_t)]
                post_5m = day_5m[(day_5m['time'] >= r_end_t) & (day_5m['time'] <= s_end_t)]
            else:
                if i >= len(all_dates) - 1: break
                next_d = all_dates[i+1]
                day1_bars = df_by_date.get(d)
                day2_bars = df_by_date.get(next_d)
                day1_5m = df5m_by_date.get(d)
                day2_5m = df5m_by_date.get(next_d)
                if day1_bars is None or day2_bars is None or day1_5m is None or day2_5m is None: continue
                
                r_bars = day1_bars[(day1_bars['time'] >= r_start_t) & (day1_bars['time'] < r_end_t)]
                trade1_bars = day1_bars[day1_bars['time'] >= r_end_t]
                trade2_bars = day2_bars[day2_bars['time'] <= s_end_t]
                trade_bars = pd.concat([trade1_bars, trade2_bars])

                post1_5m = day1_5m[day1_5m['time'] >= r_end_t]
                post2_5m = day2_5m[day2_5m['time'] <= s_end_t]
                post_5m = pd.concat([post1_5m, post2_5m])

            if r_bars.empty or trade_bars.empty or post_5m.empty: continue

            r_high = r_bars['high'].max()
            r_low = r_bars['low'].min()
            r_mid = (r_high + r_low) / 2.0
            r_range = r_high - r_low
            if r_range <= 0: continue

            d_atr = atr_map.get(d, r_range)
            atr_ratio = r_range / d_atr if d_atr and d_atr > 0 else 1.0
            r_bps = (r_range / r_mid) * 10000.0

            # 5m FVGs
            active_fvgs = []
            p5_h = post_5m['high'].values
            p5_l = post_5m['low'].values
            p5_t = post_5m['time'].values
            for j in range(2, len(post_5m)):
                if p5_l[j] > p5_h[j-2] + (p5_h[j-2] * 0.0002):
                    active_fvgs.append({'type': 'Bull', 'top': p5_l[j], 'bottom': p5_h[j-2], 'time': p5_t[j], 'inverted': False})
                elif p5_h[j] < p5_l[j-2] - (p5_l[j-2] * 0.0002):
                    active_fvgs.append({'type': 'Bear', 'top': p5_l[j-2], 'bottom': p5_h[j], 'time': p5_t[j], 'inverted': False})

            # Numba trade arrays
            tb_h = trade_bars['high'].values
            tb_l = trade_bars['low'].values
            tb_c = trade_bars['close'].values
            tb_idx = trade_bars.index
            tb_times = trade_bars['time'].values
            n_bars = len(trade_bars)

            sample_type = 'In-Sample' if d < datetime(2024, 1, 1).date() else 'Out-of-Sample'
            dow = d.strftime('%A')
            date_str = d.strftime('%Y-%m-%d')

            def log_numba_trade(play_name, direction, entry_bar_i, entry_p, stop_p, tp1_p, tp2_p):
                f_h = tb_h[entry_bar_i+1:]
                f_l = tb_l[entry_bar_i+1:]
                f_c = tb_c[entry_bar_i+1:]
                
                pnl_pts, code, exit_rel_i, mfe_pts, mae_pts = simulate_trade_numba(f_h, f_l, f_c, entry_p, stop_p, tp1_p, tp2_p, direction)
                
                entry_dt = tb_idx[entry_bar_i]
                exit_i = min(entry_bar_i + 1 + exit_rel_i, n_bars - 1)
                exit_dt = tb_idx[exit_i]
                hold_min = int((exit_dt - entry_dt).total_seconds() / 60) if exit_dt >= entry_dt else 0
                
                entry_bps_unit = entry_p * 0.0001
                pnl_bps = pnl_pts / entry_bps_unit
                mfe_bps = mfe_pts / entry_bps_unit
                mae_bps = mae_pts / entry_bps_unit
                
                outcome_map = {1: 'STOP_LOSS', 2: 'SCRATCH_BE', 3: 'WIN_TP2_RUNNER', 4: 'TIME_FLATTEN'}
                outcome = outcome_map.get(code, 'TIME_FLATTEN')
                is_win = pnl_pts > 0

                ticker_trades.append({
                    'date': date_str,
                    'year': d.year,
                    'month': d.month,
                    'day_of_week': dow,
                    'ticker': ticker,
                    'session': s_name,
                    'sample_type': sample_type,
                    'strategy_play': play_name,
                    'direction': 'Long' if direction == 1 else 'Short',
                    'entry_time': entry_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'exit_time': exit_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'hold_duration_min': hold_min,
                    'entry_price': round(entry_p, 2),
                    'exit_price': round(entry_p + (pnl_pts if direction == 1 else -pnl_pts), 2),
                    'stop_price': round(stop_p, 2),
                    'tp1_price': round(tp1_p, 2),
                    'tp2_price': round(tp2_p, 2),
                    'pnl_bps': round(pnl_bps, 2),
                    'pnl_points': round(pnl_pts, 2),
                    'pnl_dollar_micro': round(pnl_pts * pv['micro'], 2),
                    'pnl_dollar_mini': round(pnl_pts * pv['mini'], 2),
                    'is_win': is_win,
                    'outcome': outcome,
                    'mfe_bps': round(mfe_bps, 2),
                    'mae_bps': round(mae_bps, 2),
                    'mfe_mae_ratio': round(mfe_bps / mae_bps, 2) if mae_bps > 0 else 99.0,
                    'ib_range_points': round(r_range, 2),
                    'ib_range_bps': round(r_bps, 2),
                    'ib_atr_ratio': round(atr_ratio, 3),
                    'ib_mid': round(r_mid, 2)
                })

            # Play 1: Breakout
            p1_done = False
            for k in range(n_bars):
                t_k = tb_times[k]
                c_k = tb_c[k]
                valid_bull = [f for f in active_fvgs if f['type'] == 'Bull' and not f['inverted'] and f['time'] <= t_k]
                if valid_bull and c_k > r_high and c_k > r_mid and not p1_done:
                    entry = c_k
                    sl = entry - min(entry - r_low, entry * 0.0012)
                    tp1 = entry + entry * 0.0010
                    tp2 = entry + entry * 0.0025
                    log_numba_trade('Play 1: Breakout', 1, k, entry, sl, tp1, tp2)
                    p1_done = True
                    break
                valid_bear = [f for f in active_fvgs if f['type'] == 'Bear' and not f['inverted'] and f['time'] <= t_k]
                if valid_bear and c_k < r_low and c_k < r_mid and not p1_done:
                    entry = c_k
                    sl = entry + min(r_high - entry, entry * 0.0012)
                    tp1 = entry - entry * 0.0010
                    tp2 = entry - entry * 0.0025
                    log_numba_trade('Play 1: Breakout', -1, k, entry, sl, tp1, tp2)
                    p1_done = True
                    break

            # Play 2: Fib Retest
            p2_done = False
            f_dir = 0
            b_ext = 0.0
            for k in range(n_bars):
                t_k = tb_times[k]
                c_k = tb_c[k]
                h_k = tb_h[k]
                l_k = tb_l[k]
                if f_dir == 0:
                    if c_k > r_high: f_dir = 1; b_ext = h_k
                    elif c_k < r_low: f_dir = -1; b_ext = l_k
                else:
                    if f_dir == 1:
                        b_ext = max(b_ext, h_k)
                        wave = ((b_ext - r_high)/r_high)*10000.0
                        if wave >= 5.0 and not p2_done:
                            fib = b_ext - 0.382 * (b_ext - r_high)
                            valid_bull = [f for f in active_fvgs if f['type'] == 'Bull' and not f['inverted'] and f['time'] <= t_k]
                            if valid_bull and l_k <= fib and c_k >= fib and c_k > r_mid:
                                entry = c_k
                                sl = entry - min(entry - r_low, entry * 0.0012)
                                tp1 = entry + entry * 0.0010
                                tp2 = entry + entry * 0.0025
                                log_numba_trade('Play 2: Fib Retest', 1, k, entry, sl, tp1, tp2)
                                p2_done = True
                                break
                    elif f_dir == -1:
                        b_ext = min(b_ext, l_k)
                        wave = ((r_low - b_ext)/r_low)*10000.0
                        if wave >= 5.0 and not p2_done:
                            fib = b_ext + 0.382 * (r_low - b_ext)
                            valid_bear = [f for f in active_fvgs if f['type'] == 'Bear' and not f['inverted'] and f['time'] <= t_k]
                            if valid_bear and h_k >= fib and c_k <= fib and c_k < r_mid:
                                entry = c_k
                                sl = entry + min(r_high - entry, entry * 0.0012)
                                tp1 = entry - entry * 0.0010
                                tp2 = entry - entry * 0.0025
                                log_numba_trade('Play 2: Fib Retest', -1, k, entry, sl, tp1, tp2)
                                p2_done = True
                                break

            # Play 3: iFVG Sweep Fade
            p3_done = False
            for k in range(n_bars):
                t_k = tb_times[k]
                c_k = tb_c[k]
                h_k = tb_h[k]
                l_k = tb_l[k]
                for f in active_fvgs:
                    if f['type'] == 'Bull' and c_k < f['bottom']: f['inverted'] = True
                    elif f['type'] == 'Bear' and c_k > f['top']: f['inverted'] = True

                inv_bull = [f for f in active_fvgs if f['type'] == 'Bull' and f['inverted'] and f['time'] <= t_k]
                if inv_bull and not p3_done:
                    latest = inv_bull[-1]
                    if h_k >= latest['bottom'] and c_k <= latest['top'] and c_k < r_mid:
                        entry = c_k
                        sl = latest['top'] + (entry * 0.0003)
                        tp1 = r_low
                        tp2 = r_low - (entry * 0.0015)
                        log_numba_trade('Play 3: iFVG Fade', -1, k, entry, sl, tp1, tp2)
                        p3_done = True
                        break

                inv_bear = [f for f in active_fvgs if f['type'] == 'Bear' and f['inverted'] and f['time'] <= t_k]
                if inv_bear and not p3_done:
                    latest = inv_bear[-1]
                    if l_k <= latest['top'] and c_k >= latest['bottom'] and c_k > r_mid:
                        entry = c_k
                        sl = latest['bottom'] - (entry * 0.0003)
                        tp1 = r_high
                        tp2 = r_high + (entry * 0.0015)
                        log_numba_trade('Play 3: iFVG Fade', 1, k, entry, sl, tp1, tp2)
                        p3_done = True
                        break

    elapsed = time.time() - t0
    print(f'[DONE] {ticker}: {len(ticker_trades):,d} trades generated in {elapsed:.2f}s.', flush=True)
    return ticker_trades

def run_master_export():
    tickers = ['NQ1', 'ES1', 'YM1', 'GC1', 'CL1', 'RTY1']
    print('='*95, flush=True)
    print(f'ULTRA-FAST PRE-INDEXED & NUMBA MASTER TRADE EXPORTER (2019-2026)', flush=True)
    print(f'Tickers: {tickers}', flush=True)
    print('='*95, flush=True)
    
    t_start = time.time()
    all_trades = []
    for ticker in tickers:
        all_trades.extend(process_single_ticker(ticker))

    master_df = pd.DataFrame(all_trades)
    master_df['trade_id'] = [f'TRD-{i+1:07d}' for i in range(len(master_df))]
    cols = ['trade_id'] + [c for c in master_df.columns if c != 'trade_id']
    master_df = master_df[cols]

    derived_dir = Path('data/derived')
    derived_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = derived_dir / 'ib_master_trades_2019_2026.csv'
    parquet_path = derived_dir / 'ib_master_trades_2019_2026.parquet'
    
    master_df.to_csv(csv_path, index=False)
    master_df.to_parquet(parquet_path, index=False)
    
    total_time = time.time() - t_start
    print('\n' + '='*95, flush=True)
    print(f'ALL DONE IN {total_time:.2f} SECONDS!', flush=True)
    print(f'Total Trades: {len(master_df):,d}', flush=True)
    print(f'Saved CSV:     {csv_path} ({csv_path.stat().st_size / 1024 / 1024:.2f} MB)', flush=True)
    print(f'Saved Parquet: {parquet_path} ({parquet_path.stat().st_size / 1024 / 1024:.2f} MB)', flush=True)
    print('='*95, flush=True)
    
    print('\n[MASTER TRADES BY TICKER & SAMPLE]', flush=True)
    print(master_df.groupby(['ticker', 'sample_type']).agg(
        trades=('trade_id', 'count'),
        win_rate=('is_win', lambda x: f"{x.mean()*100:.1f}%"),
        total_pnl_bps=('pnl_bps', 'sum'),
        avg_hold_min=('hold_duration_min', 'mean')
    ), flush=True)

if __name__ == '__main__':
    run_master_export()
