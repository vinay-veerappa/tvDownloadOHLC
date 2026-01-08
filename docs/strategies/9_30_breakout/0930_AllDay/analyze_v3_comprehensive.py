"""
Comprehensive V3 Modes vs V2 Strategy Analysis
=============================================
Analyzes and compares 4 strategy variations:
1. V3 Fixed TP (Winner)
2. V3 Adaptive (Validated)
3. V3 Time Exit (Baseline V3)
4. V2 Baseline (Original)
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
    
    # Load all sheets
    # performance = pd.read_excel(xl, sheet_name='Performance')
    # trades_analysis = pd.read_excel(xl, sheet_name='Trades analysis') 
    # Not strictly needed if we parse Trade List manually
    
    # Try to find List of trades
    sheet = next((s for s in xl.sheet_names if s.lower() == "list of trades"), "List of trades")
    trade_list = pd.read_excel(xl, sheet_name=sheet)
    
    # Parse datetime
    trade_list['Date and time'] = pd.to_datetime(trade_list['Date and time'])
    
    # Separate entries and exits to avoid Double Counting and get MFE/MAE
    entries = trade_list[trade_list['Type'].str.contains('Entry', case=False, na=False)].copy()
    exits = trade_list[trade_list['Type'].str.contains('Exit', case=False, na=False)].copy()
    
    # Create merged trades (entry + exit info)
    # We mainly need stats from EXITS, but MFE/MAE might be on Entry or Exit row depending on export.
    # Actually, MFE/MAE is usually populated on BOTH rows in new exports.
    # We will use EXIT rows as the primary source of truth for Net P&L.
    
    # Merge Entry info (Time) into Exit info
    # Join on 'Trade #'
    
    entries = entries[['Trade #', 'Date and time', 'Signal', 'Price USD']].copy()
    entries.columns = ['Trade #', 'Entry Time', 'Entry Signal', 'Entry Price']
    
    cols_to_use = ['Trade #', 'Date and time', 'Type', 'Signal', 'Price USD', 
                   'Net P&L USD', 'Net P&L %', 'MFE USD', 'MFE %', 'MAE USD', 'MAE %']
    # Check if they exist
    cols_to_use = [c for c in cols_to_use if c in exits.columns]
    
    exits = exits[cols_to_use].copy()
    
    # Rename columns to standard internal names
    rename_map = {
        'Date and time': 'Exit Time',
        'Price USD': 'Exit Price'
    }
    exits.rename(columns=rename_map, inplace=True)
    
    # Ensure Exit Signal exists (it might be 'Signal' column)
    if 'Signal' in exits.columns:
        exits.rename(columns={'Signal': 'Exit Signal'}, inplace=True)
    
    # Merge
    merged = pd.merge(exits, entries, on='Trade #', how='left')
    
    # Fill Entry Time if missing (some partial exits?)
    # If Entry Time is NaT, use Exit Time (shouldn't happen often)
    
    merged['Strategy'] = name
    
    # Extract time components from ENTRY TIME
    merged['Hour'] = merged['Entry Time'].dt.hour
    merged['Minute'] = merged['Entry Time'].dt.minute
    merged['DayOfWeek'] = merged['Entry Time'].dt.day_name()
    merged['Month'] = merged['Entry Time'].dt.month
    merged['Year'] = merged['Entry Time'].dt.year
    merged['Date'] = merged['Entry Time'].dt.date
    
    # Time buckets
    merged['15min_bucket'] = (merged['Minute'] // 15) * 15
    merged['5min_bucket'] = (merged['Minute'] // 5) * 5
    merged['1min_bucket'] = merged['Minute']
    merged['Hour_Minute'] = merged['Hour'].astype(str).str.zfill(2) + ':' + merged['Minute'].astype(str).str.zfill(2)
    
    # Win/Loss classification
    merged['Is_Winner'] = merged['Net P&L USD'] > 0
    merged['Is_Stopped'] = merged['Exit Signal'].astype(str).str.contains('SL|Stop|MAE', case=False, na=False)
    
    return {
        'name': name,
        'merged': merged
    }

def calc_single_stats(df):
    """Calculate stats for a single group"""
    if len(df) == 0:
        return {}
    
    wins = df[df['Net P&L USD'] > 0]
    losses = df[df['Net P&L USD'] <= 0]
    
    stats = {
        'Trades': len(df),
        'Win Rate %': len(wins) / len(df) * 100 if len(df) > 0 else 0,
        'Total P&L': df['Net P&L USD'].sum(),
        'Avg P&L': df['Net P&L USD'].mean(),
        'Avg MFE %': df['MFE %'].mean() if 'MFE %' in df.columns else 0,
        'Avg MAE %': df['MAE %'].mean() if 'MAE %' in df.columns else 0,
        'Stopped Out': df['Is_Stopped'].sum(),
        'Stopped %': df['Is_Stopped'].mean() * 100,
        'Avg Win': wins['Net P&L USD'].mean() if len(wins) > 0 else 0,
        'Avg Loss': losses['Net P&L USD'].mean() if len(losses) > 0 else 0,
    }
    return stats

def generate_report(datasets):
    """Generate comprehensive comparison report for multiple datasets"""
    
    report = []
    report.append("# V3 Modes vs V2 Comprehensive Analysis")
    report.append(f"## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("---")
    report.append("")
    
    # =================
    # EXECUTIVE SUMMARY
    # =================
    report.append("## 📊 EXECUTIVE SUMMARY")
    report.append("")
    
    headers = ["Metric"] + [d['name'] for d in datasets]
    report.append("| " + " | ".join(headers) + " |")
    report.append("|" + "|".join(["---"] * len(headers)) + "|")
    
    metrics = [
        ('Trades', 'Trades', '{:.0f}'),
        ('Win Rate %', 'Win Rate %', '{:.2f}%'),
        ('Total P&L', 'Total P&L', '${:,.2f}'),
        ('Avg P&L', 'Avg P&L', '${:.2f}'),
        ('Avg MFE %', 'Avg MFE %', '{:.3f}%'),
        ('Avg MAE %', 'Avg MAE %', '{:.3f}%'),
        ('Stopped %', 'Stopped %', '{:.1f}%'),
        ('Avg Win', 'Avg Win', '${:.2f}'),
        ('Avg Loss', 'Avg Loss', '${:.2f}'),
    ]
    
    # Pre-calc stats
    all_stats = [calc_single_stats(d['merged']) for d in datasets]
    
    for label, key, fmt in metrics:
        row = [f"**{label}**"]
        for stats in all_stats:
            val = stats.get(key, 0)
            row.append(fmt.format(val))
        report.append("| " + " | ".join(row) + " |")
        
    report.append("")
    report.append("---") 
    report.append("")

    # =================
    # HOURLY P&L
    # =================
    report.append("## ⏰ HOURLY PERFORMANCE (Total P&L)")
    report.append("")
    
    hours = sorted(list(set(h for d in datasets for h in d['merged']['Hour'].unique())))
    
    header = ["Hour"] + [d['name'] for d in datasets]
    report.append("| " + " | ".join(header) + " |")
    report.append("|" + "|".join(["---"] * len(header)) + "|")
    
    for h in hours:
        row = [f"{h:02d}:00"]
        for d in datasets:
            df = d['merged']
            sub = df[df['Hour'] == h]
            pnl = sub['Net P&L USD'].sum()
            row.append(f"${pnl:,.0f}")
        report.append("| " + " | ".join(row) + " |")
        
    report.append("")
    report.append("---")
    report.append("")

    # =================
    # EXIT SIGNAL BREAKDOWN
    # =================
    report.append("## 🚪 EXIT SIGNAL ANALYSIS")
    report.append("")
    
    for d in datasets:
        name = d['name']
        df = d['merged']
        report.append(f"### {name} Exit Signals")
        report.append("")
        report.append("| Exit Signal | Count | Total P&L | Avg P&L |")
        report.append("|-------------|-------|-----------|---------|")
        
        # Aggregate by Exit Signal
        exits = df.groupby('Exit Signal')['Net P&L USD'].agg(['count', 'sum', 'mean']).sort_values('sum', ascending=False)
        
        for sig, row in exits.iterrows():
            report.append(f"| {sig} | {int(row['count'])} | ${row['sum']:,.0f} | ${row['mean']:.2f} |")
        report.append("")
        
    report.append("---")
    report.append("")

    # =================
    # YEARLY
    # =================
    report.append("## 📅 YEARLY PERFORMANCE")
    report.append("")
    
    years = sorted(list(set(y for d in datasets for y in d['merged']['Year'].unique())))
    header = ["Year"] + [d['name'] for d in datasets]
    report.append("| " + " | ".join(header) + " |")
    report.append("|" + "|".join(["---"] * len(header)) + "|")
    
    for y in years:
        row = [f"{y}"]
        for d in datasets:
            df = d['merged']
            sub = df[df['Year'] == y]
            pnl = sub['Net P&L USD'].sum()
            row.append(f"${pnl:,.0f}")
        report.append("| " + " | ".join(row) + " |")

    return '\n'.join(report)

if __name__ == '__main__':
    print("Loading datasets...")
    
    datasets = []
    
    # Fixed TP
    d1 = load_strategy_data(V3_FIXED_FILE, 'V3 Fixed TP')
    if d1: datasets.append(d1)
    
    # Adaptive
    d2 = load_strategy_data(V3_ADAPTIVE_FILE, 'V3 Adaptive')
    if d2: datasets.append(d2)
    
    # Time Exit
    d3 = load_strategy_data(V3_TIME_FILE, 'V3 Time Exit')
    if d3: datasets.append(d3)
    
    # V2 Baseline
    d4 = load_strategy_data(V2_FILE, 'V2 Baseline')
    if d4: datasets.append(d4)
    
    print(f"Loaded {len(datasets)} datasets.")
    
    if len(datasets) > 0:
        print("Generating report...")
        report_content = generate_report(datasets)
        
        out_file = 'V3_vs_V2_Comprehensive_Analysis.md'
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
            
        print(f"DONE. Report saved to {out_file}")
