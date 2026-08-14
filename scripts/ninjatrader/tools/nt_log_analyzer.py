#!/usr/bin/env python3
"""
NinjaTrader 8 Strategy Analyzer Log & Summary Inspector CLI

Fast, token-efficient parser and analytics engine for NinjaTrader Grid CSV and Summary CSV exports.

Usage:
    python -m scripts.ninjatrader.tools.nt_log_analyzer [path_to_csv]
    python -m scripts.ninjatrader.tools.nt_log_analyzer --latest
    python -m scripts.ninjatrader.tools.nt_log_analyzer --ib-only
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import numpy as np

# Point values for common futures
TICKER_POINT_VALUES = {
    "NQ": 20.0, "MNQ": 2.0,
    "ES": 50.0, "MES": 5.0,
    "YM": 5.0,  "MYM": 0.50,
    "RTY": 50.0,"M2K": 5.0,
    "CL": 1000.0,"MCL": 100.0,
    "GC": 100.0, "MGC": 10.0,
    "FDAX": 25.0, "FESX": 10.0,
    "ZB": 1000.0, "ZN": 1000.0
}

def get_point_value(instrument_name: str) -> float:
    name = str(instrument_name).upper()
    for sym, pv in TICKER_POINT_VALUES.items():
        if sym in name:
            return pv
    return 20.0  # Default to NQ

def find_latest_grid_csv(search_dir: Path) -> Optional[Path]:
    # Search for execution logs first (not summary)
    csvs = [f for f in search_dir.glob("NinjaTrader Grid*.csv") if "Summary" not in f.name]
    if not csvs:
        csvs = list(search_dir.glob("NinjaTrader Grid*.csv"))
    if not csvs:
        csvs = [f for f in search_dir.parent.glob("NinjaTrader Grid*.csv") if "Summary" not in f.name]
    if not csvs:
        return None
    csvs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return csvs[0]

def parse_grid_csv(file_path: Path) -> Tuple[pd.DataFrame, Dict]:
    df = pd.read_csv(file_path)
    
    # Check if summary CSV
    if "Performance" in df.columns:
        return pd.DataFrame(), {"type": "summary", "raw": df}
    
    # Filter valid rows
    required_cols = ['Instrument', 'Action', 'Price', 'Time', 'E/X']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in CSV: {file_path}")
            
    df = df.dropna(subset=['Instrument', 'Action', 'Price', 'Time', 'E/X']).copy()
    df['Time'] = pd.to_datetime(df['Time'])
    df = df.sort_values('Time').reset_index(drop=True)
    
    # Pair entries and exits
    trades = []
    open_entry = None
    
    for idx, row in df.iterrows():
        if row['E/X'] == 'Entry':
            open_entry = row
        elif row['E/X'] == 'Exit' and open_entry is not None:
            direction = "Long" if open_entry['Action'] == 'Buy' else "Short"
            entry_price = float(open_entry['Price'])
            exit_price = float(row['Price'])
            qty = float(open_entry['Quantity'])
            inst = str(row['Instrument'])
            pv = get_point_value(inst)
            
            if direction == "Long":
                pts = exit_price - entry_price
            else:
                pts = entry_price - exit_price
                
            pnl = pts * pv * qty
            
            trades.append({
                'Instrument': inst,
                'Direction': direction,
                'Quantity': qty,
                'EntryTime': open_entry['Time'],
                'ExitTime': row['Time'],
                'EntryPrice': entry_price,
                'ExitPrice': exit_price,
                'Points': pts,
                'PnL': pnl,
                'ExitName': str(row.get('Name', '')),
                'EntryName': str(open_entry.get('Name', '')),
                'DurationMins': (row['Time'] - open_entry['Time']).total_seconds() / 60.0
            })
            open_entry = None
            
    tdf = pd.DataFrame(trades)
    if len(tdf) > 0:
        tdf['Year'] = tdf['EntryTime'].dt.year
        tdf['YearMonth'] = tdf['EntryTime'].dt.to_period('M')
        tdf['DayOfWeek'] = tdf['EntryTime'].dt.day_name()
        tdf['Hour'] = tdf['EntryTime'].dt.hour
        tdf['Minute'] = tdf['EntryTime'].dt.minute
        tdf['TimeHHMM'] = tdf['Hour'] * 100 + tdf['Minute']
        tdf['Date'] = tdf['EntryTime'].dt.date
        tdf['IsIntraday'] = tdf['EntryTime'].dt.date == tdf['ExitTime'].dt.date
        
    return tdf, {"type": "grid", "raw_rows": len(df)}

def compute_metrics(tdf: pd.DataFrame) -> Dict:
    if len(tdf) == 0:
        return {}
    winners = tdf[tdf['PnL'] > 0]
    losers = tdf[tdf['PnL'] <= 0]
    
    total = len(tdf)
    win_cnt = len(winners)
    loss_cnt = len(losers)
    win_rate = (win_cnt / total) * 100.0
    
    gp = winners['PnL'].sum()
    gl = abs(losers['PnL'].sum())
    net = tdf['PnL'].sum()
    pf = gp / gl if gl > 0 else np.nan
    
    avg_win = winners['PnL'].mean() if win_cnt > 0 else 0
    avg_loss = losers['PnL'].mean() if loss_cnt > 0 else 0
    payoff = abs(avg_win / avg_loss) if avg_loss != 0 else np.nan
    
    # Equity curve & Max Trailing Drawdown
    tdf_sorted = tdf.sort_values('EntryTime').copy()
    cum_pnl = tdf_sorted['PnL'].cumsum()
    hwm = cum_pnl.cummax()
    dd = cum_pnl - hwm
    max_dd = dd.min()
    
    return {
        "total_trades": total,
        "winners": win_cnt,
        "losers": loss_cnt,
        "win_rate": win_rate,
        "gross_profit": gp,
        "gross_loss": gl,
        "net_profit": net,
        "profit_factor": pf,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": payoff,
        "max_drawdown": max_dd
    }

def print_dashboard(tdf: pd.DataFrame, file_path: Path):
    m = compute_metrics(tdf)
    if not m:
        print(f"No trades found in {file_path}")
        return

    print("=" * 95)
    print(f"🏛️  NINJATRADER 8 STRATEGY LOG ANALYZER | {file_path.name}")
    print("=" * 95)
    
    earliest = tdf['EntryTime'].min()
    latest = tdf['ExitTime'].max()
    days = (latest.date() - earliest.date()).days
    trades_per_day = len(tdf) / max(1, days * 5 / 7)
    
    print(f"Date Range    : {earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')} (~{days} calendar days)")
    print(f"Instruments   : {', '.join(tdf['Instrument'].unique())}")
    print(f"Total Trades  : {m['total_trades']:,d} ({trades_per_day:.2f} trades/day) | Win Rate: {m['win_rate']:.2f}% ({m['winners']}W / {m['losers']}L)")
    print(f"Net Profit    : ${m['net_profit']:>11,.2f} | Profit Factor: {m['profit_factor']:>6.3f} | Max DD: ${m['max_drawdown']:>10,.2f}")
    print(f"Gross Profit  : ${m['gross_profit']:>11,.2f} | Gross Loss   : -${m['gross_loss']:>10,.2f}")
    print(f"Average Win   : ${m['avg_win']:>11,.2f} | Average Loss : ${m['avg_loss']:>10,.2f} | Payoff: {m['payoff_ratio']:>5.2f}:1")
    
    # Rogue Brackets Health Check
    unattached = tdf[tdf['Points'] < -25]
    if len(unattached) > 0:
        print(f"\n⚠️  HEALTH WARNING: {len(unattached)} trades exceeded standard Stop Loss (>25 pt loss)!")
        print(f"   Artificial Loss Drag from Detached Brackets: -${abs(unattached['PnL'].sum()):,.2f}")
    else:
        print(f"\n✅  BRACKET HEALTH: 100% of trades adhered strictly to stop loss limits.")
        
    print("\n" + "─" * 95)
    print(f"{'DIMENSION / FILTER':<32} | {'TRADES':<7} | {'WIN RATE':<9} | {'NET PROFIT':<13} | {'PF':<6} | {'STATUS'}")
    print("─" * 95)
    
    # 1. Directional Split
    for d in ['Long', 'Short']:
        sub = tdf[tdf['Direction'] == d]
        if len(sub) > 0:
            sm = compute_metrics(sub)
            status = "🔥 STRONG" if sm['profit_factor'] >= 1.3 else ("⚠️ CHOP" if sm['profit_factor'] < 1.0 else "✅ PROFIT")
            print(f"Direction: {d:<21} | {sm['total_trades']:>7d} | {sm['win_rate']:>8.1f}% | ${sm['net_profit']:>11,.2f} | {sm['profit_factor']:>6.2f} | {status}")
            
    print("─" * 95)
    # 2. Hourly Execution Window
    ib = tdf[tdf['TimeHHMM'].between(930, 1030)]
    late = tdf[tdf['TimeHHMM'] > 1030]
    
    if len(ib) > 0:
        sm = compute_metrics(ib)
        status = "🔥 PRIME" if sm['profit_factor'] >= 1.3 else ("⚠️ CHOP" if sm['profit_factor'] < 1.0 else "✅ OK")
        print(f"Initial Balance (09:30-10:30 ET) | {sm['total_trades']:>7d} | {sm['win_rate']:>8.1f}% | ${sm['net_profit']:>11,.2f} | {sm['profit_factor']:>6.2f} | {status}")
        
    if len(late) > 0:
        sm = compute_metrics(late)
        status = "❌ DRAG" if sm['profit_factor'] < 0.9 else ("⚠️ CAUTION" if sm['profit_factor'] < 1.1 else "✅ OK")
        print(f"Late Morning (After 10:30 ET)   | {sm['total_trades']:>7d} | {sm['win_rate']:>8.1f}% | ${sm['net_profit']:>11,.2f} | {sm['profit_factor']:>6.2f} | {status}")
        
    print("─" * 95)
    # 3. Holding Time (Intraday vs Overnight)
    intra = tdf[tdf['IsIntraday']]
    over = tdf[~tdf['IsIntraday']]
    if len(intra) > 0:
        sm = compute_metrics(intra)
        print(f"Intraday Exits (Same Day)        | {sm['total_trades']:>7d} | {sm['win_rate']:>8.1f}% | ${sm['net_profit']:>11,.2f} | {sm['profit_factor']:>6.2f} | ✅ INTRADAY")
    if len(over) > 0:
        sm = compute_metrics(over)
        print(f"Multi-Day / Weekend Holds        | {sm['total_trades']:>7d} | {sm['win_rate']:>8.1f}% | ${sm['net_profit']:>11,.2f} | {sm['profit_factor']:>6.2f} | ⚠️ OVERNIGHT")
        
    print("─" * 95)
    # 4. Yearly Progression
    for y, sub in tdf.groupby('Year'):
        sm = compute_metrics(sub)
        status = "🔥 WIN" if sm['profit_factor'] >= 1.2 else ("❌ LOSS" if sm['profit_factor'] < 1.0 else "➖ EVEN")
        print(f"Year {y:<27} | {sm['total_trades']:>7d} | {sm['win_rate']:>8.1f}% | ${sm['net_profit']:>11,.2f} | {sm['profit_factor']:>6.2f} | {status}")
        
    print("=" * 95)

def main():
    parser = argparse.ArgumentParser(description="NinjaTrader 8 Strategy Analyzer Log & Summary Inspector CLI")
    parser.add_argument("path", nargs="?", default=None, help="Path to NinjaTrader Grid CSV or Summary CSV export")
    parser.add_argument("--latest", action="store_true", help="Auto-detect latest CSV in workspace")
    parser.add_argument("--ib-only", action="store_true", help="Simulate restricting entries to Initial Balance (09:30-10:30 ET)")
    parser.add_argument("--first-trade-only", action="store_true", help="Simulate taking only the 1st trade of each day")
    args = parser.parse_args()

    workspace = Path.cwd()
    target_file = None
    
    if args.path:
        target_file = Path(args.path)
        if not target_file.is_absolute():
            target_file = workspace / target_file
    else:
        target_file = find_latest_grid_csv(workspace)
        if not target_file:
            print(f"❌ No NinjaTrader Grid CSV files found in {workspace}")
            sys.exit(1)
            
    if not target_file.exists():
        print(f"❌ File not found: {target_file}")
        sys.exit(1)
        
    tdf, meta = parse_grid_csv(target_file)
    
    if meta.get("type") == "summary":
        print(f"Loaded Summary CSV: {target_file.name}")
        print(meta["raw"].to_string())
        return
        
    if args.ib_only:
        tdf = tdf[tdf['TimeHHMM'].between(930, 1030)]
        print("[FILTER APPLIED] Initial Balance Window Only (09:30 - 10:30 ET)")
        
    if args.first_trade_only:
        tdf = tdf.groupby('Date').first().reset_index()
        print("[FILTER APPLIED] One-and-Done (First Trade of Day Only)")

    print_dashboard(tdf, target_file)

if __name__ == "__main__":
    main()
