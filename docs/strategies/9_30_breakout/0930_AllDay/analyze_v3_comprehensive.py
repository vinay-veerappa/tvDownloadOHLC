"""
Comprehensive V3 Modes vs V2 Strategy Analysis
=============================================
Analyzes and compares 4 strategy variations:
1. V3 Fixed TP (Winner)
2. V3 Adaptive (Validated)
3. V3 Time Exit (Baseline V3)
4. V2 Baseline (Original)

Includes Risk Profiling, Granular Time Analysis, and MFE/MAE stats.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import glob

warnings.filterwarnings('ignore')

# Files
V3_FIXED_FILE = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_620dd.xlsx'
V3_ADAPTIVE_FILE = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_52358.xlsx'
V3_TIME_FILE = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_cfbde.xlsx'
V2_FILE = r'old\ORB_All-Day_V2_CME_MINI_MNQ1!_2026-01-07_06a7f.xlsx'

def load_strategy_data(filepath, name):
    """Load and process strategy data from Excel"""
    try:
        xl = pd.ExcelFile(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None
    
    sheet = next((s for s in xl.sheet_names if s.lower() == "list of trades"), "List of trades")
    trade_list = pd.read_excel(xl, sheet_name=sheet)
    trade_list['Date and time'] = pd.to_datetime(trade_list['Date and time'])
    
    entries = trade_list[trade_list['Type'].str.contains('Entry', case=False, na=False)].copy()
    exits = trade_list[trade_list['Type'].str.contains('Exit', case=False, na=False)].copy()
    
    entries = entries[['Trade #', 'Date and time', 'Signal', 'Price USD']].copy()
    entries.columns = ['Trade #', 'Entry Time', 'Entry Signal', 'Entry Price']
    
    cols_to_use = ['Trade #', 'Date and time', 'Type', 'Signal', 'Price USD', 
                   'Net P&L USD', 'Net P&L %', 'MFE USD', 'MFE %', 'MAE USD', 'MAE %']
    cols_to_use = [c for c in cols_to_use if c in exits.columns]
    
    exits = exits[cols_to_use].copy()
    
    rename_map = { 'Date and time': 'Exit Time', 'Price USD': 'Exit Price' }
    exits.rename(columns=rename_map, inplace=True)
    if 'Signal' in exits.columns: exits.rename(columns={'Signal': 'Exit Signal'}, inplace=True)
    
    merged = pd.merge(exits, entries, on='Trade #', how='left')
    merged['Strategy'] = name
    
    # Time Analysis Columns
    merged['Hour'] = merged['Entry Time'].dt.hour
    merged['Minute'] = merged['Entry Time'].dt.minute
    merged['DayOfWeek'] = merged['Entry Time'].dt.day_name()
    merged['Month'] = merged['Entry Time'].dt.month
    merged['Year'] = merged['Entry Time'].dt.year
    merged['Date'] = merged['Entry Time'].dt.date
    merged['YearMonth'] = merged['Entry Time'].dt.to_period('M')
    
    # Buckets
    merged['15min_bucket'] = (merged['Minute'] // 15) * 15
    merged['5min_bucket'] = (merged['Minute'] // 5) * 5
    merged['Hour_Minute'] = merged['Hour'].astype(str).str.zfill(2) + ':' + merged['Minute'].astype(str).str.zfill(2)
    
    merged['Is_Winner'] = merged['Net P&L USD'] > 0
    merged['Is_Stopped'] = merged['Exit Signal'].astype(str).str.contains('SL|Stop|MAE', case=False, na=False)
    
    return { 'name': name, 'merged': merged }

def calc_stats_extended(df):
    """Calculate extended stats for risk profiling"""
    if len(df) == 0: return {}
    
    wins = df[df['Net P&L USD'] > 0]
    losses = df[df['Net P&L USD'] <= 0]
    
    gross_profit = wins['Net P&L USD'].sum()
    gross_loss = abs(losses['Net P&L USD'].sum())
    
    trades = len(df)
    total_pnl = df['Net P&L USD'].sum()
    avg_pnl = df['Net P&L USD'].mean()
    std_pnl = df['Net P&L USD'].std()
    
    # Drawdown
    df_sorted = df.sort_values('Entry Time')
    equity = df_sorted['Net P&L USD'].cumsum()
    peak = equity.cummax()
    drawdown = equity - peak
    max_dd = drawdown.min()
    
    # SQN
    sqn = (avg_pnl / std_pnl) * (trades ** 0.5) if std_pnl > 0 else 0
    
    stats = {
        'Trades': trades,
        'Win Rate %': len(wins) / trades * 100,
        'Total P&L': total_pnl,
        'Avg P&L': avg_pnl,
        'Profit Factor': gross_profit / gross_loss if gross_loss > 0 else float('inf'),
        'SQN': sqn,
        'Max Drawdown': max_dd,
        'Return/DD': total_pnl / abs(max_dd) if max_dd < 0 else 0,
        'Avg Win': wins['Net P&L USD'].mean() if len(wins) > 0 else 0,
        'Avg Loss': losses['Net P&L USD'].mean() if len(losses) > 0 else 0,
        'Avg MFE %': df['MFE %'].mean() if 'MFE %' in df.columns else 0,
        'Avg MAE %': df['MAE %'].mean() if 'MAE %' in df.columns else 0,
        'Stopped %': df['Is_Stopped'].mean() * 100
    }
    return stats

def generate_report(datasets):
    report = []
    report.append("# V3 Modes vs V2 Comprehensive Analysis (Enhanced)")
    report.append(f"## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("---")
    report.append("")
    
    # 1. EXECUTIVE SUMMARY
    report.append("## 📊 EXECUTIVE SUMMARY")
    report.append("")
    
    headers = ["Metric"] + [d['name'] for d in datasets]
    report.append("| " + " | ".join(headers) + " |")
    report.append("|" + "|".join(["---"] * len(headers)) + "|")
    
    all_stats = [calc_stats_extended(d['merged']) for d in datasets]
    
    metrics = [
        ('Trades', 'Trades', '{:.0f}'),
        ('Total P&L', 'Total P&L', '${:,.2f}'),
        ('Win Rate %', 'Win Rate %', '{:.2f}%'),
        ('Avg P&L (EV)', 'Avg P&L', '${:.2f}'),
    ]
    
    for label, key, fmt in metrics:
        row = [f"**{label}**"]
        for stats in all_stats:
            row.append(fmt.format(stats.get(key, 0)))
        report.append("| " + " | ".join(row) + " |")
    
    report.append("")
    report.append("---")
    report.append("")

    # 2. RISK PROFILING
    report.append("## 🛡️ RISK PROFILING & EFFICIENCY")
    report.append("")
    report.append("| Metric | " + " | ".join([d['name'] for d in datasets]) + " |")
    report.append("|" + "|".join(["---"] * (len(datasets)+1)) + "|")

    risk_metrics = [
        ('Profit Factor', 'Profit Factor', '{:.2f}'),
        ('SQN', 'SQN', '{:.2f}'),
        ('Max Drawdown', 'Max Drawdown', '${:,.0f}'),
        ('Return / MaxDD', 'Return/DD', '{:.2f}'),
        ('Avg Win', 'Avg Win', '${:.2f}'),
        ('Avg Loss', 'Avg Loss', '${:.2f}'),
    ]

    for label, key, fmt in risk_metrics:
        row = [f"**{label}**"]
        for stats in all_stats:
            row.append(fmt.format(stats.get(key, 0)))
        report.append("| " + " | ".join(row) + " |")

    report.append("")
    report.append("### SQN Interpretation")
    report.append("> **SQN > 3.0** is excellent. **SQN > 5.0** is superb.")
    report.append("> V3 Fixed TP SQN: **{:.2f}** (Highest Quality)".format(all_stats[0]['SQN']))
    report.append("")
    report.append("---")
    report.append("")

    # 3. GRANULAR TIME ANALYSIS
    
    # HOURLY
    report.append("## ⏰ HOURLY PERFORMANCE (P&L)")
    report.append("")
    hours = sorted(list(set(h for d in datasets for h in d['merged']['Hour'].unique())))
    report.append("| Hour | " + " | ".join([d['name'] for d in datasets]) + " |")
    report.append("|" + "|".join(["---"] * (len(datasets)+1)) + "|")
    
    for h in hours:
        row = [f"{h:02d}:00"]
        for d in datasets:
            df = d['merged']
            pnl = df[df['Hour'] == h]['Net P&L USD'].sum()
            row.append(f"${pnl:,.0f}")
        report.append("| " + " | ".join(row) + " |")
    
    report.append("")
    
    # DAY OF WEEK
    report.append("### Day of Week Performance")
    report.append("")
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    report.append("| Day | " + " | ".join([d['name'] for d in datasets]) + " |")
    report.append("|" + "|".join(["---"] * (len(datasets)+1)) + "|")
    
    for day in days:
        row = [day]
        for d in datasets:
            df = d['merged']
            pnl = df[df['DayOfWeek'] == day]['Net P&L USD'].sum()
            row.append(f"${pnl:,.0f}")
        report.append("| " + " | ".join(row) + " |")
        
    report.append("")

    # MONTHLY (Top 5 Best/Worst months just to summarize?)
    # Or strict table by year-month... too long for 3 years?
    # Let's do Year-Month Table, it was requested.
    
    report.append("### Month-by-Month Performance")
    report.append("")
    all_ym = sorted(list(set(m for d in datasets for m in d['merged']['YearMonth'].dropna().unique())))
    report.append("| Month | " + " | ".join([d['name'] for d in datasets]) + " |")
    report.append("|" + "|".join(["---"] * (len(datasets)+1)) + "|")
    
    for ym in all_ym:
        row = [str(ym)]
        for d in datasets:
            df = d['merged']
            pnl = df[df['YearMonth'] == ym]['Net P&L USD'].sum()
            row.append(f"${pnl:,.0f}")
        report.append("| " + " | ".join(row) + " |")
        
    report.append("")
    report.append("---")
    report.append("")

    # 4. MFE/MAE STATS (Percentiles)
    report.append("## 📈 MFE/MAE DISTRIBUTION")
    report.append("")
    report.append("| Metric | " + " | ".join([d['name'] for d in datasets]) + " |")
    report.append("|" + "|".join(["---"] * (len(datasets)+1)) + "|")
    
    mfe_metrics = [
        ('Avg MFE %', lambda x: x['MFE %'].mean()),
        ('Max MFE %', lambda x: x['MFE %'].max()),
        ('Avg MAE %', lambda x: x['MAE %'].mean()),
        ('Min MAE %', lambda x: x['MAE %'].min()),
    ]
    
    for label, func in mfe_metrics:
        row = [f"**{label}**"]
        for d in datasets:
            try:
                val = func(d['merged'])
                row.append(f"{val:.3f}%")
            except:
                row.append("N/A")
        report.append("| " + " | ".join(row) + " |")
        
    return '\n'.join(report)

if __name__ == '__main__':
    print("Loading datasets...")
    datasets = []
    d1 = load_strategy_data(V3_FIXED_FILE, 'V3 Fixed TP')
    if d1: datasets.append(d1)
    d2 = load_strategy_data(V3_ADAPTIVE_FILE, 'V3 Adaptive')
    if d2: datasets.append(d2)
    d3 = load_strategy_data(V3_TIME_FILE, 'V3 Time Exit')
    if d3: datasets.append(d3)
    d4 = load_strategy_data(V2_FILE, 'V2 Baseline')
    if d4: datasets.append(d4)
    
    print(f"Loaded {len(datasets)} datasets.")
    if len(datasets) > 0:
        print("Generating Enhanced report...")
        report_content = generate_report(datasets)
        out_file = 'V3_vs_V2_Comprehensive_Analysis.md'
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"DONE. Report saved to {out_file}")
