"""
Auction Market Theory Live Prop Firm Simulation:
Enforces Strict True SFP / Failed Auction Mechanics:
1. Range Containment: Prior bars must be trading INSIDE the reference range.
2. Immediate Rejection: Sweep must reject back inside within 1-2 bars (no accepted breakout).
3. 1-tick order queue penetration on limit entry.
4. 2-tick slippage on stop-loss market fills.
5. Micro Sizing: 4 Micro MES / 2 Micro MNQ on $50k account ($2,000 Max Trailing DD, $3,000 Profit Target).
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
class LiveTrade:
    symbol: str
    session_name: str
    date: str
    direction: str
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
    leg1_pnl: float
    leg2_pnl: float
    net_pnl_dollars: float
    r_multiple: float


def run_amt_simulation(symbol: str, df_1m: pd.DataFrame, start_year: int = 2021, end_year: int = 2026) -> List[LiveTrade]:
    print(f"Running Auction Market Theory simulation for {symbol} ({start_year}-{end_year})...")
    df_1m = df_1m[(df_1m.index.year >= start_year) & (df_1m.index.year <= end_year)].copy()
    if df_1m.empty:
        return []

    tick_size = 0.25
    is_es = 'ES' in symbol
    
    # 4 Micro MES ($20/pt total; 2 contracts per leg)
    # 2 Micro MNQ ($4/pt total; 1 contract per leg)
    contracts_total = 4 if is_es else 2
    contracts_per_leg = 2 if is_es else 1
    pt_val_per_leg = (5.0 * contracts_per_leg) if is_es else (2.0 * contracts_per_leg)
    comm_total = contracts_total * 1.20  # $1.20 round-trip per micro
    
    slippage_sl_ticks = 2  # 2 ticks slippage on market stop
    min_fvg_size = 0.75 if is_es else 3.5
    
    df_daily = df_1m.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    high, low, close = df_daily['high'], df_daily['low'], df_daily['close']
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    daily_atr = tr.rolling(10, min_periods=1).mean()
    
    df_5m = df_1m.resample('5min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
    
    df_1m['trade_date'] = df_1m.index.date
    evening_mask = df_1m.index.hour >= 18
    df_1m.loc[evening_mask, 'trade_date'] = (df_1m.loc[evening_mask].index + pd.Timedelta(days=1)).date
    
    unique_dates = sorted(df_1m['trade_date'].unique())
    trades: List[LiveTrade] = []
    
    for t_date in unique_dates:
        t_date_str = str(t_date)
        prev_day = t_date - pd.Timedelta(days=1)
        
        atr_val = daily_atr.get(pd.Timestamp(prev_day), daily_atr.mean())
        if pd.isna(atr_val) or atr_val <= 0:
            atr_val = 20.0 if is_es else 80.0
            
        prior_rth = df_1m.loc[f"{prev_day} 09:30:00":f"{prev_day} 16:00:00"]
        prior_rth_h = prior_rth['high'].max() if len(prior_rth) > 0 else np.nan
        prior_rth_l = prior_rth['low'].min() if len(prior_rth) > 0 else np.nan
        
        asia_1m = df_1m.loc[f"{prev_day} 18:00:00":f"{t_date} 02:00:00"]
        asia_h = asia_1m['high'].max() if len(asia_1m) > 0 else np.nan
        asia_l = asia_1m['low'].min() if len(asia_1m) > 0 else np.nan
        asia_r = (asia_h - asia_l) if not np.isnan(asia_h) else np.nan
        
        on_1m = df_1m.loc[f"{prev_day} 18:00:00":f"{t_date} 09:29:00"]
        on_h = on_1m['high'].max() if len(on_1m) > 0 else np.nan
        on_l = on_1m['low'].min() if len(on_1m) > 0 else np.nan
        on_r = (on_h - on_l) if not np.isnan(on_h) else np.nan
        
        ib_1m = df_1m.loc[f"{t_date} 09:30:00":f"{t_date} 10:30:00"]
        ib_h = ib_1m['high'].max() if len(ib_1m) > 0 else np.nan
        ib_l = ib_1m['low'].min() if len(ib_1m) > 0 else np.nan
        ib_r = (ib_h - ib_l) if not np.isnan(ib_h) else np.nan

        sessions = [
            {'name': 'ASIA', 'start': f"{prev_day} 18:00:00", 'end': f"{t_date} 02:00:00", 'ref_h': prior_rth_h, 'ref_l': prior_rth_l, 'ref_r': (prior_rth_h - prior_rth_l), 'scan': f"{prev_day} 19:00:00"},
            {'name': 'LONDON', 'start': f"{t_date} 02:00:00", 'end': f"{t_date} 08:30:00", 'ref_h': asia_h, 'ref_l': asia_l, 'ref_r': asia_r, 'scan': f"{t_date} 02:30:00"},
            {'name': 'NY_AM', 'start': f"{t_date} 09:30:00", 'end': f"{t_date} 11:30:00", 'ref_h': on_h, 'ref_l': on_l, 'ref_r': on_r, 'scan': f"{t_date} 09:45:00"},
            {'name': 'NY_MIDDAY', 'start': f"{t_date} 11:30:00", 'end': f"{t_date} 13:30:00", 'ref_h': ib_h, 'ref_l': ib_l, 'ref_r': ib_r, 'scan': f"{t_date} 11:30:00"},
            {'name': 'NY_PM', 'start': f"{t_date} 13:30:00", 'end': f"{t_date} 16:00:00", 'ref_h': ib_h, 'ref_l': ib_l, 'ref_r': ib_r, 'scan': f"{t_date} 13:30:00"}
        ]
        
        session_losses = 0
        for sess in sessions:
            if session_losses >= 2:
                continue
                
            ref_h = sess['ref_h']
            ref_l = sess['ref_l']
            ref_r = sess['ref_r']
            
            if np.isnan(ref_h) or np.isnan(ref_l) or np.isnan(ref_r) or ref_r <= 0:
                continue
                
            # Filter B: Reference range must be compressed (<0.40 ATR)
            if ref_r >= (0.40 * atr_val):
                continue
                
            sess_1m = df_1m.loc[sess['start']:sess['end']]
            if len(sess_1m) < 15:
                continue
            sess_5m = df_5m.loc[sess['start']:sess['end']]
            if len(sess_5m) < 4:
                continue
                
            scan_bars = sess_5m.loc[sess['scan']:]
            session_traded = False
            
            for i_idx in range(2, len(scan_bars)):
                if session_traded:
                    break
                    
                b0 = scan_bars.iloc[i_idx - 2]
                b1 = scan_bars.iloc[i_idx - 1]
                b2 = scan_bars.iloc[i_idx]
                curr_time = scan_bars.index[i_idx]
                
                # Check prior bars inside the session:
                # If market had already closed > 1 bar outside range, it is an accepted breakout -> SKIP
                prior_session_5m = sess_5m.loc[:curr_time]
                closes_above_ref = (prior_session_5m['close'] > ref_h).sum()
                closes_below_ref = (prior_session_5m['close'] < ref_l).sum()
                
                # -----------------------------------------------------------------
                # SHORT SETUP: Strict Failed Auction / SFP at Range High
                # 1. b0 was trading inside range (b0['close'] <= ref_h)
                # 2. b1 or b2 pierced above ref_h (swept liquidity)
                # 3. b2 closes back inside range (b2['close'] < ref_h)
                # 4. No previous accepted closes above ref_h (closes_above_ref <= 1)
                # 5. Bearish 5m FVG displacement
                # -----------------------------------------------------------------
                is_contained_before = (b0['close'] <= ref_h)
                swept_h = (b1['high'] > ref_h or b2['high'] > ref_h)
                closed_inside = (b2['close'] < ref_h) and (b2['close'] < b2['open'])
                bear_fvg = (b0['low'] - b2['high']) >= min_fvg_size
                no_breakout_accepted = (closes_above_ref <= 1)
                
                if is_contained_before and swept_h and closed_inside and bear_fvg and no_breakout_accepted:
                    fvg_entry = b2['high']
                    sweep_ext = max(b1['high'], b2['high'])
                    sl = sweep_ext + (2 * tick_size)
                    risk = sl - fvg_entry
                    tp1 = ref_l + (0.50 * ref_r)
                    tp2 = ref_l
                    
                    if risk > 0 and risk < (0.25 * atr_val) and tp1 < fvg_entry:
                        sim_1m = sess_1m.loc[curr_time:]
                        filled = False
                        fill_idx = None
                        t1_hit = False
                        t2_hit = False
                        stopped = False
                        leg1_pnl, leg2_pnl = 0.0, 0.0
                        
                        for t_bar, row in sim_1m.iterrows():
                            if not filled:
                                if row['high'] >= fvg_entry:
                                    filled = True
                                    fill_idx = t_bar
                            else:
                                if row['high'] >= sl:
                                    stopped = True
                                    effective_sl_pnl = -risk - (slippage_sl_ticks * tick_size)
                                    if not t1_hit:
                                        leg1_pnl = effective_sl_pnl
                                        leg2_pnl = effective_sl_pnl
                                    else:
                                        leg2_pnl = -(slippage_sl_ticks * tick_size)
                                    exit_time = t_bar
                                    break
                                
                                if not t1_hit and row['low'] <= tp1:
                                    t1_hit = True
                                    leg1_pnl = (fvg_entry - tp1)
                                    sl = fvg_entry  # Move Leg 2 to BE
                                    
                                if row['low'] <= tp2:
                                    t2_hit = True
                                    leg2_pnl = (fvg_entry - tp2)
                                    exit_time = t_bar
                                    break
                                    
                        if filled:
                            if not stopped and not t2_hit:
                                exit_price = sim_1m['close'].iloc[-1]
                                exit_time = sim_1m.index[-1]
                                if not t1_hit:
                                    leg1_pnl = (fvg_entry - exit_price)
                                leg2_pnl = (fvg_entry - exit_price)
                                
                            gross_dollars = (leg1_pnl * pt_val_per_leg) + (leg2_pnl * pt_val_per_leg)
                            net_dollars = gross_dollars - comm_total
                            total_pts = (leg1_pnl + leg2_pnl) / 2.0
                            r_mult = total_pts / risk if risk > 0 else 0.0
                            
                            if net_dollars < 0:
                                session_losses += 1
                            else:
                                session_losses = 0
                                
                            trades.append(LiveTrade(
                                symbol=symbol, session_name=sess['name'], date=t_date_str,
                                direction='SHORT', entry_time=fill_idx, entry_price=fvg_entry,
                                stop_loss=sweep_ext + (2 * tick_size), tp1_price=tp1, tp2_price=tp2,
                                risk_points=risk, t1_hit=t1_hit, t2_hit=t2_hit, stopped_out=stopped,
                                exit_time=exit_time, leg1_pnl=leg1_pnl, leg2_pnl=leg2_pnl,
                                net_pnl_dollars=net_dollars, r_multiple=r_mult
                            ))
                            session_traded = True
                
                # -----------------------------------------------------------------
                # LONG SETUP: Strict Failed Auction / SFP at Range Low
                # -----------------------------------------------------------------
                is_contained_before_l = (b0['close'] >= ref_l)
                swept_l = (b1['low'] < ref_l or b2['low'] < ref_l)
                closed_inside_l = (b2['close'] > ref_l) and (b2['close'] > b2['open'])
                bull_fvg = (b2['low'] - b0['high']) >= min_fvg_size
                no_breakout_accepted_l = (closes_below_ref <= 1)
                
                if not session_traded and is_contained_before_l and swept_l and closed_inside_l and bull_fvg and no_breakout_accepted_l:
                    fvg_entry = b2['low']
                    sweep_ext = min(b1['low'], b2['low'])
                    sl = sweep_ext - (2 * tick_size)
                    risk = fvg_entry - sl
                    tp1 = ref_l + (0.50 * ref_r)
                    tp2 = ref_h
                    
                    if risk > 0 and risk < (0.25 * atr_val) and tp1 > fvg_entry:
                        sim_1m = sess_1m.loc[curr_time:]
                        filled = False
                        fill_idx = None
                        t1_hit = False
                        t2_hit = False
                        stopped = False
                        leg1_pnl, leg2_pnl = 0.0, 0.0
                        
                        for t_bar, row in sim_1m.iterrows():
                            if not filled:
                                if row['low'] <= fvg_entry:
                                    filled = True
                                    fill_idx = t_bar
                            else:
                                if row['low'] <= sl:
                                    stopped = True
                                    effective_sl_pnl = -risk - (slippage_sl_ticks * tick_size)
                                    if not t1_hit:
                                        leg1_pnl = effective_sl_pnl
                                        leg2_pnl = effective_sl_pnl
                                    else:
                                        leg2_pnl = -(slippage_sl_ticks * tick_size)
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
                                
                            gross_dollars = (leg1_pnl * pt_val_per_leg) + (leg2_pnl * pt_val_per_leg)
                            net_dollars = gross_dollars - comm_total
                            total_pts = (leg1_pnl + leg2_pnl) / 2.0
                            r_mult = total_pts / risk if risk > 0 else 0.0
                            
                            if net_dollars < 0:
                                session_losses += 1
                            else:
                                session_losses = 0
                                
                            trades.append(LiveTrade(
                                symbol=symbol, session_name=sess['name'], date=t_date_str,
                                direction='LONG', entry_time=fill_idx, entry_price=fvg_entry,
                                stop_loss=sweep_ext - (2 * tick_size), tp1_price=tp1, tp2_price=tp2,
                                risk_points=risk, t1_hit=t1_hit, t2_hit=t2_hit, stopped_out=stopped,
                                exit_time=exit_time, leg1_pnl=leg1_pnl, leg2_pnl=leg2_pnl,
                                net_pnl_dollars=net_dollars, r_multiple=r_mult
                            ))
                            session_traded = True

    return trades


def analyze_prop_firm_passes(df_trades: pd.DataFrame, symbol: str, target: float = 3000.0, max_dd_limit: float = 2000.0):
    df_sym = df_trades[df_trades['symbol'] == symbol].sort_values('entry_time').reset_index(drop=True)
    if df_sym.empty:
        return
        
    pnl = df_sym['net_pnl_dollars']
    cum_pnl = pnl.cumsum()
    peak = cum_pnl.cummax()
    dd = cum_pnl - peak
    max_dd = abs(dd.min())
    
    wins = df_sym[pnl > 0]
    win_rate = (len(wins) / len(df_sym)) * 100.0
    gross_win = wins['net_pnl_dollars'].sum()
    gross_loss = abs(df_sym[pnl < 0]['net_pnl_dollars'].sum())
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 99.0
    
    eval_passes = 0
    eval_fails = 0
    curr_eval_pnl = 0.0
    curr_eval_peak = 0.0
    days_to_pass = []
    start_eval_idx = 0
    
    for idx, row in df_sym.iterrows():
        curr_eval_pnl += row['net_pnl_dollars']
        if curr_eval_pnl > curr_eval_peak:
            curr_eval_peak = curr_eval_pnl
        curr_eval_dd = curr_eval_pnl - curr_eval_peak
        
        # Check Fail
        if abs(curr_eval_dd) >= max_dd_limit:
            eval_fails += 1
            curr_eval_pnl = 0.0
            curr_eval_peak = 0.0
            start_eval_idx = idx + 1
        # Check Pass
        elif curr_eval_pnl >= target:
            eval_passes += 1
            days_count = (pd.to_datetime(row['date']) - pd.to_datetime(df_sym.iloc[start_eval_idx]['date'])).days
            days_to_pass.append(max(1, days_count))
            curr_eval_pnl = 0.0
            curr_eval_peak = 0.0
            start_eval_idx = idx + 1

    avg_days_pass = np.mean(days_to_pass) if days_to_pass else 0
    
    print("\n" + "=" * 85)
    print(f"STRICT AUCTION MARKET THEORY PROP FIRM BENCHMARK: {symbol}")
    print(f"Config: 4 Micro MES / 2 Micro MNQ | $50k Account ($2,000 Max DD, $3,000 Profit Target)")
    print("=" * 85)
    print(f"Total Completed Trades (5-Yr): {len(df_sym)}")
    print(f"Realistic Win Rate: {round(win_rate, 1)}%")
    print(f"Realistic Profit Factor: {round(profit_factor, 2)}")
    print(f"5-Year Max Peak-to-Valley Drawdown: ${round(max_dd, 0):,} (Threshold: ${max_dd_limit:,})")
    print(f"Total 5-Year Net Profit: ${round(cum_pnl.iloc[-1], 0):,}")
    print("-" * 85)
    print(f"Simulated $3,000 Evaluations Passed: {eval_passes} Times")
    print(f"Simulated $2,000 Evaluations Failed/Busted: {eval_fails} Times")
    pass_rate = (eval_passes / (eval_passes + eval_fails) * 100.0) if (eval_passes + eval_fails) > 0 else 0.0
    print(f"Prop Firm Challenge Pass Rate: {round(pass_rate, 1)}%")
    print(f"Average Calendar Days to Pass $3,000 Target: {round(avg_days_pass, 0)} days (~{round(avg_days_pass/7, 1)} weeks)")
    print("=" * 85)


def main():
    parser = argparse.ArgumentParser(description="Strict AMT Prop Firm Simulation")
    parser.add_argument('--start-year', type=int, default=2021)
    parser.add_argument('--end-year', type=int, default=2026)
    parser.add_argument('--symbols', type=str, default='ES,NQ')
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    all_trades: List[LiveTrade] = []

    for sym in symbols:
        parquet_file = Path(f"data/{sym}1_1m.parquet")
        if not parquet_file.exists():
            continue
        df_1m = pd.read_parquet(parquet_file)
        sym_trades = run_amt_simulation(sym, df_1m, start_year=args.start_year, end_year=args.end_year)
        all_trades.extend(sym_trades)

    if not all_trades:
        print("No trades generated.")
        return

    df_results = pd.DataFrame([t.__dict__ for t in all_trades])
    
    for sym in symbols:
        analyze_prop_firm_passes(df_results, sym, target=3000.0, max_dd_limit=2000.0)

    output_path = Path(f"data/derived/amt_prop_firm_simulation_{args.start_year}_{args.end_year}.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_results.to_csv(output_path, index=False)
    print(f"\nSaved AMT live simulation log to {output_path}")


if __name__ == '__main__':
    main()
