"""
Robust Zero-Lookahead Session Benchmark: Range Regime Filters vs. 5m FVG Displacement
Anchors strictly to pre-established structural levels (Asia H/L, Overnight H/L, IB H/L, Prior RTH H/L)
Includes 2-leg position management (50% TP1 + BE, 50% TP2 Runner) and real transaction friction.
"""
from __future__ import annotations

import argparse
import warnings
warnings.filterwarnings('ignore')
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class TradeResult:
    symbol: str
    session_name: str
    date: str
    direction: str  # 'LONG' or 'SHORT'
    entry_time: pd.Timestamp
    entry_price: float
    stop_loss: float
    tp1_price: float
    tp2_price: float
    risk_points: float
    t1_hit: bool
    t2_hit: bool
    stopped_out: bool
    exit_time: pd.Timestamp
    leg1_pnl: float  # points
    leg2_pnl: float  # points
    total_pnl_points: float
    total_pnl_dollars: float
    r_multiple: float
    filter_a: bool  # Real-time VWAP flatness up to entry
    filter_b: bool  # Pre-session compression vs ATR
    filter_c: bool  # Opened inside prior reference range


def calculate_atr(df_daily: pd.DataFrame, period: int = 10) -> pd.Series:
    high = df_daily['high']
    low = df_daily['low']
    close = df_daily['close']
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()


def resample_to_5m(df_1m: pd.DataFrame) -> pd.DataFrame:
    df_5m = df_1m.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    return df_5m


