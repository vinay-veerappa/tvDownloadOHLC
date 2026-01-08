"""
Comprehensive Strategy Analysis & Grading Tool (The Edge System)
============================================================
Author: AI Assistant
Date: 2026-01-07
Purpose: 
    To load TradingView backtest exports, calculate advanced risk metrics (Edge System), 
    and generate a graded performance report.

The "Edge System" Metrics:
1.  Risk ($): The average loss per trade (used as the base unit 'R').
2.  Expected Value (EV): Average P&L per trade.
3.  Profit Factor: Gross Profit / Gross Loss.
4.  Combined Edge: (EV / Risk) * Profit Factor.
5.  SQN: System Quality Number (Mean R / Std R * sqrt(N)).
6.  RoR: Risk of Ruin based on Combined Edge and Bankroll.
7.  DRR: Drawdown Risk Rating (MaxDD / Risk).

Input:
    - Excel files (.xlsx) exported from TradingView 'List of Trades'.
    - Must contain columns: 'Type', 'Signal', 'Date and time', 'Price USD', 'Net P&L USD', 'MAE USD', 'MFE USD'.

Output:
    - Markdown Report (`V3_Comprehensive_Analysis.md`) containing:
        - 10-Metric Scorecard
        - System Grades (A-F)
        - Actionable Recommendations (Fix Table)
        - Time Analysis (5m, 15m, Hourly, Daily, Monthly)
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import glob

warnings.filterwarnings('ignore')

# --- CONFIGURATION: INPUT FILES ---
# Update these paths to point to new backtest exports
V3_FIXED_FILE = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_620dd.xlsx'
V3_ADAPTIVE_FILE = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_52358.xlsx'
V3_TIME_FILE = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_cfbde.xlsx'
V2_FILE = r'old\ORB_All-Day_V2_CME_MINI_MNQ1!_2026-01-07_06a7f.xlsx'

def load_strategy_data(filepath, name):
    """
    Load and process strategy data from TradingView Excel export.
    
    Handles the TradingView export quirk where P&L is duplicated on Entry and Exit rows.
    Logic:
    1. Read 'List of trades' sheet.
    2. Filter 'Exit' rows to get P&L, MFE, MAE.
    3. Filter 'Entry' rows to get Entry Signal, Price, Time.
    4. Merge Entry info into Exit rows based on 'Trade #'.
    
    Args:
        filepath (str): Path to .xlsx file.
        name (str): Display name for the strategy.
        
    Returns:
        dict: {'name': str, 'merged': DataFrame} or None if failed.
    """
    try:
        xl = pd.ExcelFile(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None
    
    # Locate the correct sheet (usually "List of trades")
    sheet = next((s for s in xl.sheet_names if s.lower() == "list of trades"), "List of trades")
    trade_list = pd.read_excel(xl, sheet_name=sheet)
    trade_list['Date and time'] = pd.to_datetime(trade_list['Date and time'])
    
    # Split into Entries and Exits
    entries = trade_list[trade_list['Type'].str.contains('Entry', case=False, na=False)].copy()
    exits = trade_list[trade_list['Type'].str.contains('Exit', case=False, na=False)].copy()
    
    # Prepare Entries (Source of Time/Signal)
    entries = entries[['Trade #', 'Date and time', 'Signal', 'Price USD']].copy()
    entries.columns = ['Trade #', 'Entry Time', 'Entry Signal', 'Entry Price']
    
    # Prepare Exits (Source of P&L/MAE/MFE)
    cols_to_use = ['Trade #', 'Date and time', 'Type', 'Signal', 'Price USD', 
                   'Net P&L USD', 'Net P&L %', 'MFE USD', 'MFE %', 'MAE USD', 'MAE %']
    cols_to_use = [c for c in cols_to_use if c in exits.columns]
    exits = exits[cols_to_use].copy()
    
    # Rename for clarity
    rename_map = { 'Date and time': 'Exit Time', 'Price USD': 'Exit Price' }
    exits.rename(columns=rename_map, inplace=True)
    if 'Signal' in exits.columns: exits.rename(columns={'Signal': 'Exit Signal'}, inplace=True)
    
    # Merge: Final Dataset has one row per trade (Exit) with Entry info attached
    merged = pd.merge(exits, entries, on='Trade #', how='left')
    merged['Strategy'] = name
    
    # --- TIME ANALYSIS COLUMNS ---
    merged['Hour'] = merged['Entry Time'].dt.hour
    merged['Minute'] = merged['Entry Time'].dt.minute
    merged['DayOfWeek'] = merged['Entry Time'].dt.day_name()
    merged['Month'] = merged['Entry Time'].dt.month
    merged['Year'] = merged['Entry Time'].dt.year
    merged['Date'] = merged['Entry Time'].dt.date
    merged['YearMonth'] = merged['Entry Time'].dt.to_period('M')
    
    # Time Buckets for Granular Analysis
    merged['15min_bucket'] = (merged['Minute'] // 15) * 15
    merged['5min_bucket'] = (merged['Minute'] // 5) * 5
    merged['Hour_Minute'] = merged['Hour'].astype(str).str.zfill(2) + ':' + merged['Minute'].astype(str).str.zfill(2)
    
    # Helper Flags
    merged['Is_Winner'] = merged['Net P&L USD'] > 0
    merged['Is_Stopped'] = merged['Exit Signal'].astype(str).str.contains('SL|Stop|MAE', case=False, na=False)
    
    return { 'name': name, 'merged': merged }

def calc_stats_extended(df):
    """
    Calculate the full suite of 'Edge System' metrics for a strategy dataframe.
    
    Implements:
    - EV, PF, Combined Edge
    - SQN (using R-multiples)
    - Risk of Ruin (RoR)
    - Drawdown Risk Rating (DRR)
    - Grading Logic (A-F)
    
    Args:
        df: DataFrame containing trade data.
        
    Returns:
        dict: A dictionary of calculated statistics.
    """
    if len(df) == 0: return {}
    
    wins = df[df['Net P&L USD'] > 0]
    losses = df[df['Net P&L USD'] <= 0]
    
    gross_profit = wins['Net P&L USD'].sum()
    gross_loss = abs(losses['Net P&L USD'].sum())
    
    trades = len(df)
    total_pnl = df['Net P&L USD'].sum()
    avg_pnl = df['Net P&L USD'].mean()
    std_pnl = df['Net P&L USD'].std()
    
    # Drawdown Calculation (Equity Curve)
    df_sorted = df.sort_values('Entry Time')
    equity = df_sorted['Net P&L USD'].cumsum()
    peak = equity.cummax()
    drawdown = equity - peak
    max_dd = drawdown.min()
    
    # --- RISK PROFILE CALCULATIONS (Per User Doc) ---
    
    # 1. RISK ($R)
    # Defined as AvgLoss (absolute). If no losses, use dummy 1 to avoid div/0
    avg_loss_abs = abs(losses['Net P&L USD'].mean()) if len(losses) > 0 else 1
    risk_r = avg_loss_abs
    
    # 2. EXPECTED VALUE (EV)
    win_rate = len(wins) / trades if trades > 0 else 0
    loss_rate = 1 - win_rate
    avg_win = wins['Net P&L USD'].mean() if len(wins) > 0 else 0
    
    ev_dollars = (win_rate * avg_win) - (loss_rate * risk_r)
    
    # 3. NORMALIZED EV (EV_R)
    ev_r = ev_dollars / risk_r
    
    # 4. PROFIT FACTOR (PF)
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # 5. COMBINED EDGE (Normalized)
    combined_edge = ev_r * pf
    
    # 6. SQN (Based on R-multiples)
    # Calculate R for every trade: PnL / Risk
    df['R_Multiple'] = df['Net P&L USD'] / risk_r
    mean_r = df['R_Multiple'].mean()
    std_r = df['R_Multiple'].std()
    sqn = (mean_r / std_r) * (trades ** 0.5) if std_r > 0 else 0
    
    # Combined Edge (For Grading - Raw Dollars as per User Text Section 8)
    # "CombinedEdge = EV * PF" -> grading A > 150
    combined_edge_raw = ev_dollars * pf
    
    # 7. MAX LOSING STREAK (Theoretical)
    # Formula: ln(N) / ln(1/Loss%)
    try:
        max_streak_theoretical = np.log(trades) / np.log(1 / loss_rate) if loss_rate > 0 else 0
    except:
        max_streak_theoretical = 0
        
    # 8. DRAWDOWN RISK RATING (DRR)
    # DRR = MaxDD ($) / Risk ($) -> "How many R's is the drawdown?"
    drr = abs(max_dd) / risk_r if risk_r > 0 else 0
        
    # 9. MAE/MFE RATIO
    avg_mae = df['MAE USD'].mean() if 'MAE USD' in df.columns else 0
    avg_mfe = df['MFE USD'].mean() if 'MFE USD' in df.columns else 0
    mae_mfe_ratio = abs(avg_mfe / avg_mae) if avg_mae != 0 else 0
    
    # 10. RISK OF RUIN (RoR)
    # Formula: ((1 - CombinedEdge) / (1 + CombinedEdge)) ^ Bankroll_Units
    bankroll_units = 20 # Standard assumption
    try:
        ror_calc = (1 - combined_edge) / (1 + combined_edge)
        if ror_calc <= 0:
            ror = 0.0 # Excellent (Edge is so strong RoR is 0)
        else:
            ror = (ror_calc ** bankroll_units) * 100
    except:
        ror = 100.0

    # GRADING LOGIC (A-F)
    grade = "F"
    if combined_edge_raw > 150: grade = "A+"
    elif combined_edge_raw > 100: grade = "A"
    elif combined_edge_raw > 50: grade = "B"
    elif combined_edge_raw > 20: grade = "C"
    elif combined_edge_raw > 0: grade = "D"
    else: grade = "F"
    
    # Downgrades for Risk Factors
    if ror > 5.0: grade = f"{grade} (Dangerous RoR)"
    if sqn < 1.0 and "F" not in grade: grade = f"{grade} (Low Quality)"
    if drr > 10 and "F" not in grade: grade = f"{grade} (High DRR)"

    stats = {
        'Trades': trades,
        'Win Rate %': win_rate * 100,
        'Total P&L': total_pnl,
        'Avg P&L (EV)': ev_dollars,
        'Risk ($)': risk_r,
        'Profit Factor': pf,
        'Combined Edge (Norm)': combined_edge,
        'Combined Edge (Raw)': combined_edge_raw,
        'Grade': grade,
        'SQN': sqn,
        'RoR %': ror,
        'Max Losing Streak (Est)': max_streak_theoretical,
        'DRR': drr,
        'Avg MAE ($)': avg_mae,
        'Avg MFE ($)': avg_mfe,
        'MAE/MFE Ratio': mae_mfe_ratio,
        'Max Drawdown ($)': max_dd
    }
    return stats

def get_recommendations(stats):
    """
    Generate actionable text recommendations based on the 'Fix Table'.
    Checks EV, PF, RoR, DRR thresholds and suggests specific fixes.
    """
    recs = []
    
    # Position Sizing Guide
    grade = stats['Grade'].split()[0] # Remove comments like "(High DRR)"
    size_msg = "0%"
    if "A" in grade: size_msg = "2-5%"
    elif "B" in grade: size_msg = "1-2%"
    elif "C" in grade: size_msg = "0.5-1%"
    elif "D" in grade: size_msg = "0.25-0.5%"
    
    recs.append(f"🔵 **Position Size**: {size_msg} Risk (Grade {grade})")
    
    # EV Fixes
    if stats['Avg P&L (EV)'] < 20: 
        recs.append("🔴 **Fix EV**: Increase AvgWin (let winners run) or Reduce AvgLoss.")
        
    # PF Fixes
    if stats['Profit Factor'] < 1.4:
        recs.append("🟠 **Fix PF**: Tighten stops to improve efficiency.")
        
    # RoR
    if stats['RoR %'] > 2.0:
        recs.append("🔴 **Fix RoR (CRITICAL)**: REDUCE RISK PER TRADE immediately.")
        
    # DRR
    if stats['DRR'] > 10:
        recs.append("🔴 **Fix DRR**: Drawdown is too deep relative to Risk. Reduce Risk/Trade.")

    # Healthy System
    if not recs or len(recs) == 1: # Only pos size
        recs.append("🟢 **System Healthy**: Consider scaling size.")
        
    return recs

def generate_time_table(datasets, key_col, key_label, title):
    """Generates a Markdown table for a specific time breakdown (e.g. Hourly, Daily)."""
    lines = []
    lines.append(f"### {title}")
    lines.append("")
    
    # Get all unique keys for the bucket (Sorted)
    all_keys = sorted(list(set(k for d in datasets for k in d['merged'][key_col].dropna().unique())))
    
    # Header
    names = [d['name'] for d in datasets]
    lines.append(f"| {key_label} | " + " | ".join(names) + " |")
    lines.append("|" + "|".join(["---"] * (len(names)+1)) + "|")
    
    for k in all_keys:
        row = [str(k)]
        for d in datasets:
            df = d['merged']
            val = df[df[key_col] == k]['Net P&L USD'].sum()
            row.append(f"${val:,.0f}")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return lines

def generate_report(datasets):
    """Constructs the full Markdown report string."""
    report = []
    report.append("# Strategy Grade & Comprehensive Metrics")
    report.append(f"## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("---")
    
    # 1. EXECUTIVE GRADING (THE 10 METRICS)
    report.append("## 🏆 THE EDGE SYSTEM: 10 METRIC CARD")
    report.append("")
    
    headers = ["Metric"] + [d['name'] for d in datasets]
    report.append("| " + " | ".join(headers) + " |")
    report.append("|" + "|".join(["---"] * len(headers)) + "|")
    
    all_stats = [calc_stats_extended(d['merged']) for d in datasets]
    all_recs = [get_recommendations(s) for s in all_stats]
    
    # The 10 + Grade
    metrics_10 = [
        ('1. Risk ($)', 'Risk ($)', '${:.2f}'),
        ('2. Expected Value (EV)', 'Avg P&L (EV)', '${:.2f}'),
        ('3. Profit Factor', 'Profit Factor', '{:.2f}'),
        ('4. MAE/MFE Ratio', 'MAE/MFE Ratio', '{:.2f}'),
        ('5. SQN', 'SQN', '{:.2f}'),
        ('6. Max Streak (Est)', 'Max Losing Streak (Est)', '{:.1f}'),
        ('7. DRR (Drawdown R)', 'DRR', '{:.1f}'),
        ('8. Combined Edge (Raw)', 'Combined Edge (Raw)', '{:.1f}'),
        ('9. Risk of Ruin', 'RoR %', '{:.4f}%'),
        ('10. Max Drawdown', 'Max Drawdown ($)', '${:,.0f}'),
        ('FINAL GRADE', 'Grade', '**{}**'),
    ]

    for label, key, fmt in metrics_10:
        row = [f"**{label}**"]
        for stats in all_stats:
            val = stats.get(key, 0)
            if isinstance(val, str):
                row.append(val)
            else:
                row.append(fmt.format(val))
        report.append("| " + " | ".join(row) + " |")
        
    report.append("")
    
    # 2. RECOMMENDATIONS
    report.append("## 🛠️ ACTIONABLE RECOMMENDATIONS")
    for i, d in enumerate(datasets):
        name = d['name']
        recs = all_recs[i]
        report.append(f"### {name}")
        for r in recs:
            report.append(f"- {r}")
        report.append("")
    
    report.append("---")
    
    # 3. GRANULAR TIME ANALYSIS
    report.append("## ⏰ GRANULAR TIME BREAKDOWN")
    
    # 5-Min
    report.extend(generate_time_table(datasets, '5min_bucket', '5-Min Bucket', '5-Minute Resolution'))
    
    # 15-Min
    report.extend(generate_time_table(datasets, '15min_bucket', '15-Min Bucket', '15-Minute Resolution'))
    
    # Hourly
    report.extend(generate_time_table(datasets, 'Hour', 'Hour', 'Hourly Resolution'))
    
    # Daily
    report.extend(generate_time_table(datasets, 'DayOfWeek', 'Day', 'Day of Week'))
    
    report.append("---")
    report.append("## 📅 PERIODIC BREAKDOWN")
    
    # Date helper for buckets
    for d in datasets:
        d['merged']['Quarter'] = d['merged']['Entry Time'].dt.to_period('Q')
    
    # Quarterly
    report.extend(generate_time_table(datasets, 'Quarter', 'Quarter', 'Quarterly Performance'))
    
    # Yearly
    report.extend(generate_time_table(datasets, 'Year', 'Year', 'Yearly Performance'))

    return '\n'.join(report)
    # ... rest of report remains similar, just shorter summary
    
    metrics = [
        ('Trades', 'Trades', '{:.0f}'),
        ('Total P&L', 'Total P&L', '${:,.2f}'),
        ('Example R (AvgLoss)', 'Avg Loss (R)', '${:,.2f}'),
        ('Win Rate %', 'Win Rate %', '{:.2f}%'),
        ('Expected Value (EV)', 'Avg P&L (EV)', '${:.2f}'),
    ]
    
    for label, key, fmt in metrics:
        row = [f"**{label}**"]
        for stats in all_stats:
            row.append(fmt.format(stats.get(key, 0)))
        report.append("| " + " | ".join(row) + " |")
    
    report.append("")
    report.append("---")
    report.append("")

    # 2. RISK PROFILING (ADVANCED)
    report.append("## 🛡️ RISK PROFILING (PER EDGE SYSTEM)")
    report.append("")
    report.append("| Metric | " + " | ".join([d['name'] for d in datasets]) + " |")
    report.append("|" + "|".join(["---"] * (len(datasets)+1)) + "|")

    risk_metrics = [
        ('Profit Factor', 'Profit Factor', '{:.2f}'),
        ('Combined Edge (Norm)', 'Combined Edge (Norm)', '{:.2f}'),
        ('SQN (Trade Quality)', 'SQN', '{:.2f}'),
        ('Risk of Ruin %', 'RoR %', '{:.4f}%'),
        ('Max Streak (Theory)', 'Max Losing Streak (Est)', '{:.1f}'),
    ]

    for label, key, fmt in risk_metrics:
        row = [f"**{label}**"]
        for stats in all_stats:
            row.append(fmt.format(stats.get(key, 0)))
        report.append("| " + " | ".join(row) + " |")

    report.append("")
    report.append("### Metric Grades")
    report.append("> **Combined Edge**: > 50 is Good. > 100 is Excellent.")
    report.append("> **SQN**: > 2.0 is Good. > 3.0 is Excellent.")
    report.append("> **RoR**: < 1% is Excellent. > 10% is Dangerous.")
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
        
    report.append("")
    report.append("---")
    report.append("")

    # 5. STRATEGY CONFIGURATION & DIFFERENCES
    report.append("## ⚙️ STRATEGY CONFIGURATION & DIFFERENCES")
    report.append("")
    report.append("### Parameter Settings by Mode")
    report.append("")
    report.append("| Parameter | V3 Fixed TP (Winner) | V3 Adaptive | V3 Time Exit | V2 Baseline |")
    report.append("|---|---|---|---|---|")
    report.append("| **Runner Mode** | `Fixed TP` | `Adaptive (Time + Trail)` | `Time Exit` | `Time Exit` |")
    report.append("| **TP1** | 0.15% (30%) | 0.15% (30%) | 0.15% (30%) | n/a |")
    report.append("| **TP2** | 0.25% (30%) | 0.25% (30%) | 0.25% (30%) | n/a |")
    report.append("| **TP3 / Runner** | 0.50% (40%) | **Adaptive Trail** | **Hold to 15:55** | Hold to 15:55 |")
    report.append("| **Trail Activation** | n/a | **0.50%** | n/a | n/a |")
    report.append("| **Trail Offset** | n/a | **0.25%** | n/a | n/a |")
    report.append("| **Stop Loss** | 0.22% | 0.22% | 0.22% | Market Structure |")
    report.append("| **Min Contracts** | 3 (Ensures all TPs hit) | 3 | 3 | 1 (Risk of partials) |")
    report.append("")
    report.append("### Key Differences")
    report.append("1.  **V3 Fixed TP**: Takes all risk off the table by 0.50%. Maximizes **Win Rate** and **SQN** by banking profits in the volatile 2023-2025 regime.")
    report.append("2.  **V3 Adaptive**: Validated logic. Holds for trend but **activates protection** if price hits +0.50%. If price retraces 0.25% from peak, it exits. Captures trends but prevents full giveback.")
    report.append("3.  **V3 Time Exit**: Pure trend following. Holds the last 40% until 15:55 ET. Vulnerable to afternoon reversals (Giveback).")
    report.append("4.  **V2 Baseline**: The original strategy. Lower position sizing (1 contract min) and looser filters resulted in lower total profit.")
    
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
        out_file = 'V3_Comprehensive_Analysis.md'
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"DONE. Report saved to {out_file}")
