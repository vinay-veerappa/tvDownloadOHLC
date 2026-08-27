"""
Unified Confluence IS/OOS Multi-Asset Backtesting Engine
Evaluates:
- Play 1: Breakout Bot
- Play 2: Fib Retest Bot
- Play 3: iFVG Sweep Fade Bot
Across:
- In-Sample (IS): 2019-01-01 to 2023-12-31 (5 Years)
- Out-of-Sample (OOS): 2024-01-01 to 2026-08-05 (2.5+ Years)
On NQ1 and ES1.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

def run_study(ticker='NQ1'):
    data_path = Path(f'data/{ticker}_1m.parquet')
    if not data_path.exists():
        print(f'[ERROR] {data_path} not found')
        return

    print('='*95)
    print(f'UNIFIED CONFLUENCE IS/OOS BACKTEST: {ticker}')
    print(f'IS Period:  2019-01-01 to 2023-12-31 (5 Years)')
    print(f'OOS Period: 2024-01-01 to 2026-08-05 (2.5+ Years)')
    print('='*95)

    df = pd.read_parquet(data_path)
    df = df.sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')

    df['time'] = df.index.time
    df['date'] = df.index.date
    df = df[(df.index >= '2019-01-01') & (df.index <= '2026-08-05')].copy()

    # Resample 5m bars for FVG detection
    df_5m = df.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    df_5m['time'] = df_5m.index.time
    df_5m['date'] = df_5m.index.date

    # Compute Daily IB (09:30 - 10:00) & 09:00 Hour
    rth = df[(df['time'] >= time(9, 0)) & (df['time'] < time(16, 0))]

    h09_bars = rth[(rth['time'] >= time(9, 0)) & (rth['time'] < time(10, 0))]
    h09_daily = h09_bars.groupby('date').agg(
        h09_high=('high', 'max'),
        h09_low=('low', 'min')
    )

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
    ib_daily = ib_daily.join(daily[['atr14']]).join(h09_daily)
    ib_daily['ib_atr_ratio'] = ib_daily['ib_range'] / ib_daily['atr14']

    print(f'[INFO] Extracted {len(ib_daily):,d} trading sessions.')

    # Run simulations for IS and OOS
    def simulate_unified_suite(start_dt, end_dt):
        p1_trades = []
        p2_trades = []
        p3_trades = []
        
        ib_subset = ib_daily[(ib_daily.index >= pd.to_datetime(start_dt).date()) & (ib_daily.index <= pd.to_datetime(end_dt).date())]
        
        for d, ib_row in ib_subset.iterrows():
            if pd.isna(ib_row['ib_range']) or ib_row['ib_range'] <= 0:
                continue
                
            day_1m = df[df['date'] == d]
            day_5m = df_5m[df_5m['date'] == d]
            if day_1m.empty or len(day_5m) < 10:
                continue

            ib_high = ib_row['ib_high']
            ib_low = ib_row['ib_low']
            ib_mid = ib_row['ib_mid']
            atr_ratio = ib_row['ib_atr_ratio']
            h09_high = ib_row['h09_high']
            h09_low = ib_row['h09_low']

            # Detect 5m FVGs formed post-10:00 AM (10:00 - 15:30)
            post10_5m = day_5m[(day_5m['time'] >= time(10, 0)) & (day_5m['time'] <= time(15, 30))]
            active_fvgs = []
            
            for i in range(2, len(post10_5m)):
                b0 = post10_5m.iloc[i-2]; b2 = post10_5m.iloc[i]
                if b2['low'] > b0['high'] + (b0['high'] * 0.0002):
                    active_fvgs.append({'type': 'Bull', 'top': b2['low'], 'bottom': b0['high'], 'time': b2['time'], 'inverted': False})
                elif b2['high'] < b0['low'] - (b0['low'] * 0.0002):
                    active_fvgs.append({'type': 'Bear', 'top': b0['low'], 'bottom': b2['high'], 'time': b2['time'], 'inverted': False})

            # Check 10:00 AM Double Sweep (R1 Whipsaw Lockout)
            h10_window = day_1m[(day_1m['time'] >= time(10, 0)) & (day_1m['time'] < time(11, 0))]
            if not h10_window.empty:
                swept_both_09 = (h10_window['high'].max() > h09_high) and (h10_window['low'].min() < h09_low)
                if swept_both_09:
                    continue # R1 Double-Breach Lockout: Skip Day

            # -------------------------------------------------------------
            # PLAY 1: BREAKOUT BOT (10:30 - 15:30, Avoid Lunch 11:30-13:30)
            # -------------------------------------------------------------
            tw_p1 = day_1m[(day_1m['time'] >= time(10, 30)) & (day_1m['time'] <= time(15, 30))]
            p1_done = False
            for idx, bar in tw_p1.iterrows():
                if time(11, 30) <= bar['time'] <= time(13, 30):
                    continue
                # Require 5m Bull FVG Respect AND Price > IB Mid
                valid_bull = [f for f in active_fvgs if f['type'] == 'Bull' and not f['inverted'] and f['time'] <= bar['time']]
                if valid_bull and bar['close'] > ib_high and bar['close'] > ib_mid:
                    entry = bar['close']
                    sl = entry - min(entry - ib_low, entry * 0.0012)
                    tp1 = entry + entry * 0.0010
                    tp2 = entry + entry * 0.0025
                    fwd = day_1m.loc[idx:][1:]
                    pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                    p1_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                    p1_done = True
                    break
                    
                valid_bear = [f for f in active_fvgs if f['type'] == 'Bear' and not f['inverted'] and f['time'] <= bar['time']]
                if valid_bear and bar['close'] < ib_low and bar['close'] < ib_mid:
                    entry = bar['close']
                    sl = entry + min(ib_high - entry, entry * 0.0012)
                    tp1 = entry - entry * 0.0010
                    tp2 = entry - entry * 0.0025
                    fwd = day_1m.loc[idx:][1:]
                    pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                    p1_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                    p1_done = True
                    break

            # -------------------------------------------------------------
            # PLAY 2: FIB 38.2% RETEST BOT (10:30 - 15:30)
            # -------------------------------------------------------------
            tw_p2 = day_1m[(day_1m['time'] >= time(10, 0)) & (day_1m['time'] <= time(15, 30))]
            f_dir = 0
            b_ext = 0.0
            p2_done = False
            for idx, bar in tw_p2.iterrows():
                if time(11, 30) <= bar['time'] <= time(13, 30):
                    continue
                if f_dir == 0:
                    if bar['close'] > ib_high: f_dir = 1; b_ext = bar['high']
                    elif bar['close'] < ib_low: f_dir = -1; b_ext = bar['low']
                else:
                    if f_dir == 1:
                        b_ext = max(b_ext, bar['high'])
                        wave = ((b_ext - ib_high)/ib_high)*10000.0
                        if wave >= 5.0 and bar['time'] >= time(10, 30) and not p2_done:
                            fib382 = b_ext - 0.382 * (b_ext - ib_high)
                            valid_bull = [f for f in active_fvgs if f['type'] == 'Bull' and not f['inverted'] and f['time'] <= bar['time']]
                            if valid_bull and bar['low'] <= fib382 and bar['close'] >= fib382 and bar['close'] > ib_mid:
                                entry = bar['close']
                                sl = entry - min(entry - ib_low, entry * 0.0012)
                                tp1 = entry + entry * 0.0010
                                tp2 = entry + entry * 0.0025
                                fwd = day_1m.loc[idx:][1:]
                                pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                                p2_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                                p2_done = True
                                break
                    elif f_dir == -1:
                        b_ext = min(b_ext, bar['low'])
                        wave = ((ib_low - b_ext)/ib_low)*10000.0
                        if wave >= 5.0 and bar['time'] >= time(10, 30) and not p2_done:
                            fib382 = b_ext + 0.382 * (ib_low - b_ext)
                            valid_bear = [f for f in active_fvgs if f['type'] == 'Bear' and not f['inverted'] and f['time'] <= bar['time']]
                            if valid_bear and bar['high'] >= fib382 and bar['close'] <= fib382 and bar['close'] < ib_mid:
                                entry = bar['close']
                                sl = entry + min(ib_high - entry, entry * 0.0012)
                                tp1 = entry - entry * 0.0010
                                tp2 = entry - entry * 0.0025
                                fwd = day_1m.loc[idx:][1:]
                                pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                                p2_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                                p2_done = True
                                break

            # -------------------------------------------------------------
            # PLAY 3: iFVG SWEEP FADE BOT (11:30 - 15:50)
            # -------------------------------------------------------------
            tw_p3 = day_1m[(day_1m['time'] >= time(11, 30)) & (day_1m['time'] <= time(15, 50))]
            p3_done = False
            for idx, bar in tw_p3.iterrows():
                # Inversion FVG Check:
                # Bullish FVG that inverted (closed below) -> Respected as Resistance for Short Fade
                for f in active_fvgs:
                    if f['type'] == 'Bull' and bar['close'] < f['bottom']:
                        f['inverted'] = True
                    elif f['type'] == 'Bear' and bar['close'] > f['top']:
                        f['inverted'] = True

                inv_bull = [f for f in active_fvgs if f['type'] == 'Bull' and f['inverted'] and f['time'] <= bar['time']]
                if inv_bull and not p3_done:
                    latest = inv_bull[-1]
                    if bar['high'] >= latest['bottom'] and bar['close'] <= latest['top'] and bar['close'] < ib_mid:
                        entry = bar['close']
                        sl = latest['top'] + (entry * 0.0003)
                        tp1 = ib_low
                        tp2 = ib_low - (entry * 0.0015)
                        fwd = day_1m.loc[idx:][1:]
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                        p3_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                        p3_done = True
                        break

                inv_bear = [f for f in active_fvgs if f['type'] == 'Bear' and f['inverted'] and f['time'] <= bar['time']]
                if inv_bear and not p3_done:
                    latest = inv_bear[-1]
                    if bar['low'] <= latest['top'] and bar['close'] >= latest['bottom'] and bar['close'] > ib_mid:
                        entry = bar['close']
                        sl = latest['bottom'] - (entry * 0.0003)
                        tp1 = ib_high
                        tp2 = ib_high + (entry * 0.0015)
                        fwd = day_1m.loc[idx:][1:]
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                        p3_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                        p3_done = True
                        break

        return pd.DataFrame(p1_trades), pd.DataFrame(p2_trades), pd.DataFrame(p3_trades)

    # Execute for IS (2019-2023) and OOS (2024-2026)
    p1_is, p2_is, p3_is = simulate_unified_suite('2019-01-01', '2023-12-31')
    p1_oos, p2_oos, p3_oos = simulate_unified_suite('2024-01-01', '2026-08-05')

    def calc_metrics(res_df):
        if res_df.empty:
            return {'trades': 0, 'wr': 0.0, 'pf': 0.0, 'net_bps': 0.0, 'max_dd_bps': 0.0}
        wins = res_df[res_df['win']]
        losses = res_df[~res_df['win']]
        gw = wins['pnl_bps'].sum()
        gl = abs(losses['pnl_bps'].sum())
        pf = gw / gl if gl > 0 else 99.0
        wr = (len(wins) / len(res_df)) * 100.0
        net = res_df['pnl_bps'].sum()
        cum = res_df['pnl_bps'].cumsum()
        max_dd = abs((cum - cum.cummax()).min()) if not cum.empty else 0.0
        return {'trades': len(res_df), 'wr': wr, 'pf': pf, 'net_bps': net, 'max_dd_bps': max_dd}

    summary = []
    for name, df_is_res, df_oos_res in [
        ('Play 1 Breakout (Unified Confluence)', p1_is, p1_oos),
        ('Play 2 Fib Retest (Unified Confluence)', p2_is, p2_oos),
        ('Play 3 iFVG Fade (Unified Confluence)', p3_is, p3_oos)
    ]:
        m_is = calc_metrics(df_is_res)
        m_oos = calc_metrics(df_oos_res)
        ratio = m_oos['pf'] / m_is['pf'] if m_is['pf'] > 0 else 0.0
        summary.append({
            'Strategy': name,
            'IS_Trades': m_is['trades'], 'IS_WR': m_is['wr'], 'IS_PF': m_is['pf'], 'IS_Net': m_is['net_bps'], 'IS_MaxDD': m_is['max_dd_bps'],
            'OOS_Trades': m_oos['trades'], 'OOS_WR': m_oos['wr'], 'OOS_PF': m_oos['pf'], 'OOS_Net': m_oos['net_bps'], 'OOS_MaxDD': m_oos['max_dd_bps'],
            'Stability_Ratio': ratio
        })

    sum_df = pd.DataFrame(summary)
    print('\n' + '='*95)
    print(f'UNIFIED CONFLUENCE IS vs. OOS PERFORMANCE MATRIX: {ticker}')
    print('='*95)
    for _, r in sum_df.iterrows():
        print(f"\n[{r['Strategy']}]")
        print(f"  IN-SAMPLE (2019-2023):      Trades: {r['IS_Trades']:4d} | WR: {r['IS_WR']:5.1f}% | PF: {r['IS_PF']:5.2f} | Net: {r['IS_Net']:+8.1f} bps | MaxDD: {r['IS_MaxDD']:6.1f} bps")
        print(f"  OUT-OF-SAMPLE (2024-2026):  Trades: {r['OOS_Trades']:4d} | WR: {r['OOS_WR']:5.1f}% | PF: {r['OOS_PF']:5.2f} | Net: {r['OOS_Net']:+8.1f} bps | MaxDD: {r['OOS_MaxDD']:6.1f} bps")
        print(f"  OOS/IS Stability Ratio:     {r['Stability_Ratio']:.2f}x")

    return sum_df

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
    run_study('NQ1')
    run_study('ES1')