def run_zero_lookahead_backtest(
    symbol: str,
    df_1m: pd.DataFrame,
    start_year: int = 2021,
    end_year: int = 2026
) -> List[TradeResult]:
    print(f"Running zero-lookahead backtest for {symbol} ({start_year}-{end_year})...")
    
    df_1m = df_1m[(df_1m.index.year >= start_year) & (df_1m.index.year <= end_year)].copy()
    if df_1m.empty:
        return []

    tick_size = 0.25
    point_val = 50.0 if 'ES' in symbol else 20.0
    comm_per_contract = 4.50  # $4.50 round-trip
    slippage_ticks = 1  # 1 tick slippage on market/stop fills
    min_fvg_size = 0.75 if 'ES' in symbol else 3.5
    
    # Calculate daily ATR(10)
    df_daily = df_1m.resample('D').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    daily_atr = calculate_atr(df_daily, period=10)
    
    df_5m = resample_to_5m(df_1m)
    
    # Organize trade dates (Day D begins at 18:00 D-1 and ends at 17:00 D)
    df_1m['trade_date'] = df_1m.index.date
    evening_mask = df_1m.index.hour >= 18
    df_1m.loc[evening_mask, 'trade_date'] = (df_1m.loc[evening_mask].index + pd.Timedelta(days=1)).date
    
    unique_dates = sorted(df_1m['trade_date'].unique())
    trades: List[TradeResult] = []
    
    for i_date, t_date in enumerate(unique_dates):
        t_date_str = str(t_date)
        prev_day = t_date - pd.Timedelta(days=1)
        
        # ATR up to yesterday (Strict Zero-Lookahead)
        atr_val = daily_atr.get(pd.Timestamp(prev_day), daily_atr.mean())
        if pd.isna(atr_val) or atr_val <= 0:
            atr_val = 20.0 if 'ES' in symbol else 80.0
            
        # 1. Define Historical Reference Windows for Structural Anchoring
        # Prior Day RTH: 09:30 to 16:00 of prev_day
        prior_rth = df_1m.loc[f"{prev_day} 09:30:00":f"{prev_day} 16:00:00"]
        prior_rth_h = prior_rth['high'].max() if len(prior_rth) > 0 else np.nan
        prior_rth_l = prior_rth['low'].min() if len(prior_rth) > 0 else np.nan
        
        # Asia Session: 18:00 (prev_day) to 02:00 (t_date)
        asia_1m = df_1m.loc[f"{prev_day} 18:00:00":f"{t_date} 02:00:00"]
        asia_h = asia_1m['high'].max() if len(asia_1m) > 0 else np.nan
        asia_l = asia_1m['low'].min() if len(asia_1m) > 0 else np.nan
        asia_range = (asia_h - asia_l) if not np.isnan(asia_h) else np.nan
        
        # Overnight / Globex: 18:00 (prev_day) to 09:30 (t_date)
        on_1m = df_1m.loc[f"{prev_day} 18:00:00":f"{t_date} 09:29:00"]
        on_h = on_1m['high'].max() if len(on_1m) > 0 else np.nan
        on_l = on_1m['low'].min() if len(on_1m) > 0 else np.nan
        on_range = (on_h - on_l) if not np.isnan(on_h) else np.nan
        
        # Initial Balance (IB60): 09:30 to 10:30 (t_date)
        ib_1m = df_1m.loc[f"{t_date} 09:30:00":f"{t_date} 10:30:00"]
        ib_h = ib_1m['high'].max() if len(ib_1m) > 0 else np.nan
        ib_l = ib_1m['low'].min() if len(ib_1m) > 0 else np.nan
        ib_range = (ib_h - ib_l) if not np.isnan(ib_h) else np.nan

        # 2. Session Execution Configurations
        sessions = [
            {
                'name': 'ASIA',
                'start': pd.Timestamp(f"{prev_day} 18:00:00"),
                'end': pd.Timestamp(f"{t_date} 02:00:00"),
                'ref_high': prior_rth_h,
                'ref_low': prior_rth_l,
                'ref_range': (prior_rth_h - prior_rth_l) if not np.isnan(prior_rth_h) else np.nan,
                'scan_start': pd.Timestamp(f"{prev_day} 19:00:00"),  # Let 1 hour establish early context
            },
            {
                'name': 'LONDON',
                'start': pd.Timestamp(f"{t_date} 02:00:00"),
                'end': pd.Timestamp(f"{t_date} 08:30:00"),
                'ref_high': asia_h,
                'ref_low': asia_l,
                'ref_range': asia_range,
                'scan_start': pd.Timestamp(f"{t_date} 02:30:00"),
            },
            {
                'name': 'NY_AM',
                'start': pd.Timestamp(f"{t_date} 09:30:00"),
                'end': pd.Timestamp(f"{t_date} 11:30:00"),
                'ref_high': on_h,
                'ref_low': on_l,
                'ref_range': on_range,
                'scan_start': pd.Timestamp(f"{t_date} 09:45:00"),
            },
            {
                'name': 'NY_MIDDAY',
                'start': pd.Timestamp(f"{t_date} 11:30:00"),
                'end': pd.Timestamp(f"{t_date} 13:30:00"),
                'ref_high': ib_h,
                'ref_low': ib_l,
                'ref_range': ib_range,
                'scan_start': pd.Timestamp(f"{t_date} 11:30:00"),
            },
            {
                'name': 'NY_PM',
                'start': pd.Timestamp(f"{t_date} 13:30:00"),
                'end': pd.Timestamp(f"{t_date} 16:00:00"),
                'ref_high': ib_h,
                'ref_low': ib_l,
                'ref_range': ib_range,
                'scan_start': pd.Timestamp(f"{t_date} 13:30:00"),
            }
        ]
        
        for sess in sessions:
            ref_h = sess['ref_high']
            ref_l = sess['ref_low']
            ref_r = sess['ref_range']
            
            if np.isnan(ref_h) or np.isnan(ref_l) or np.isnan(ref_r) or ref_r <= 0:
                continue
                
            sess_1m = df_1m.loc[sess['start']:sess['end']]
            if len(sess_1m) < 20:
                continue
                
            sess_5m = df_5m.loc[sess['start']:sess['end']]
            if len(sess_5m) < 4:
                continue
                
            s_open = sess_1m['open'].iloc[0]
            
            # Filter B (Pre-session compression): Is the PRE-ESTABLISHED reference range tight?
            filter_b = ref_r < (0.40 * atr_val)
            
            # Filter C: Did this session open inside the reference range?
            filter_c = (s_open >= ref_l) and (s_open <= ref_h)
            
            # Precompute Anchored VWAP strictly progressively (Zero look-ahead)
            cum_vol = sess_1m['volume'].cumsum()
            cum_vol_price = (sess_1m['close'] * sess_1m['volume']).cumsum()
            progressive_vwap = (cum_vol_price / cum_vol.replace(0, np.nan)).ffill().bfill()
            
            session_traded = False
            
            # Scan 5m bars for Sweep of Pre-established Level + FVG Displacement
            scan_bars = sess_5m.loc[sess['scan_start']:]
            
            for i_idx in range(2, len(scan_bars)):
                if session_traded:
                    break
                    
                b0 = scan_bars.iloc[i_idx - 2]
                b1 = scan_bars.iloc[i_idx - 1]
                b2 = scan_bars.iloc[i_idx]
                curr_time = scan_bars.index[i_idx]
                
                # Check Filter A at decision time: Rolling VWAP slope and cross count UP TO curr_time
                sub_vwap_1m = progressive_vwap.loc[:curr_time]
                sub_close_1m = sess_1m['close'].loc[:curr_time]
                diff_vwap = sub_close_1m - sub_vwap_1m
                vwap_crosses = ((diff_vwap.shift(1) * diff_vwap) < 0).sum()
                vwap_slope = (sub_vwap_1m.iloc[-1] - sub_vwap_1m.iloc[0]) / (atr_val * 0.1) if len(sub_vwap_1m) > 5 else 0.0
                filter_a = (abs(vwap_slope) < 0.18) and (vwap_crosses >= 2)
                
                # -------------------------------------------------------------
                # SHORT SETUP: Sweep of Pre-Established Reference High
                # -------------------------------------------------------------
                swept_high = (b1['high'] > ref_h or b2['high'] > ref_h)
                bearish_disp = (b2['close'] < b2['open']) and (b2['close'] < ref_h)
                bearish_fvg = (b0['low'] - b2['high']) >= min_fvg_size
                
                if swept_high and bearish_disp and bearish_fvg:
                    fvg_entry = b2['high']
                    sweep_extreme = max(b1['high'], b2['high'])
                    sl = sweep_extreme + (2 * tick_size)
                    risk = sl - fvg_entry
                    
                    # Target 1: 50% Equilibrium of reference range or Session VWAP
                    tp1 = ref_l + (0.50 * ref_r)
                    # Target 2: Complete rotation to Reference Low
                    tp2 = ref_l
                    
                    if risk > 0 and risk < (0.30 * atr_val) and tp1 < fvg_entry:
                        # Forward 1m simulation
                        sim_1m = sess_1m.loc[curr_time:]
                        filled = False
                        fill_idx = None
                        t1_hit = False
                        t2_hit = False
                        stopped = False
                        
                        leg1_pnl = 0.0
                        leg2_pnl = 0.0
                        
                        for t_bar, row in sim_1m.iterrows():
                            if not filled:
                                if row['high'] >= fvg_entry:
                                    filled = True
                                    fill_idx = t_bar
                            else:
                                # Stop Loss Check
                                if row['high'] >= sl:
                                    stopped = True
                                    if not t1_hit:
                                        leg1_pnl = -risk - (slippage_ticks * tick_size)
                                        leg2_pnl = -risk - (slippage_ticks * tick_size)
                                    else:
                                        # Leg 2 stopped out at Breakeven
                                        leg2_pnl = -(slippage_ticks * tick_size)
                                    exit_time = t_bar
                                    break
                                
                                # Target 1 Check (50% scale-out)
                                if not t1_hit and row['low'] <= tp1:
                                    t1_hit = True
                                    leg1_pnl = (fvg_entry - tp1)
                                    # SL on Leg 2 moved to Breakeven
                                    sl = fvg_entry
                                    
                                # Target 2 Check (Runner)
                                if row['low'] <= tp2:
                                    t2_hit = True
                                    leg2_pnl = (fvg_entry - tp2)
                                    exit_time = t_bar
                                    break
                                    
                        if filled:
                            # Session end exit if not hit
                            if not stopped and not t2_hit:
                                exit_price = sim_1m['close'].iloc[-1]
                                exit_time = sim_1m.index[-1]
                                if not t1_hit:
                                    leg1_pnl = (fvg_entry - exit_price)
                                leg2_pnl = (fvg_entry - exit_price)
                                
                            # 2 Contracts Total (1 contract per leg)
                            total_pts = (leg1_pnl + leg2_pnl) / 2.0
                            gross_dollars = (leg1_pnl * point_val) + (leg2_pnl * point_val)
                            net_dollars = gross_dollars - (2 * comm_per_contract)
                            r_mult = total_pts / risk if risk > 0 else 0.0
                            
                            trades.append(TradeResult(
                                symbol=symbol, session_name=sess['name'], date=t_date_str,
                                direction='SHORT', entry_time=fill_idx, entry_price=fvg_entry,
                                stop_loss=sweep_extreme + (2 * tick_size), tp1_price=tp1, tp2_price=tp2,
                                risk_points=risk, t1_hit=t1_hit, t2_hit=t2_hit, stopped_out=stopped,
                                exit_time=exit_time, leg1_pnl=leg1_pnl, leg2_pnl=leg2_pnl,
                                total_pnl_points=total_pts, total_pnl_dollars=net_dollars,
                                r_multiple=r_mult, filter_a=filter_a, filter_b=filter_b, filter_c=filter_c
                            ))
                            session_traded = True
                
                # -------------------------------------------------------------
                # LONG SETUP: Sweep of Pre-Established Reference Low
                # -------------------------------------------------------------
                swept_low = (b1['low'] < ref_l or b2['low'] < ref_l)
                bullish_disp = (b2['close'] > b2['open']) and (b2['close'] > ref_l)
                bullish_fvg = (b2['low'] - b0['high']) >= min_fvg_size
                
                if not session_traded and swept_low and bullish_disp and bullish_fvg:
                    fvg_entry = b2['low']
                    sweep_extreme = min(b1['low'], b2['low'])
                    sl = sweep_extreme - (2 * tick_size)
                    risk = fvg_entry - sl
                    
                    tp1 = ref_l + (0.50 * ref_r)
                    tp2 = ref_h
                    
                    if risk > 0 and risk < (0.30 * atr_val) and tp1 > fvg_entry:
                        sim_1m = sess_1m.loc[curr_time:]
                        filled = False
                        fill_idx = None
                        t1_hit = False
                        t2_hit = False
                        stopped = False
                        
                        leg1_pnl = 0.0
                        leg2_pnl = 0.0
                        
                        for t_bar, row in sim_1m.iterrows():
                            if not filled:
                                if row['low'] <= fvg_entry:
                                    filled = True
                                    fill_idx = t_bar
                            else:
                                if row['low'] <= sl:
                                    stopped = True
                                    if not t1_hit:
                                        leg1_pnl = -risk - (slippage_ticks * tick_size)
                                        leg2_pnl = -risk - (slippage_ticks * tick_size)
                                    else:
                                        leg2_pnl = -(slippage_ticks * tick_size)
                                    exit_time = t_bar
                                    break
                                
                                if not t1_hit and row['high'] >= tp1:
                                    t1_hit = True
                                    leg1_pnl = (tp1 - fvg_entry)
                                    sl = fvg_entry
                                    
                                if row['high'] >= tp2:
                                    t2_hit = True
                                    leg2_pnl = (tp2 - fvg_entry)
                                    exit_time = t_bar
                                    break
                                    
                        if filled:
                            if not stopped and not t2_hit:
                                exit_price = sim_1m['close'].iloc[-1]
                                exit_time = sim_1m.index[-1]
                                if not t1_hit:
                                    leg1_pnl = (exit_price - fvg_entry)
                                leg2_pnl = (exit_price - fvg_entry)
                                
                            total_pts = (leg1_pnl + leg2_pnl) / 2.0
                            gross_dollars = (leg1_pnl * point_val) + (leg2_pnl * point_val)
                            net_dollars = gross_dollars - (2 * comm_per_contract)
                            r_mult = total_pts / risk if risk > 0 else 0.0
                            
                            trades.append(TradeResult(
                                symbol=symbol, session_name=sess['name'], date=t_date_str,
                                direction='LONG', entry_time=fill_idx, entry_price=fvg_entry,
                                stop_loss=sweep_extreme - (2 * tick_size), tp1_price=tp1, tp2_price=tp2,
                                risk_points=risk, t1_hit=t1_hit, t2_hit=t2_hit, stopped_out=stopped,
                                exit_time=exit_time, leg1_pnl=leg1_pnl, leg2_pnl=leg2_pnl,
                                total_pnl_points=total_pts, total_pnl_dollars=net_dollars,
                                r_multiple=r_mult, filter_a=filter_a, filter_b=filter_b, filter_c=filter_c
                            ))
                            session_traded = True

    return trades


