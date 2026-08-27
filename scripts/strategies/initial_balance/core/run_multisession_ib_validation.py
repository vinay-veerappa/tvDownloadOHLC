"""
Universal Multi-Session & Any Time-Based Range Backtest Engine
Supports:
- NY RTH Open (09:30 - 10:00 ET, Session 09:30 - 16:00 ET)
- London Open (03:00 - 03:30 ET, Session 03:00 - 11:30 ET)
- Tokyo / Asia Open (19:30 - 20:00 ET, Session 18:00 - 02:00 ET)
- Globex Open (18:00 - 18:30 ET, Session 18:00 - 09:00 ET)
- Custom Arbitrary Time-Based Ranges
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

class MultiSessionIBEngine:
    def __init__(self, ticker='NQ1'):
        self.ticker = ticker
        data_path = Path(f'data/{ticker}_1m.parquet')
        if not data_path.exists():
            raise FileNotFoundError(f'{data_path} not found')

        print(f'[INFO] Loading {ticker} continuous 1m data...')
        self.df = pd.read_parquet(data_path)
        self.df = self.df.sort_index()
        if self.df.index.tz is None:
            self.df.index = self.df.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
            self.df.index = self.df.index.tz_convert('America/New_York')

        self.df['time'] = self.df.index.time
        self.df['date'] = self.df.index.date
        # Filter to 2019-2026
        self.df = self.df[(self.df.index >= '2019-01-01') & (self.df.index <= '2026-08-05')].copy()

        # Resample 5m
        self.df_5m = self.df.resample('5min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
        self.df_5m['time'] = self.df_5m.index.time
        self.df_5m['date'] = self.df_5m.index.date

    def run_session_backtest(self, session_name, range_start_str, range_end_str, session_end_str, is_overnight=False):
        print('\n' + '='*95)
        print(f'MULTI-SESSION BACKTEST: {self.ticker} | Session: {session_name}')
        print(f'Range Window:   {range_start_str} - {range_end_str} ET')
        print(f'Session Window: {range_start_str} - {session_end_str} ET (Overnight: {is_overnight})')
        print('='*95)

        r_start = datetime.strptime(range_start_str, '%H:%M').time()
        r_end = datetime.strptime(range_end_str, '%H:%M').time()
        s_end = datetime.strptime(session_end_str, '%H:%M').time()

        # Extract sessions
        # For each day/session, extract range bars and trading window bars
        all_dates = sorted(self.df['date'].unique())
        
        p1_trades = []
        p2_trades = []
        p3_trades = []

        for i, d in enumerate(all_dates):
            if not is_overnight:
                day_bars = self.df[self.df['date'] == d]
                day_5m = self.df_5m[self.df_5m['date'] == d]
                if day_bars.empty or len(day_5m) < 6: continue
                
                # Range bars
                r_bars = day_bars[(day_bars['time'] >= r_start) & (day_bars['time'] < r_end)]
                trade_bars = day_bars[(day_bars['time'] >= r_end) & (day_bars['time'] <= s_end)]
                post_5m = day_5m[(day_5m['time'] >= r_end) & (day_5m['time'] <= s_end)]
            else:
                # Overnight session spans d to d+1
                if i >= len(all_dates) - 1: break
                next_d = all_dates[i+1]
                sess_bars = self.df[((self.df['date'] == d) & (self.df['time'] >= r_start)) | ((self.df['date'] == next_d) & (self.df['time'] <= s_end))]
                sess_5m = self.df_5m[((self.df_5m['date'] == d) & (self.df_5m['time'] >= r_start)) | ((self.df_5m['date'] == next_d) & (self.df_5m['time'] <= s_end))]
                if sess_bars.empty or len(sess_5m) < 6: continue
                
                r_bars = sess_bars[(sess_bars['date'] == d) & (sess_bars['time'] >= r_start) & (sess_bars['time'] < r_end)]
                trade_bars = sess_bars[~((sess_bars['date'] == d) & (sess_bars['time'] < r_end))]
                post_5m = sess_5m[~((sess_5m['date'] == d) & (sess_5m['time'] < r_end))]

            if r_bars.empty or trade_bars.empty: continue

            r_high = r_bars['high'].max()
            r_low = r_bars['low'].min()
            r_mid = (r_high + r_low) / 2.0
            r_range = r_high - r_low
            if r_range <= 0: continue

            # Detect 5m FVGs in trade window
            active_fvgs = []
            for j in range(2, len(post_5m)):
                b0 = post_5m.iloc[j-2]; b2 = post_5m.iloc[j]
                if b2['low'] > b0['high'] + (b0['high'] * 0.0002):
                    active_fvgs.append({'type': 'Bull', 'top': b2['low'], 'bottom': b0['high'], 'time': b2['time'], 'inverted': False})
                elif b2['high'] < b0['low'] - (b0['low'] * 0.0002):
                    active_fvgs.append({'type': 'Bear', 'top': b0['low'], 'bottom': b2['high'], 'time': b2['time'], 'inverted': False})

            # Play 1 Breakout
            p1_done = False
            for idx, bar in trade_bars.iterrows():
                valid_bull = [f for f in active_fvgs if f['type'] == 'Bull' and not f['inverted'] and f['time'] <= bar['time']]
                if valid_bull and bar['close'] > r_high and bar['close'] > r_mid and not p1_done:
                    entry = bar['close']
                    sl = entry - min(entry - r_low, entry * 0.0012)
                    tp1 = entry + entry * 0.0010
                    tp2 = entry + entry * 0.0025
                    fwd = trade_bars.loc[idx:][1:]
                    pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                    p1_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                    p1_done = True
                    break
                valid_bear = [f for f in active_fvgs if f['type'] == 'Bear' and not f['inverted'] and f['time'] <= bar['time']]
                if valid_bear and bar['close'] < r_low and bar['close'] < r_mid and not p1_done:
                    entry = bar['close']
                    sl = entry + min(r_high - entry, entry * 0.0012)
                    tp1 = entry - entry * 0.0010
                    tp2 = entry - entry * 0.0025
                    fwd = trade_bars.loc[idx:][1:]
                    pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                    p1_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                    p1_done = True
                    break

            # Play 2 Fib 38.2% Retest
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
                                pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                                p2_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
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
                                pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                                p2_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                                p2_done = True
                                break

            # Play 3 iFVG Sweep Fade
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
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, -1)
                        p3_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
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
                        pnl, win, mfe, mae = eval_pack(fwd, entry, sl, tp1, tp2, 1)
                        p3_trades.append({'date': d, 'pnl_bps': pnl, 'win': win, 'mfe_bps': mfe, 'mae_bps': mae})
                        p3_done = True
                        break

        def report(name, t_list):
            if not t_list:
                print(f"  {name:30s} | No trades")
                return
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
            print(f"  {name:32s} | Trades: {len(df_t):4d} | WR: {wr:5.1f}% | PF: {pf:5.2f} | Net: {net:+8.1f} bps | MaxDD: {max_dd:5.1f} bps")

        report("Play 1: Breakout", p1_trades)
        report("Play 2: Fib Retest", p2_trades)
        report("Play 3: iFVG Sweep Fade", p3_trades)

def eval_pack(fwd_bars, entry, stop, tp1, tp2, direction):
    if fwd_bars.empty: return 0.0, False, 0.0, 0.0
    tp1_hit = False; tp2_hit = False; stopped = False; curr_stop = stop
    mfe_pts = 0.0; mae_pts = 0.0
    for _, bar in fwd_bars.iterrows():
        if direction == 1:
            mfe_pts = max(mfe_pts, bar['high'] - entry)
            mae_pts = max(mae_pts, entry - bar['low'])
            if bar['low'] <= curr_stop: stopped = True; break
            if not tp1_hit and bar['high'] >= tp1: tp1_hit = True; curr_stop = entry
            if tp1_hit and bar['high'] >= tp2: tp2_hit = True; break
        else:
            mfe_pts = max(mfe_pts, entry - bar['low'])
            mae_pts = max(mae_pts, bar['high'] - entry)
            if bar['high'] >= curr_stop: stopped = True; break
            if not tp1_hit and bar['low'] <= tp1: tp1_hit = True; curr_stop = entry
            if tp1_hit and bar['low'] <= tp2: tp2_hit = True; break
    entry_bps = entry * 0.0001
    mfe_bps = mfe_pts / entry_bps; mae_bps = mae_pts / entry_bps
    if stopped and not tp1_hit: return -(abs(entry - stop) / entry_bps), False, mfe_bps, mae_bps
    elif stopped and tp1_hit: return (abs(tp1 - entry) / entry_bps) / 2.0, True, mfe_bps, mae_bps
    elif tp2_hit: return ((abs(tp1 - entry) + abs(tp2 - entry)) / 2.0) / entry_bps, True, mfe_bps, mae_bps
    else:
        last_p = fwd_bars.iloc[-1]['close']
        pnl = ((last_p - entry) * direction) / entry_bps
        return pnl, pnl > 0, mfe_bps, mae_bps

if __name__ == '__main__':
    engine = MultiSessionIBEngine('NQ1')
    
    # 1. NY RTH Open (09:30 - 10:00 ET)
    engine.run_session_backtest('NY RTH Open', '09:30', '10:00', '16:00', is_overnight=False)
    
    # 2. London Open (03:00 - 03:30 ET)
    engine.run_session_backtest('London Open', '03:00', '03:30', '11:30', is_overnight=False)
    
    # 3. Tokyo / Asia Open (19:30 - 20:00 ET / 09:30 JST)
    engine.run_session_backtest('Tokyo / Asia Open', '19:30', '20:00', '02:00', is_overnight=True)
    
    # 4. Globex Open (18:00 - 18:30 ET)
    engine.run_session_backtest('Globex Overnight Open', '18:00', '18:30', '09:00', is_overnight=True)
