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
    
    # 5. COMBINED EDGE
    combined_edge = ev_r * pf
    
    # 6. SQN (Based on R-multiples)
    df['R_Multiple'] = df['Net P&L USD'] / risk_r
    mean_r = df['R_Multiple'].mean()
    std_r = df['R_Multiple'].std()
    sqn = (mean_r / std_r) * (trades ** 0.5) if std_r > 0 else 0
    
    # Combined Edge (For Grading - Raw Dollars as per User Text Section 8)
    # "CombinedEdge = EV * PF" -> grading A > 150
    combined_edge_raw = ev_dollars * pf
    
    # 7. MAX LOSING STREAK (Theoretical)
    try:
        max_streak_theoretical = np.log(trades) / np.log(1 / loss_rate) if loss_rate > 0 else 0
    except:
        max_streak_theoretical = 0
        
    # 8. RISK OF RUIN (RoR)
    # Uses Normalized Combined Edge: ev_r * pf
    bankroll_units = 20
    try:
        ror_calc = (1 - combined_edge) / (1 + combined_edge)
        if ror_calc <= 0:
            ror = 0.0 
        else:
            ror = (ror_calc ** bankroll_units) * 100
    except:
        ror = 100.0

    # GRADING LOGIC
    grade = "F"
    if combined_edge_raw > 150: grade = "A+"
    elif combined_edge_raw > 100: grade = "A"
    elif combined_edge_raw > 50: grade = "B"
    elif combined_edge_raw > 20: grade = "C"
    elif combined_edge_raw > 0: grade = "D"
    else: grade = "F"
    
    # Adjust grade based on SQN/RoR (downgrade if dangerous)
    if ror > 5.0: grade = f"{grade} (Dangerous RoR)"
    if sqn < 1.0 and "F" not in grade: grade = f"{grade} (Low Quality)"

    stats = {
        'Trades': trades,
        'Win Rate %': win_rate * 100,
        'Total P&L': total_pnl,
        'Avg P&L (EV)': ev_dollars,
        'Avg Loss (R)': risk_r,
        'Profit Factor': pf,
        'Combined Edge (Norm)': combined_edge,
        'Combined Edge (Raw)': combined_edge_raw,
        'Grade': grade,
        'SQN': sqn,
        'RoR %': ror,
        'Max Losing Streak (Est)': max_streak_theoretical,
        'Avg MFE %': df['MFE %'].mean() if 'MFE %' in df.columns else 0
    }
    return stats

def get_recommendations(stats):
    recs = []
    
    # EV Fixes
    if stats['Avg P&L (EV)'] < 20: # Weak EV
        recs.append("🔴 **Fix EV**: Increase AvgWin (let winners run) or Reduce AvgLoss.")
        
    # PF Fixes
    if stats['Profit Factor'] < 1.4:
        recs.append("🟠 **Fix PF**: Review MAE to cut outlier losses. Tighten stops?")
        
    # RoR Fixes
    if stats['RoR %'] > 2.0:
        recs.append("🔴 **Fix RoR (CRITICAL)**: REDUCE RISK PER TRADE immediately.")
        
    # Combined Edge
    if stats['Combined Edge (Raw)'] < 50:
        recs.append("🟡 **Fix Edge**: System is weak (Grade C/D). Needs better filters (Win%).")
        
    # SQN
    if stats['SQN'] < 2.0:
        recs.append("🟠 **Fix SQN**: Consistency is low. System may be too volatile.")
        
    if not recs:
        recs.append("🟢 **System Healthy**: Consider scaling size (Grade A/B).")
        
    return recs

def generate_report(datasets):
    report = []
    report.append("# V3 Comprehensive Strategy Grade & Analysis")
    report.append(f"## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("---")
    
    # 1. EXECUTIVE GRADING
    report.append("## 🏆 SYSTEM GRADING REPORT")
    report.append("")
    
    headers = ["Metric"] + [d['name'] for d in datasets]
    report.append("| " + " | ".join(headers) + " |")
    report.append("|" + "|".join(["---"] * len(headers)) + "|")
    
    all_stats = [calc_stats_extended(d['merged']) for d in datasets]
    all_recs = [get_recommendations(s) for s in all_stats]
    
    grading_metrics = [
        ('Overall Grade', 'Grade', '{}'),
        ('Combined Edge (Score)', 'Combined Edge (Raw)', '{:.1f}'),
        ('SQN (Quality)', 'SQN', '{:.2f}'),
        ('Profit Factor', 'Profit Factor', '{:.2f}'),
        ('Calculated RoR', 'RoR %', '{:.4f}%'),
        ('Expected Value ($)', 'Avg P&L (EV)', '${:.2f}'),
    ]

    for label, key, fmt in grading_metrics:
        row = [f"**{label}**"]
        for stats in all_stats:
            row.append(fmt.format(stats.get(key, 0)))
        report.append("| " + " | ".join(row) + " |")
        
    report.append("")
    
    # 2. ACTIONABLE RECOMMENDATIONS
    report.append("## 🛠️ ACTIONABLE RECOMMENDATIONS (THE FIX TABLE)")
    report.append("")
    
    for i, d in enumerate(datasets):
        name = d['name']
        recs = all_recs[i]
        grade = all_stats[i]['Grade']
        report.append(f"### {name} (Grade: {grade})")
        for r in recs:
            report.append(f"- {r}")
        report.append("")
        
    report.append("---")
    
    # 3. DETAILED PERFORMANCE (Previous Tables)
    report.append("## 📊 DETAILED PERFORMANCE METRICS")
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