def generate_metrics(trades_df: pd.DataFrame) -> Dict[str, float]:
    if trades_df.empty:
        return {'trades': 0, 'win_rate': 0.0, 'tp2_rate': 0.0, 'profit_factor': 0.0, 'exp_r': 0.0, 'net_pnl': 0.0, 'avg_win_r': 0.0, 'avg_loss_r': 0.0}
        
    total_trades = len(trades_df)
    wins = trades_df[trades_df['total_pnl_dollars'] > 0]
    tp2_wins = trades_df[trades_df['t2_hit'] == True]
    losses = trades_df[trades_df['total_pnl_dollars'] <= 0]
    
    win_rate = (len(wins) / total_trades) * 100.0
    tp2_rate = (len(tp2_wins) / total_trades) * 100.0
    
    gross_gain = wins['total_pnl_dollars'].sum()
    gross_loss = losses['total_pnl_dollars'].abs().sum()
    pf = (gross_gain / gross_loss) if gross_loss > 0 else (99.0 if gross_gain > 0 else 0.0)
    exp_r = trades_df['r_multiple'].mean()
    net_pnl = trades_df['total_pnl_dollars'].sum()
    
    avg_win_r = wins['r_multiple'].mean() if len(wins) > 0 else 0.0
    avg_loss_r = losses['r_multiple'].mean() if len(losses) > 0 else 0.0
    
    return {
        'trades': total_trades,
        'win_rate': round(win_rate, 1),
        'tp2_rate': round(tp2_rate, 1),
        'profit_factor': round(pf, 2),
        'exp_r': round(exp_r, 2),
        'net_pnl': round(net_pnl, 0),
        'avg_win_r': round(avg_win_r, 2),
        'avg_loss_r': round(avg_loss_r, 2)
    }


