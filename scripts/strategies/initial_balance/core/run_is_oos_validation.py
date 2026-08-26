"""
Comprehensive In-Sample (IS) vs. Out-of-Sample (OOS) Validation Engine
Initial Balance Strategy Suite (Play 1 Breakout, Play 2 Retest, Play 3 Fade)
Universal Basis Points & Pack Trading Standards.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta

# Ensure project root is in sys.path
_root = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

def run_is_oos_study(ticker: str = 'NQ1', is_start: str = '2019-01-01', is_end: str = '2023-12-31', oos_start: str = '2024-01-01', oos_end: str = '2026-08-05'):
    print('='*90)
    print(f'IN-SAMPLE (IS) vs. OUT-OF-SAMPLE (OOS) VALIDATION STUDY: {ticker}')
    print(f'In-Sample Period:     {is_start} to {is_end} (5 Years)')
    print(f'Out-of-Sample Period: {oos_start} to {oos_end} (2.5+ Years)')
    print('='*90)

    # 1. Load Data
    data_path = Path(f'data/{ticker}_1m.parquet')
    if not data_path.exists():
        print(f'[ERROR] {data_path} not found.')
        return

    print(f'[INFO] Loading {data_path}...')
    df = pd.read_parquet(data_path)
    df = df.sort_index()

    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        df.index = df.index.tz_convert('America/New_York')

    # Add bar time attributes
    df['time'] = df.index.time
    df['date'] = df.index.date
    df['bar_high'] = df['high']
    df['bar_low'] = df['low']
    df['bar_close'] = df['close']
    df['bar_open'] = df['open']

    # Filter to overall study window
    df_study = df[(df.index >= is_start) & (df.index <= oos_end)].copy()
    print(f'[INFO] Total Study Bars: {len(df_study):,d} bars ({df_study.index.min().date()} to {df_study.index.max().date()})')

    # 2. Extract Sessions & IB (09:30 - 10:00 ET)
    # Identify RTH bars
    rth_bars = df_study[(df_study['time'] >= time(9, 30)) & (df_study['time'] < time(16, 0))].copy()
    
    # Compute daily IB (09:30 - 10:00)
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

    # Compute Daily ATR (14-day rolling)
    daily_bars = df_study.groupby('date').agg(
        d_high=('high', 'max'),
        d_low=('low', 'min'),
        d_close=('close', 'last')
    )
    daily_bars['tr'] = np.maximum(
        daily_bars['d_high'] - daily_bars['d_low'],
        np.maximum(
            (daily_bars['d_high'] - daily_bars['d_close'].shift(1)).abs(),
            (daily_bars['d_low'] - daily_bars['d_close'].shift(1)).abs()
        )
    )
    daily_bars['atr14'] = daily_bars['tr'].rolling(14).mean()
    ib_daily = ib_daily.join(daily_bars['atr14'])
    ib_daily['ib_atr_ratio'] = ib_daily['ib_range'] / ib_daily['atr14']

    print(f'[INFO] Extracted {len(ib_daily):,d} daily trading sessions.')

    # 3. Simulate Strategies across IS and OOS
    def simulate_play1_breakout(df_subset, ib_df, use_pack_trading=True, max_sl_bps=12.0, tp1_bps=10.0, tp2_bps=25.0, start_time_str='10:15'):
        # Play 1 Breakout Simulation
        trades = []
        start_t = datetime.strptime(start_time_str, '%H:%M').time()
        
        for d, ib_row in ib_df.iterrows():
            if pd.isna(ib_row['ib_range']) or ib_row['ib_range'] <= 0:
                continue
            
            day_data = df_subset[df_subset['date'] == d]
            if day_data.empty:
                continue
                
            trade_window = day_data[(day_data['time'] >= start_t) & (day_data['time'] <= time(15, 30))]
            if trade_window.empty:
                continue
                
            ib_high = ib_row['ib_high']
            ib_low = ib_row['ib_low']
            
            long_entered = False
            short_entered = False
            
            for idx, bar in trade_window.iterrows():
                # Avoid lunch hour (11:30 - 13:30)
                if time(11, 30) <= bar['time'] <= time(13, 30):
                    continue
                    
                # Long Breakout
                if not long_entered and bar['close'] > ib_high:
                    entry_price = bar['close']
                    sl_dist = min(entry_price - ib_low, entry_price * (max_sl_bps * 0.0001))
                    sl_price = entry_price - sl_dist
                    tp1_price = entry_price + entry_price * (tp1_bps * 0.0001)
                    tp2_price = entry_price + entry_price * (tp2_bps * 0.0001)
                    
                    # Track post-entry forward path
                    fwd_data = day_data.loc[idx:][1:]
                    pnl_bps, win, mfe_bps, mae_bps = evaluate_trade(fwd_data, entry_price, sl_price, tp1_price, tp2_price, 1, use_pack_trading)
                    trades.append({'date': d, 'time': bar['time'], 'dir': 'Long', 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'mae_bps': mae_bps})
                    long_entered = True
                    break
                    
                # Short Breakout
                elif not short_entered and bar['close'] < ib_low:
                    entry_price = bar['close']
                    sl_dist = min(ib_high - entry_price, entry_price * (max_sl_bps * 0.0001))
                    sl_price = entry_price + sl_dist
                    tp1_price = entry_price - entry_price * (tp1_bps * 0.0001)
                    tp2_price = entry_price - entry_price * (tp2_bps * 0.0001)
                    
                    fwd_data = day_data.loc[idx:][1:]
                    pnl_bps, win, mfe_bps, mae_bps = evaluate_trade(fwd_data, entry_price, sl_price, tp1_price, tp2_price, -1, use_pack_trading)
                    trades.append({'date': d, 'time': bar['time'], 'dir': 'Short', 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'mae_bps': mae_bps})
                    short_entered = True
                    break
                    
        return pd.DataFrame(trades)

    def simulate_play2_retest(df_subset, ib_df, use_pack_trading=True, max_sl_bps=12.0, tp1_bps=10.0, tp2_bps=25.0, min_wave_bps=5.0):
        # Play 2 Fib 38.2% Retest Simulation
        trades = []
        for d, ib_row in ib_df.iterrows():
            if pd.isna(ib_row['ib_range']) or ib_row['ib_range'] <= 0:
                continue
                
            day_data = df_subset[df_subset['date'] == d]
            if day_data.empty:
                continue
                
            trade_window = day_data[(day_data['time'] >= time(10, 0)) & (day_data['time'] <= time(15, 30))]
            if trade_window.empty:
                continue
                
            ib_high = ib_row['ib_high']
            ib_low = ib_row['ib_low']
            ib_mid = ib_row['ib_mid']
            
            first_break_dir = 0
            breakout_extreme = 0.0
            trade_taken = False
            
            for idx, bar in trade_window.iterrows():
                # Avoid lunch hour
                if time(11, 30) <= bar['time'] <= time(13, 30):
                    continue
                    
                if first_break_dir == 0:
                    if bar['close'] > ib_high:
                        first_break_dir = 1
                        breakout_extreme = bar['high']
                    elif bar['close'] < ib_low:
                        first_break_dir = -1
                        breakout_extreme = bar['low']
                else:
                    if first_break_dir == 1:
                        breakout_extreme = max(breakout_extreme, bar['high'])
                        wave_bps = ((breakout_extreme - ib_high) / ib_high) * 10000.0
                        if wave_bps >= min_wave_bps:
                            fib382 = breakout_extreme - 0.382 * (breakout_extreme - ib_high)
                            if bar['low'] <= fib382 and bar['close'] >= fib382 and not trade_taken:
                                entry_price = bar['close']
                                sl_dist = min(entry_price - ib_low, entry_price * (max_sl_bps * 0.0001))
                                sl_price = entry_price - sl_dist
                                tp1_price = entry_price + entry_price * (tp1_bps * 0.0001)
                                tp2_price = entry_price + entry_price * (tp2_bps * 0.0001)
                                
                                fwd_data = day_data.loc[idx:][1:]
                                pnl_bps, win, mfe_bps, mae_bps = evaluate_trade(fwd_data, entry_price, sl_price, tp1_price, tp2_price, 1, use_pack_trading)
                                trades.append({'date': d, 'time': bar['time'], 'dir': 'Long', 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'mae_bps': mae_bps})
                                trade_taken = True
                                break
                    elif first_break_dir == -1:
                        breakout_extreme = min(breakout_extreme, bar['low'])
                        wave_bps = ((ib_low - breakout_extreme) / ib_low) * 10000.0
                        if wave_bps >= min_wave_bps:
                            fib382 = breakout_extreme + 0.382 * (ib_low - breakout_extreme)
                            if bar['high'] >= fib382 and bar['close'] <= fib382 and not trade_taken:
                                entry_price = bar['close']
                                sl_dist = min(ib_high - entry_price, entry_price * (max_sl_bps * 0.0001))
                                sl_price = entry_price + sl_dist
                                tp1_price = entry_price - entry_price * (tp1_bps * 0.0001)
                                tp2_price = entry_price - entry_price * (tp2_bps * 0.0001)
                                
                                fwd_data = day_data.loc[idx:][1:]
                                pnl_bps, win, mfe_bps, mae_bps = evaluate_trade(fwd_data, entry_price, sl_price, tp1_price, tp2_price, -1, use_pack_trading)
                                trades.append({'date': d, 'time': bar['time'], 'dir': 'Short', 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'mae_bps': mae_bps})
                                trade_taken = True
                                break
        return pd.DataFrame(trades)

    def simulate_play3_fade(df_subset, ib_df, max_compression_ratio=0.50):
        # Play 3 FVG Displacement Sweep Fade Simulation (11:30 - 15:50 ET)
        trades = []
        for d, ib_row in ib_df.iterrows():
            if pd.isna(ib_row['ib_range']) or ib_row['ib_range'] <= 0:
                continue
            if pd.isna(ib_row['ib_atr_ratio']) or ib_row['ib_atr_ratio'] > max_compression_ratio:
                continue # Skip non-compressed days (mean reversion edge requires compression)
                
            day_data = df_subset[df_subset['date'] == d]
            if day_data.empty:
                continue
                
            trade_window = day_data[(day_data['time'] >= time(11, 30)) & (day_data['time'] <= time(15, 50))]
            if trade_window.empty:
                continue
                
            ib_high = ib_row['ib_high']
            ib_low = ib_row['ib_low']
            ib_mid = ib_row['ib_mid']
            
            sweep_high = False
            sweep_low = False
            trade_taken = False
            
            for idx, bar in trade_window.iterrows():
                if not sweep_high and bar['high'] > ib_high:
                    sweep_high = True
                if not sweep_low and bar['low'] < ib_low:
                    sweep_low = True
                    
                # Short Fade: Swept high, closed back inside IB
                if sweep_high and bar['close'] < ib_high and not trade_taken:
                    entry_price = bar['close']
                    sl_price = bar['high'] + entry_price * 0.0003 # 3 ticks above wick
                    tp1_price = ib_mid # Scale out 50% at midpoint
                    tp2_price = ib_low # Runner to opposite boundary
                    
                    fwd_data = day_data.loc[idx:][1:]
                    pnl_bps, win, mfe_bps, mae_bps = evaluate_trade(fwd_data, entry_price, sl_price, tp1_price, tp2_price, -1, True)
                    trades.append({'date': d, 'time': bar['time'], 'dir': 'Short', 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'mae_bps': mae_bps})
                    trade_taken = True
                    break
                    
                # Long Fade: Swept low, closed back inside IB
                elif sweep_low and bar['close'] > ib_low and not trade_taken:
                    entry_price = bar['close']
                    sl_price = bar['low'] - entry_price * 0.0003
                    tp1_price = ib_mid
                    tp2_price = ib_high
                    
                    fwd_data = day_data.loc[idx:][1:]
                    pnl_bps, win, mfe_bps, mae_bps = evaluate_trade(fwd_data, entry_price, sl_price, tp1_price, tp2_price, 1, True)
                    trades.append({'date': d, 'time': bar['time'], 'dir': 'Long', 'pnl_bps': pnl_bps, 'win': win, 'mfe_bps': mfe_bps, 'mae_bps': mae_bps})
                    trade_taken = True
                    break
                    
        return pd.DataFrame(trades)

    def evaluate_trade(fwd_bars, entry, stop, tp1, tp2, direction, use_pack_trading):
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
                # Favorable / adverse excursions
                mfe_pts = max(mfe_pts, bar['high'] - entry)
                mae_pts = max(mae_pts, entry - bar['low'])
                
                # Check Stop Loss
                if bar['low'] <= curr_stop:
                    stopped = True
                    break
                    
                # Check TP1 (Cover The Queen)
                if not tp1_hit and bar['high'] >= tp1:
                    tp1_hit = True
                    if use_pack_trading:
                        curr_stop = entry # Move stop to Breakeven
                        
                # Check TP2 (Runner)
                if tp1_hit and bar['high'] >= tp2:
                    tp2_hit = True
                    break
            else:
                mfe_pts = max(mfe_pts, entry - bar['low'])
                mae_pts = max(mae_pts, bar['high'] - entry)
                
                if bar['high'] >= curr_stop:
                    stopped = True
                    break
                    
                if not tp1_hit and bar['low'] <= tp1:
                    tp1_hit = True
                    if use_pack_trading:
                        curr_stop = entry # Move stop to Breakeven
                        
                if tp1_hit and bar['low'] <= tp2:
                    tp2_hit = True
                    break
                    
        # Calculate Realized PnL in Basis Points (bps)
        entry_bps = entry * 0.0001
        mfe_bps = mfe_pts / entry_bps
        mae_bps = mae_pts / entry_bps
        
        if not use_pack_trading:
            if stopped:
                pnl_pts = -(abs(entry - stop))
                return (pnl_pts / entry_bps), False, mfe_bps, mae_bps
            elif tp1_hit:
                pnl_pts = abs(tp1 - entry)
                return (pnl_pts / entry_bps), True, mfe_bps, mae_bps
            else:
                last_p = fwd_bars.iloc[-1]['close']
                pnl_pts = (last_p - entry) * direction
                return (pnl_pts / entry_bps), pnl_pts > 0, mfe_bps, mae_bps
        else:
            # 2-Leg Pack Trading (50% Queen, 50% Runner)
            if stopped and not tp1_hit:
                # Full loss on both legs
                pnl_pts = -(abs(entry - stop))
                return (pnl_pts / entry_bps), False, mfe_bps, mae_bps
            elif stopped and tp1_hit:
                # Leg 1 won TP1, Leg 2 stopped at Breakeven
                leg1_pts = abs(tp1 - entry)
                leg2_pts = 0.0 # BE
                pnl_pts = (leg1_pts + leg2_pts) / 2.0
                return (pnl_pts / entry_bps), True, mfe_bps, mae_bps
            elif tp2_hit:
                # Both legs hit targets
                leg1_pts = abs(tp1 - entry)
                leg2_pts = abs(tp2 - entry)
                pnl_pts = (leg1_pts + leg2_pts) / 2.0
                return (pnl_pts / entry_bps), True, mfe_bps, mae_bps
            elif tp1_hit:
                # Queen hit, session closed before runner TP2
                last_p = fwd_bars.iloc[-1]['close']
                leg1_pts = abs(tp1 - entry)
                leg2_pts = (last_p - entry) * direction
                pnl_pts = (leg1_pts + max(0.0, leg2_pts)) / 2.0
                return (pnl_pts / entry_bps), True, mfe_bps, mae_bps
            else:
                last_p = fwd_bars.iloc[-1]['close']
                pnl_pts = (last_p - entry) * direction
                return (pnl_pts / entry_bps), pnl_pts > 0, mfe_bps, mae_bps

    # 4. Execute Analysis for IS and OOS
    results_summary = []

    for name, sim_fn in [
        ('Play 1 Breakout (Baseline)', lambda df_sub, ib_sub: simulate_play1_breakout(df_sub, ib_sub, use_pack_trading=False, max_sl_bps=50.0, tp1_bps=30.0, start_time_str='10:00')),
        ('Play 1 Breakout (Calibrated Pack Trading)', lambda df_sub, ib_sub: simulate_play1_breakout(df_sub, ib_sub, use_pack_trading=True, max_sl_bps=12.0, tp1_bps=10.0, tp2_bps=25.0, start_time_str='10:30')),
        ('Play 2 Retest (Baseline Mid)', lambda df_sub, ib_sub: simulate_play2_retest(df_sub, ib_sub, use_pack_trading=False, max_sl_bps=50.0, tp1_bps=30.0, min_wave_bps=0.0)),
        ('Play 2 Retest (Calibrated Fib 38.2% Pack)', lambda df_sub, ib_sub: simulate_play2_retest(df_sub, ib_sub, use_pack_trading=True, max_sl_bps=12.0, tp1_bps=10.0, tp2_bps=25.0, min_wave_bps=5.0)),
        ('Play 3 Sweep Fade (Calibrated FVG Compression)', lambda df_sub, ib_sub: simulate_play3_fade(df_sub, ib_sub, max_compression_ratio=0.50))
    ]:
        # In-Sample
        df_is = df_study[(df_study.index >= is_start) & (df_study.index <= is_end)]
        ib_is = ib_daily[(ib_daily.index >= pd.to_datetime(is_start).date()) & (ib_daily.index <= pd.to_datetime(is_end).date())]
        res_is = sim_fn(df_is, ib_is)
        
        # Out-of-Sample
        df_oos = df_study[(df_study.index >= oos_start) & (df_study.index <= oos_end)]
        ib_oos = ib_daily[(ib_daily.index >= pd.to_datetime(oos_start).date()) & (ib_daily.index <= pd.to_datetime(oos_end).date())]
        res_oos = sim_fn(df_oos, ib_oos)
        
        def calc_metrics(res_df):
            if res_df.empty:
                return {'trades': 0, 'wr': 0.0, 'pf': 0.0, 'net_bps': 0.0, 'avg_bps': 0.0, 'max_dd_bps': 0.0}
            wins = res_df[res_df['pnl_bps'] > 0]
            losses = res_df[res_df['pnl_bps'] < 0]
            gross_win = wins['pnl_bps'].sum()
            gross_loss = abs(losses['pnl_bps'].sum())
            pf = (gross_win / gross_loss) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
            wr = (len(wins) / len(res_df)) * 100.0
            net_bps = res_df['pnl_bps'].sum()
            avg_bps = res_df['pnl_bps'].mean()
            
            # Cumulative drawdown in bps
            cum_pnl = res_df['pnl_bps'].cumsum()
            high_water = cum_pnl.cummax()
            drawdown = cum_pnl - high_water
            max_dd_bps = abs(drawdown.min()) if not drawdown.empty else 0.0
            
            return {'trades': len(res_df), 'wr': wr, 'pf': pf, 'net_bps': net_bps, 'avg_bps': avg_bps, 'max_dd_bps': max_dd_bps}
            
        m_is = calc_metrics(res_is)
        m_oos = calc_metrics(res_oos)
        
        results_summary.append({
            'Strategy': name,
            'IS_Trades': m_is['trades'],
            'IS_WR': m_is['wr'],
            'IS_PF': m_is['pf'],
            'IS_Net_bps': m_is['net_bps'],
            'IS_MaxDD_bps': m_is['max_dd_bps'],
            'OOS_Trades': m_oos['trades'],
            'OOS_WR': m_oos['wr'],
            'OOS_PF': m_oos['pf'],
            'OOS_Net_bps': m_oos['net_bps'],
            'OOS_MaxDD_bps': m_oos['max_dd_bps'],
            'OOS_IS_PF_Ratio': (m_oos['pf'] / m_is['pf']) if m_is['pf'] > 0 else 0.0
        })

    summary_df = pd.DataFrame(results_summary)
    
    print('\n' + '='*90)
    print('IS vs. OOS COMPREHENSIVE PERFORMANCE MATRIX')
    print('='*90)
    
    for idx, r in summary_df.iterrows():
        print(f"\n[{r['Strategy']}]")
        print(f"  IN-SAMPLE (2019-2023):      Trades: {r['IS_Trades']:4d} | WR: {r['IS_WR']:5.1f}% | PF: {r['IS_PF']:5.2f} | Net: {r['IS_Net_bps']:+8.1f} bps | MaxDD: {r['IS_MaxDD_bps']:6.1f} bps")
        print(f"  OUT-OF-SAMPLE (2024-2026):  Trades: {r['OOS_Trades']:4d} | WR: {r['OOS_WR']:5.1f}% | PF: {r['OOS_PF']:5.2f} | Net: {r['OOS_Net_bps']:+8.1f} bps | MaxDD: {r['OOS_MaxDD_bps']:6.1f} bps")
        print(f"  OOS/IS Stability Ratio:     {r['OOS_IS_PF_Ratio']:.2f}x")

    # Export to CSV
    out_path = Path('scripts/strategies/initial_balance/data/is_oos_study_results.csv')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(out_path, index=False)
    print(f'\n[SUCCESS] IS/OOS matrix saved to {out_path}')
    return summary_df

if __name__ == '__main__':
    run_is_oos_study('NQ1')
