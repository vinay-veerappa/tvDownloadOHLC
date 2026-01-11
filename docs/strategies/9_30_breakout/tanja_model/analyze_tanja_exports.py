"""
Comprehensive Strategy Analysis & Grading Tool (The Edge System)
============================================================
Author: AI Assistant
Date: 2026-01-08 (Hyper-Precision Update)
Purpose: 
    To load TradingView backtest exports, calculate advanced risk metrics (Edge System), 
    run Monte Carlo simulations, and generate a hyper-precise forensic report.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import glob

warnings.filterwarnings('ignore')

# --- CONFIGURATION: DYNAMIC INPUT ---
INPUT_PATTERN = r"ORBv6-Tanja*.xlsx"

# --- MARKET CONTEXT KNOWLEDGE BASE ---
# Maps (Year, Quarter) to a brief macro tag. 
# 0 = All Quarters generic tag
MACRO_CONTEXT = {
    (2020, 1): "COVID Crash", (2020, 2): "Fed Stimulus Injection",
    (2021, 1): "Meme Stock Mania", (2021, 4): "Peak Liquidity",
    (2022, 1): "Rate Hike Begins", (2022, 2): "Inflation Panic",
    (2023, 1): "AI Rally Start", (2023, 3): "Higher for Longer",
    (2024, 4): "Election Rally", 
    (2025, 1): "Soft Landing Confirmed",
}

def load_properties(filepath):
    props = {}
    try:
        xl = pd.ExcelFile(filepath)
        sheet = next((s for s in xl.sheet_names if any(x in s.lower() for x in ['propert', 'setting', 'input'])), None)
        if sheet:
            df = pd.read_excel(xl, sheet_name=sheet)
            if len(df.columns) >= 2:
                for index, row in df.iterrows():
                    key = str(row[0]).strip()
                    val = str(row[1]).strip()
                    props[key] = val
    except Exception as e:
        print(f"Warning: Could not load properties for {os.path.basename(filepath)}: {e}")
    return props

def load_strategy_data(filepath, name):
    try:
        xl = pd.ExcelFile(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None
    
    sheet = next((s for s in xl.sheet_names if s.lower() == "list of trades"), "List of trades")
    trade_list = pd.read_excel(xl, sheet_name=sheet)
    trade_list['Date and time'] = pd.to_datetime(trade_list['Date and time'])
    
    props = load_properties(filepath)
    
    entries = trade_list[trade_list['Type'].str.contains('Entry', case=False, na=False)].copy()
    exits = trade_list[trade_list['Type'].str.contains('Exit', case=False, na=False)].copy()
    
    if 'Signal' not in entries.columns: entries['Signal'] = 'Entry'
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
    
    # --- TIME COLUMNS ---
    merged['Hour'] = merged['Entry Time'].dt.hour
    merged['Minute'] = merged['Entry Time'].dt.minute
    merged['Month'] = merged['Entry Time'].dt.month
    merged['Quarter'] = merged['Entry Time'].dt.quarter
    merged['Year'] = merged['Entry Time'].dt.year
    merged['Date'] = merged['Entry Time'].dt.date
    merged['DayOfWeek'] = merged['Entry Time'].dt.day_name() # Monday, Tuesday...
    
    # Precise Time Slot (e.g., "09:30")
    merged['TimeSlot'] = merged['Entry Time'].dt.strftime('%H:%M')
    
    # Granular Buckets
    merged['15min_bucket'] = (merged['Minute'] // 15) * 15
    merged['5min_bucket'] = (merged['Minute'] // 5) * 5
    merged['Q_Hour'] = pd.cut(merged['Minute'], bins=[-1, 14, 29, 44, 59], labels=['Q1', 'Q2', 'Q3', 'Q4'])

    # Helper Flags
    merged['Is_Winner'] = merged['Net P&L USD'] > 0
    
    return { 'name': name, 'merged': merged, 'props': props }

def perform_monte_carlo(pnl_array, iterations=2500):
    all_max_dd = []
    equity_curve = np.cumsum(pnl_array)
    peak = np.maximum.accumulate(equity_curve)
    orig_dd = (equity_curve - peak).min()
    for _ in range(iterations):
        shuffled = np.random.permutation(pnl_array)
        eq = np.cumsum(shuffled)
        peak_sim = np.maximum.accumulate(eq)
        dd_sim = (eq - peak_sim).min()
        all_max_dd.append(dd_sim)

    dd_p95 = np.percentile(all_max_dd, 5) 
    dd_median = np.median(all_max_dd)
    prob_2k = np.sum(np.array(all_max_dd) < -2000) / iterations * 100
    return { "mc_orig_dd": orig_dd, "mc_median_dd": dd_median, "mc_95_dd": dd_p95, "mc_prob_2k": prob_2k }

def calc_stats_extended(df):
    if len(df) == 0: return {}
    wins = df[df['Net P&L USD'] > 0]
    losses = df[df['Net P&L USD'] <= 0]
    trades = len(df)
    total_pnl = df['Net P&L USD'].sum()
    gross_profit = wins['Net P&L USD'].sum()
    gross_loss = abs(losses['Net P&L USD'].sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    avg_loss_abs = abs(losses['Net P&L USD'].mean()) if len(losses) > 0 else 1
    risk_r = avg_loss_abs
    win_rate = len(wins) / trades if trades > 0 else 0
    avg_win = wins['Net P&L USD'].mean() if len(wins) > 0 else 0
    ev_dollars = (win_rate * avg_win) - ((1 - win_rate) * risk_r)
    combined_edge_raw = ev_dollars * pf
    df['R_Multiple'] = df['Net P&L USD'] / risk_r
    std_r = df['R_Multiple'].std()
    sqn = (df['R_Multiple'].mean() / std_r) * (trades ** 0.5) if std_r > 0 else 0
    check_streak = df['Is_Winner'].ne(df['Is_Winner'].shift()).cumsum()
    streaks = df.groupby(check_streak)['Is_Winner'].agg(['first', 'size'])
    losing_streaks = streaks[streaks['first'] == False]
    max_losing_streak = losing_streaks['size'].max() if not losing_streaks.empty else 0
    df_sorted = df.sort_values('Entry Time')
    eq = df_sorted['Net P&L USD'].cumsum()
    peak = eq.cummax()
    max_dd = (eq - peak).min()
    daily_pnl = df.groupby('Date')['Net P&L USD'].sum()
    max_daily_loss = daily_pnl.min()
    mc_results = perform_monte_carlo(df['Net P&L USD'].values)
    drr = abs(max_dd) / risk_r if risk_r > 0 else 0
    
    grade = "F"
    if combined_edge_raw > 150: grade = "A+"
    elif combined_edge_raw > 100: grade = "A"
    elif combined_edge_raw > 50: grade = "B"
    elif combined_edge_raw > 20: grade = "C"
    elif combined_edge_raw > 0: grade = "D"
    if drr > 10: grade += " (High DRR)"

    stats = {
        'Trades': trades, 'Win Rate %': win_rate * 100, 'Total P&L': total_pnl, 'Profit Factor': pf,
        'Max Trailing DD': max_dd, 'Max Daily Loss': max_daily_loss, 'SQN': sqn, 'Combined Edge': combined_edge_raw,
        'Grade': grade, 'Risk ($)': risk_r, 'Max Loss Streak': max_losing_streak, 'Avg Win': avg_win,
        'Avg Loss': -risk_r, 'DRR': drr, 'MC Median DD': mc_results['mc_median_dd'], 'MC 95% DD': mc_results['mc_95_dd'],
        'MC Prob >2k': mc_results['mc_prob_2k']
    }
    return stats

def get_recommendations(stats):
    recs = []
    if stats['Profit Factor'] < 1.4: recs.append("🟠 **Fix PF**: Tighten stops.")
    if stats['MC Prob >2k'] > 1.0: recs.append("🔴 **High Risk**: >1% chance of $2k DD.")
    if stats['DRR'] > 10: recs.append("🔴 **Deep Drawdown**: Volatile.")
    if not recs: recs.append("🟢 **System Healthy**")
    return recs

def generate_entry_timing_analysis(df, name):
    lines = []
    lines.append(f"#### {name} Precision Matrices")
    
    # 1. Day x Hour Matrix
    lines.append("**Day of Week x Hour Performance ($)**")
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    df['DayOfWeek'] = pd.Categorical(df['DayOfWeek'], categories=day_order, ordered=True)
    
    dh_pivot = df.pivot_table(index='DayOfWeek', columns='Hour', values='Net P&L USD', aggfunc='sum').fillna(0)
    
    # Headers
    cols = sorted(list(dh_pivot.columns))
    headers = [f"{c}:00" for c in cols]
    lines.append(f"| Day | {' | '.join(headers)} |")
    lines.append("|---" + "|---" * len(cols) + "|")
    
    for day in day_order:
        if day in dh_pivot.index:
            row = dh_pivot.loc[day]
            vals = [f"${v/1000:.1f}k" if abs(v) > 999 else f"${v:.0f}" for v in row]
            lines.append(f"| **{day}** | {' | '.join(vals)} |")
    lines.append("")

    # 2. Year x Quarter Breakdown
    lines.append("**Year x Quarter Performance ($) with Context**")
    lines.append("| Year-Qtr | P&L | Trades | Context/News |")
    lines.append("|---|---|---|---|")
    
    yq_groups = df.groupby(['Year', 'Quarter']).agg({'Net P&L USD': 'sum', 'Trade #': 'count'}).reset_index()
    for _, row in yq_groups.iterrows():
        yr = int(row['Year'])
        qtr = int(row['Quarter'])
        pnl = row['Net P&L USD']
        cnt = row['Trade #']
        
        ctx = MACRO_CONTEXT.get((yr, qtr), "-")
        lines.append(f"| {yr}-Q{qtr} | ${pnl:,.0f} | {int(cnt)} | {ctx} |")
    lines.append("")

    return lines

def generate_golden_minutes(df, name):
    lines = []
    # Group by TimeSlot (Hour:Minute)
    ts_stats = df.groupby('TimeSlot').agg({
        'Net P&L USD': 'sum', 
        'Trade #': 'count', 
        'Is_Winner': 'mean'
    }).reset_index()
    
    # Filter noise
    ts_stats = ts_stats[ts_stats['Trade #'] >= 5]
    
    # Top 5
    best = ts_stats.sort_values('Net P&L USD', ascending=False).head(5)
    worst = ts_stats.sort_values('Net P&L USD', ascending=True).head(5)
    
    lines.append(f"#### {name} - Golden Minutes (Specific Time)")
    lines.append("| Time | P&L | Win% | Trades |")
    lines.append("|---|---|---|---|")
    for _, r in best.iterrows():
        lines.append(f"| **{r['TimeSlot']}** | ${r['Net P&L USD']:,.0f} | {r['Is_Winner']*100:.1f}% | {int(r['Trade #'])} |")
        
    lines.append(f"#### {name} - Toxic Minutes (Specific Time)")
    lines.append("| Time | P&L | Win% | Trades |")
    lines.append("|---|---|---|---|")
    for _, r in worst.iterrows():
        lines.append(f"| **{r['TimeSlot']}** | ${r['Net P&L USD']:,.0f} | {r['Is_Winner']*100:.1f}% | {int(r['Trade #'])} |")
    lines.append("")
    return lines

def generate_report(datasets):
    report = []
    report.append("# Strategy Grade & Comprehensive Metrics")
    report.append(f"## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("---")
    
    # 1. SCORECARD
    report.append("## 🏆 THE EDGE SYSTEM: SCORECARD")
    headers = ["Metric"] + [d['name'] for d in datasets]
    report.append("| " + " | ".join(headers) + " |")
    report.append("|" + "|".join(["---"] * len(headers)) + "|")
    
    all_stats = [calc_stats_extended(d['merged']) for d in datasets]
    all_recs = [get_recommendations(s) for s in all_stats]
    
    metrics = [
        ('1. Profit Factor', 'Profit Factor', '{:.2f}'),
        ('2. Win Rate %', 'Win Rate %', '{:.2f}%'),
        ('3. Total P&L', 'Total P&L', '${:,.2f}'),
        ('4. Max Trailing DD', 'Max Trailing DD', '${:,.0f}'),
        ('5. Max Daily Loss', 'Max Daily Loss', '${:,.0f}'),
        ('6. SQN', 'SQN', '{:.2f}'),
        ('7. Combined Edge', 'Combined Edge', '{:.1f}'),
        ('FINAL GRADE', 'Grade', '**{}**'),
    ]
    for label, key, fmt in metrics:
        row = [f"**{label}**"]
        for stats in all_stats:
            val = stats.get(key, 0)
            row.append(fmt.format(val) if not isinstance(val, str) else val)
        report.append("| " + " | ".join(row) + " |")
    report.append("")
    report.append("## 🛠️ RECOMMENDATIONS")
    for i, d in enumerate(datasets):
        report.append(f"- **{d['name']}**: {'; '.join(all_recs[i])}")
    report.append("")
    report.append("---")
    
    report.append("## 💀 RISK & ROBUSTNESS (Monte Carlo)")
    report.append("| Metric | " + " | ".join([d['name'] for d in datasets]) + " |")
    report.append("|" + "|".join(["---"] * (len(datasets)+1)) + "|")
    risk_metrics = [
        ('1. Avg Risk (R)', 'Risk ($)', '${:,.2f}'),
        ('3. Actual Max DD', 'Max Trailing DD', '${:,.0f}'),
        ('4. Monte Carlo Median DD', 'MC Median DD', '${:,.0f}'),
        ('5. Monte Carlo 95% DD', 'MC 95% DD', '${:,.0f}'),
        ('7. DRR Score', 'DRR', '{:.1f}'),
    ]
    for label, key, fmt in risk_metrics:
        row = [f"**{label}**"]
        for stats in all_stats:
            val = stats.get(key, 0)
            row.append(fmt.format(val) if not isinstance(val, str) else val)
        report.append("| " + " | ".join(row) + " |")
    report.append("")
    report.append("---")
    
    # 2. CONFIGURATION VERIFICATION
    report.append("## ⚙️ CONFIGURATION VERIFICATION")
    
    # Collect all unique keys from all datasets
    all_keys = set()
    for d in datasets:
        all_keys.update(d['props'].keys())
    
    # Find keys where values differ across datasets
    differing_keys = []
    
    # Also include specific important keys even if they don't differ (optional, but good for context)
    important_keys = ["Tanja Mode", "Entry Mode", "Stop Loss Mode"]
    
    sorted_keys = sorted(list(all_keys))
    
    for key in sorted_keys:
        values = [str(d['props'].get(key, "-")) for d in datasets]
        # Check if set has more than 1 unique value (ignoring potential minor format diffs if needed)
        if len(set(values)) > 1 or key in important_keys:
            differing_keys.append(key)
            
    # If no differences, fallback to some defaults or message
    if not differing_keys:
        differing_keys = ["(No setting differences found)"]

    report.append("| Parameter | " + " | ".join([d['name'] for d in datasets]) + " |")
    report.append("|" + "|".join(["---"] * (len(datasets)+1)) + "|")
    
    for key in differing_keys:
        if key == "(No setting differences found)":
             report.append(f"| {key} | " + " | ".join(["-" for _ in datasets]) + " |")
             continue
             
        row = [f"**{key}**"]
        for d in datasets:
            val = d['props'].get(key, "-")
            row.append(str(val))
        report.append("| " + " | ".join(row) + " |")

    report.append("")
    report.append("---")
    
    # 3. HYPER-PRECISION MATRIX
    report.append("## ⏰ HYPER-PRECISION TIME ANALYSIS")
    
    # A. Day x Hour & Year x Quarter
    for d in datasets:
        report.extend(generate_entry_timing_analysis(d['merged'], d['name']))
        
    # B. Golden Minutes
    report.append("### ⚡ PRECISE ENTRY OPTIMIZATION")
    for d in datasets:
        report.extend(generate_golden_minutes(d['merged'], d['name']))
        
    # C. 5-Min P&L & W/L Ratio Matrix (Retained)
    for d in datasets:
        report.append(f"#### {d['name']} 5-Minute Distribution Matrices")
        df = d['merged']
        df['Bucket5'] = (df['Minute'] // 5) * 5
        
        # P&L
        pnl = df.pivot_table(index='Hour', columns='Bucket5', values='Net P&L USD', aggfunc='sum').fillna(0)
        # W/L Count
        def wl_fmt(s): return f"{s.sum()}/{s.count()-s.sum()}"
        wl = df.pivot_table(index='Hour', columns='Bucket5', values='Is_Winner', aggfunc=wl_fmt).fillna("-")
        
        # Helper to render pivot
        def render(pivot, title, fmt):
            ls = []
            ls.append(f"**{title}**")
            for c in range(0, 60, 5): 
                if c not in pivot.columns: pivot[c] = 0
            cols = sorted(list(pivot.columns))
            ls.append(f"| Hour | {' | '.join([f':{c:02d}' for c in cols])} |")
            ls.append("|---" + "|---" * len(cols) + "|")
            for h, r in pivot.iterrows():
                vals = [fmt(r[c]) for c in cols]
                ls.append(f"| **{h}:00** | {' | '.join(vals)} |")
            ls.append("")
            return ls
            
        report.extend(render(pnl, "5-Minute P&L ($)", lambda v: f"${v/1000:.1f}k" if abs(v)>999 else f"${v:.0f}"))
        report.extend(render(wl, "5-Minute W/L Count", lambda v: str(v)))

    return '\n'.join(report)

if __name__ == '__main__':
    print(f"Searching for files: {INPUT_PATTERN}")
    files = glob.glob(INPUT_PATTERN)
    datasets = []
    
    # 1. Load All Datasets
    if files:
        for f in files:
            # Extract Ticker from filename logic
            # Format: ORB_V3_Doji_CME_MINI_MNQ1!_2026-01-08...
            # Split by '_' and find the ticker part (usually index 4 or 5)
            # We'll use a simple heuristic: Look for the part containing '!' or known tickers
            parts = os.path.basename(f).split('_')
            ticker = "UNKNOWN"
            for p in parts:
                if "!" in p:
                    ticker = p
                    break
            
            # Fallback if no specific ticker found
            if ticker == "UNKNOWN":
                # unexpected format, just treat as generic
                ticker = "GENERIC"

            name = os.path.basename(f).split('_')[-1].replace('.xlsx', '')
            print(f"Loading {name} ({ticker})...")
            
            data = load_strategy_data(f, name)
            if data: 
                # Enhance name with Tanja Mode if valid
                mode = data['props'].get('Tanja Mode', 'Unknown')
                # Shorten mode string for display
                if 'Smart' in mode: mode = 'Smart'
                elif 'Inverse' in mode: mode = 'Inverse'
                elif 'Trend' in mode: mode = 'Trend'
                elif 'Off' in mode: mode = 'Off'
                
                data['name'] = f"{name} ({mode})"
                data['ticker'] = ticker
                datasets.append(data)
            
    # 2. Group by Ticker & Generate Reports
    if datasets:
        # Get unique tickers
        unique_tickers = list(set(d['ticker'] for d in datasets))
        
        for t in unique_tickers:
            print(f"\nProcessing Group: {t}")
            # Filter for this ticker
            group = [d for d in datasets if d['ticker'] == t]
            
            # Sort by Profit Factor
            group.sort(key=lambda d: calc_stats_extended(d['merged']).get('Profit Factor', 0), reverse=True)
            
            # Generate Report
            # Clean ticker for filename (remove !, replace special chars)
            safe_ticker = t.replace('!', '').replace('^', '').replace('/', '')
            filename = f'Tanja_Analysis_{safe_ticker}.md'
            
            print(f"Generating report: {filename}...")
            content = generate_report(group)
            
            # Add Ticker Header to Report
            content = f"# {t} Strategy Forensics\n**Ticker**: {t}\n\n" + content
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
                
        print("\nALL DONE.")