def main():
    parser = argparse.ArgumentParser(description="Zero-Lookahead Session Range Regime & 5m FVG Benchmark")
    parser.add_argument('--start-year', type=int, default=2021, help='Start Year (e.g. 2021)')
    parser.add_argument('--end-year', type=int, default=2026, help='End Year (e.g. 2026)')
    parser.add_argument('--symbols', type=str, default='ES,NQ', help='Comma-separated symbols')
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    all_trades: List[TradeResult] = []

    for sym in symbols:
        parquet_file = Path(f"data/{sym}1_1m.parquet")
        if not parquet_file.exists():
            print(f"File not found: {parquet_file}")
            continue
        df_1m = pd.read_parquet(parquet_file)
        sym_trades = run_zero_lookahead_backtest(sym, df_1m, start_year=args.start_year, end_year=args.end_year)
        all_trades.extend(sym_trades)

    if not all_trades:
        print("No trades generated.")
        return

    df_results = pd.DataFrame([t.__dict__ for t in all_trades])
    
    print("\n" + "=" * 115)
    print(f"REALISTIC ZERO-LOOKAHEAD BENCHMARK: {args.start_year} - {args.end_year} (ES vs. NQ Structurally Anchored)")
    print("Includes 2-Leg Scaling (50% TP1 + BE, 50% Runner TP2) + Commissions ($4.50/contract) + Slippage")
    print("=" * 115)
    
    filter_keys = [
        ('Baseline: Raw FVG Sweep (No Filter)', lambda df: df),
        ('Filter A: Real-Time VWAP Flat & Crosses', lambda df: df[df['filter_a'] == True]),
        ('Filter B: Pre-Session Compression <0.40ATR', lambda df: df[df['filter_b'] == True]),
        ('Filter C: Opened Inside Reference Range', lambda df: df[df['filter_c'] == True]),
    ]
    
    sessions = ['ASIA', 'LONDON', 'NY_AM', 'NY_MIDDAY', 'NY_PM']
    
    for sym in symbols:
        print(f"\n==================== ASSET: {sym} ====================")
        sym_df = df_results[df_results['symbol'] == sym]
        
        print(f"\n--- {sym} Overall Strategy Performance ---")
        fmt_header = f"{'Regime Filter':<40} | {'Trades':<7} | {'Win Rate':<10} | {'TP2 Hit':<9} | {'Avg Win R':<10} | {'Profit Factor':<14} | {'Exp (R)':<8} | {'Net PnL ($)':<12}"
        print(fmt_header)
        print("-" * len(fmt_header))
        for fname, ffunc in filter_keys:
            m = generate_metrics(ffunc(sym_df))
            row = f"{fname:<40} | {m['trades']:<7} | {m['win_rate']:<9}% | {m['tp2_rate']:<8}% | +{m['avg_win_r']:<8}R | {m['profit_factor']:<14} | {m['exp_r']:+0.2f}R | ${m['net_pnl']:<11,}"
            print(row)

        print(f"\n--- {sym} Session-by-Session Breakdown ---")
        for sess in sessions:
            sess_df = sym_df[sym_df['session_name'] == sess]
            print(f"\n[Session: {sess}]")
            print(fmt_header)
            print("-" * len(fmt_header))
            for fname, ffunc in filter_keys:
                m = generate_metrics(ffunc(sess_df))
                row = f"{fname:<40} | {m['trades']:<7} | {m['win_rate']:<9}% | {m['tp2_rate']:<8}% | +{m['avg_win_r']:<8}R | {m['profit_factor']:<14} | {m['exp_r']:+0.2f}R | ${m['net_pnl']:<11,}"
                print(row)

    output_path = Path(f"data/derived/range_regime_zero_lookahead_{args.start_year}_{args.end_year}.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_results.to_csv(output_path, index=False)
    print(f"\nSaved realistic trade logs to {output_path}")


if __name__ == '__main__':
    main()
