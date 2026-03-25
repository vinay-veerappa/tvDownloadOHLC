"""
Comprehensive V2 vs V7G Strategy Analysis
==========================================
Analyzes and compares two ORB strategies with detailed breakdowns by:
- Time (hour, 15-min, 5-min, 1-min buckets)
- Day of week
- Month and Year
- Entry/Exit signal types
- Stop-out analysis
- MFE/MAE percentage analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# File paths - Run 6 (Dynamic Min 3 Contracts)
V7G_FILE = 'ORB_V7G_-_Hybrid_CME_MINI_MNQ1!_2026-01-07_b8fb2.xlsx'
V2_FILE = 'ORB_All-Day_V2_CME_MINI_MNQ1!_2026-01-07_06a7f.xlsx'

def load_strategy_data(filepath, name):
    """Load and process strategy data from Excel"""
    xl = pd.ExcelFile(filepath)
    
    # Load all sheets
    performance = pd.read_excel(xl, sheet_name='Performance')
    trades_analysis = pd.read_excel(xl, sheet_name='Trades analysis')
    risk_adj = pd.read_excel(xl, sheet_name='Risk-adjusted performance')
    trade_list = pd.read_excel(xl, sheet_name='List of trades')
    
    # Parse datetime
    trade_list['Date and time'] = pd.to_datetime(trade_list['Date and time'])
    
    # Separate entries and exits
    entries = trade_list[trade_list['Type'].str.contains('Entry', na=False)].copy()
    exits = trade_list[trade_list['Type'].str.contains('Exit', na=False)].copy()
    
    # Create merged trades (entry + exit info)
    merged = entries[['Trade #', 'Date and time', 'Type', 'Signal', 'Price USD', 
                      'Net P&L USD', 'Net P&L %', 'MFE USD', 'MFE %', 'MAE USD', 'MAE %']].copy()
    merged.columns = ['Trade #', 'Entry Time', 'Entry Type', 'Entry Signal', 'Entry Price',
                      'Net P&L USD', 'Net P&L %', 'MFE USD', 'MFE %', 'MAE USD', 'MAE %']
    
    # Get exit signals
    exit_info = exits[['Trade #', 'Date and time', 'Signal']].copy()
    exit_info.columns = ['Trade #', 'Exit Time', 'Exit Signal']
    
    merged = merged.merge(exit_info, on='Trade #', how='left')
    merged['Strategy'] = name
    
    # Extract time components
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
    merged['Is_Stopped'] = merged['Exit Signal'].str.contains('SL|Stop|MAE', case=False, na=False)
    
    return {
        'name': name,
        'performance': performance,
        'trades_analysis': trades_analysis,
        'risk_adj': risk_adj,
        'trade_list': trade_list,
        'merged': merged
    }

def calc_stats(df, group_col=None):
    """Calculate comprehensive statistics for a DataFrame or group"""
    if group_col:
        groups = df.groupby(group_col)
        results = []
        for name, group in groups:
            stats = calc_single_stats(group)
            stats[group_col] = name
            results.append(stats)
        return pd.DataFrame(results)
    else:
        return calc_single_stats(df)

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
        'Median P&L': df['Net P&L USD'].median(),
        'Std P&L': df['Net P&L USD'].std(),
        'Avg MFE %': df['MFE %'].mean(),
        'Median MFE %': df['MFE %'].median(),
        'Avg MAE %': df['MAE %'].mean(),
        'Median MAE %': df['MAE %'].median(),
        'Stopped Out': df['Is_Stopped'].sum(),
        'Stopped %': df['Is_Stopped'].mean() * 100,
        'Avg Win': wins['Net P&L USD'].mean() if len(wins) > 0 else 0,
        'Avg Loss': losses['Net P&L USD'].mean() if len(losses) > 0 else 0,
        'Gross Profit': wins['Net P&L USD'].sum() if len(wins) > 0 else 0,
        'Gross Loss': abs(losses['Net P&L USD'].sum()) if len(losses) > 0 else 0,
    }
    
    # Advanced Risk Metrics
    stats['Profit Factor'] = stats['Gross Profit'] / stats['Gross Loss'] if stats['Gross Loss'] > 0 else float('inf')
    stats['EV'] = stats['Avg P&L']
    stats['SQN'] = (stats['Avg P&L'] / stats['Std P&L']) * (stats['Trades'] ** 0.5) if stats['Std P&L'] > 0 else 0
    
    # Drawdown Calculation
    df = df.sort_values('Entry Time')
    equity = df['Net P&L USD'].cumsum()
    peak = equity.cummax()
    drawdown = equity - peak
    stats['Max Drawdown'] = drawdown.min()
    stats['Return/DD'] = stats['Total P&L'] / abs(stats['Max Drawdown']) if stats['Max Drawdown'] < 0 else 0
    
    return stats

def generate_report(v2_data, v7g_data):
    """Generate comprehensive comparison report"""
    
    v2 = v2_data['merged']
    v7g = v7g_data['merged']
    
    report = []
    report.append("# V2 vs V7G Comprehensive Strategy Analysis")
    report.append(f"## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("---")
    report.append("")
    
    # =================
    # EXECUTIVE SUMMARY
    # =================
    report.append("## 📊 EXECUTIVE SUMMARY")
    report.append("")
    
    v2_stats = calc_single_stats(v2)
    v7g_stats = calc_single_stats(v7g)
    
    report.append("| Metric | V2 | V7G | Winner |")
    report.append("|--------|-----|-----|--------|")
    
    metrics = [
        ('Trades', 'Trades', True),  # higher not necessarily better
        ('Win Rate %', 'Win Rate %', True),
        ('Total P&L', 'Total P&L', True),
        ('Avg P&L', 'Avg P&L', True),
        ('Avg MFE %', 'Avg MFE %', True),
        ('Avg MAE %', 'Avg MAE %', False),  # Lower is better (less adverse)
        ('Stopped Out', 'Stopped Out', False),  # Lower is better
        ('Stopped %', 'Stopped %', False),  # Lower is better
        ('Avg Win', 'Avg Win', True),
        ('Avg Loss', 'Avg Loss', False),  # Lower (less negative) is better
    ]
    
    for metric_name, key, higher_better in metrics:
        v2_val = v2_stats.get(key, 0)
        v7g_val = v7g_stats.get(key, 0)
        
        if isinstance(v2_val, float):
            v2_str = f"${v2_val:,.2f}" if 'P&L' in key or key in ['Avg Win', 'Avg Loss'] else f"{v2_val:.2f}"
            v7g_str = f"${v7g_val:,.2f}" if 'P&L' in key or key in ['Avg Win', 'Avg Loss'] else f"{v7g_val:.2f}"
        else:
            v2_str = str(v2_val)
            v7g_str = str(v7g_val)
        
        if higher_better:
            winner = "V2" if v2_val > v7g_val else ("V7G" if v7g_val > v2_val else "Tie")
        else:
            winner = "V2" if v2_val < v7g_val else ("V7G" if v7g_val < v2_val else "Tie")
        
        report.append(f"| **{metric_name}** | {v2_str} | {v7g_str} | **{winner}** |")
    
    report.append("")
    
    # =================
    # RISK PROFILING
    # =================
    report.append("## 🛡️ RISK PROFILING & EFFICIENCY")
    report.append("")
    report.append("| Metric | V2 | V7G | Winner |")
    report.append("|--------|-----|-----|--------|")
    
    risk_metrics = [
        ('Profit Factor', 'Profit Factor', True),
        ('Expectancy (EV)', 'EV', True),
        ('SQN', 'SQN', True),
        ('Max Drawdown', 'Max Drawdown', True), # Higher (closer to 0) is better
        ('Return / MaxDD', 'Return/DD', True),
    ]
    
    for metric_name, key, higher_better in risk_metrics:
        v2_val = v2_stats.get(key, 0)
        v7g_val = v7g_stats.get(key, 0)
        
        if key in ['EV', 'Max Drawdown']:
            v2_str = f"${v2_val:,.2f}"
            v7g_str = f"${v7g_val:,.2f}"
        else:
            v2_str = f"{v2_val:.2f}"
            v7g_str = f"{v7g_val:.2f}"
            
        if higher_better:
            winner = "V2" if v2_val > v7g_val else ("V7G" if v7g_val > v2_val else "Tie")
        else:
            winner = "V2" if v2_val < v7g_val else ("V7G" if v7g_val < v2_val else "Tie")
            
        report.append(f"| **{metric_name}** | {v2_str} | {v7g_str} | **{winner}** |")

    report.append("")
    report.append("---")
    report.append("")
    
    # =================
    # MFE/MAE ANALYSIS (Percentages)
    # =================
    report.append("## 📈 MFE/MAE ANALYSIS (Price Percentages - Time Agnostic)")
    report.append("")
    report.append("### Distribution Statistics")
    report.append("")
    report.append("| Metric | V2 | V7G |")
    report.append("|--------|-----|-----|")
    
    for strategy, df, name in [(v2, v2_data, 'V2'), (v7g, v7g_data, 'V7G')]:
        pass
    
    mfe_mae_metrics = [
        ('Avg MFE %', 'MFE %', 'mean'),
        ('Median MFE %', 'MFE %', 'median'),
        ('25th Pctl MFE %', 'MFE %', lambda x: x.quantile(0.25)),
        ('75th Pctl MFE %', 'MFE %', lambda x: x.quantile(0.75)),
        ('Max MFE %', 'MFE %', 'max'),
        ('Avg MAE %', 'MAE %', 'mean'),
        ('Median MAE %', 'MAE %', 'median'),
        ('25th Pctl MAE %', 'MAE %', lambda x: x.quantile(0.25)),
        ('75th Pctl MAE %', 'MAE %', lambda x: x.quantile(0.75)),
        ('Min MAE %', 'MAE %', 'min'),
    ]
    
    for label, col, agg in mfe_mae_metrics:
        if callable(agg):
            v2_val = agg(v2[col])
            v7g_val = agg(v7g[col])
        else:
            v2_val = getattr(v2[col], agg)()
            v7g_val = getattr(v7g[col], agg)()
        report.append(f"| {label} | {v2_val:.3f}% | {v7g_val:.3f}% |")
    
    report.append("")
    
    # MFE/MAE by Win/Loss
    report.append("### MFE/MAE by Outcome")
    report.append("")
    report.append("| Outcome | Strategy | Avg MFE % | Avg MAE % | Median MFE % | Median MAE % |")
    report.append("|---------|----------|-----------|-----------|--------------|--------------|")
    
    for df, name in [(v2, 'V2'), (v7g, 'V7G')]:
        wins = df[df['Is_Winner']]
        losses = df[~df['Is_Winner']]
        
        report.append(f"| Winners | {name} | {wins['MFE %'].mean():.3f}% | {wins['MAE %'].mean():.3f}% | {wins['MFE %'].median():.3f}% | {wins['MAE %'].median():.3f}% |")
        report.append(f"| Losers | {name} | {losses['MFE %'].mean():.3f}% | {losses['MAE %'].mean():.3f}% | {losses['MFE %'].median():.3f}% | {losses['MAE %'].median():.3f}% |")
    
    report.append("")
    report.append("---")
    report.append("")
    
    # =================
    # STOP-OUT ANALYSIS
    # =================
    report.append("## 🛑 STOP-OUT ANALYSIS")
    report.append("")
    
    report.append("### Overall Stop-Out Comparison")
    report.append("")
    report.append("| Metric | V2 | V7G |")
    report.append("|--------|-----|-----|")
    
    v2_stopped = v2[v2['Is_Stopped']]
    v7g_stopped = v7g[v7g['Is_Stopped']]
    
    report.append(f"| Total Stopped | {len(v2_stopped)} | {len(v7g_stopped)} |")
    report.append(f"| % of Trades Stopped | {len(v2_stopped)/len(v2)*100:.1f}% | {len(v7g_stopped)/len(v7g)*100:.1f}% |")
    report.append(f"| Avg Loss on Stop | ${v2_stopped['Net P&L USD'].mean():.2f} | ${v7g_stopped['Net P&L USD'].mean():.2f} |")
    report.append(f"| Total Stop Loss | ${v2_stopped['Net P&L USD'].sum():,.2f} | ${v7g_stopped['Net P&L USD'].sum():,.2f} |")
    
    report.append("")
    
    # Exit signal breakdown
    report.append("### Exit Signal Breakdown")
    report.append("")
    
    for df, name in [(v2, 'V2'), (v7g, 'V7G')]:
        report.append(f"#### {name} Exit Signals")
        report.append("")
        report.append("| Exit Signal | Count | Total P&L | Avg P&L | Avg MFE % | Avg MAE % |")
        report.append("|-------------|-------|-----------|---------|-----------|-----------|")
        
        for signal in df['Exit Signal'].unique():
            subset = df[df['Exit Signal'] == signal]
            report.append(f"| {signal} | {len(subset)} | ${subset['Net P&L USD'].sum():,.2f} | ${subset['Net P&L USD'].mean():.2f} | {subset['MFE %'].mean():.3f}% | {subset['MAE %'].mean():.3f}% |")
        
        report.append("")
    
    report.append("---")
    report.append("")
    
    # =================
    # ENTRY/EXIT COMPARISON
    # =================
    report.append("## 🔄 ENTRY/EXIT SIGNAL COMPARISON")
    report.append("")
    
    report.append("### Entry Signal Distribution")
    report.append("")
    
    for df, name in [(v2, 'V2'), (v7g, 'V7G')]:
        report.append(f"#### {name} Entry Signals")
        report.append("")
        report.append("| Entry Signal | Count | Win Rate | Total P&L | Avg P&L | Avg MFE % | Avg MAE % |")
        report.append("|--------------|-------|----------|-----------|---------|-----------|-----------|")
        
        for signal in df['Entry Signal'].unique():
            subset = df[df['Entry Signal'] == signal]
            wins = subset[subset['Is_Winner']]
            report.append(f"| {signal} | {len(subset)} | {len(wins)/len(subset)*100:.1f}% | ${subset['Net P&L USD'].sum():,.2f} | ${subset['Net P&L USD'].mean():.2f} | {subset['MFE %'].mean():.3f}% | {subset['MAE %'].mean():.3f}% |")
        
        report.append("")
    
    report.append("---")
    report.append("")
    
    # =================
    # HOURLY ANALYSIS
    # =================
    report.append("## ⏰ HOURLY ANALYSIS (ET)")
    report.append("")
    
    report.append("### Performance by Hour")
    report.append("")
    report.append("| Hour (ET) | V2 Trades | V2 Win% | V2 P&L | V7G Trades | V7G Win% | V7G P&L |")
    report.append("|-----------|-----------|---------|--------|------------|----------|---------|")
    
    for hour in sorted(set(v2['Hour'].unique()) | set(v7g['Hour'].unique())):
        v2_h = v2[v2['Hour'] == hour]
        v7g_h = v7g[v7g['Hour'] == hour]
        
        v2_trades = len(v2_h)
        v2_wr = v2_h['Is_Winner'].mean() * 100 if v2_trades > 0 else 0
        v2_pnl = v2_h['Net P&L USD'].sum()
        
        v7g_trades = len(v7g_h)
        v7g_wr = v7g_h['Is_Winner'].mean() * 100 if v7g_trades > 0 else 0
        v7g_pnl = v7g_h['Net P&L USD'].sum()
        
        report.append(f"| {hour:02d}:00 | {v2_trades} | {v2_wr:.1f}% | ${v2_pnl:,.0f} | {v7g_trades} | {v7g_wr:.1f}% | ${v7g_pnl:,.0f} |")
    
    report.append("")
    
    # =================
    # 15-MINUTE BUCKET ANALYSIS
    # =================
    report.append("### Performance by 15-Minute Buckets (After 9:30 ET)")
    report.append("")
    report.append("| Time Bucket | V2 Trades | V2 Win% | V2 Avg P&L | V7G Trades | V7G Win% | V7G Avg P&L |")
    report.append("|-------------|-----------|---------|------------|------------|----------|-------------|")
    
    # Focus on trading hours (9:30 to 16:00)
    for hour in range(9, 17):
        for minute in [0, 15, 30, 45]:
            if hour == 9 and minute < 30:
                continue
            
            bucket_label = f"{hour:02d}:{minute:02d}"
            
            v2_b = v2[(v2['Hour'] == hour) & (v2['15min_bucket'] == minute)]
            v7g_b = v7g[(v7g['Hour'] == hour) & (v7g['15min_bucket'] == minute)]
            
            if len(v2_b) == 0 and len(v7g_b) == 0:
                continue
            
            v2_trades = len(v2_b)
            v2_wr = v2_b['Is_Winner'].mean() * 100 if v2_trades > 0 else 0
            v2_avg = v2_b['Net P&L USD'].mean() if v2_trades > 0 else 0
            
            v7g_trades = len(v7g_b)
            v7g_wr = v7g_b['Is_Winner'].mean() * 100 if v7g_trades > 0 else 0
            v7g_avg = v7g_b['Net P&L USD'].mean() if v7g_trades > 0 else 0
            
            report.append(f"| {bucket_label} | {v2_trades} | {v2_wr:.1f}% | ${v2_avg:.2f} | {v7g_trades} | {v7g_wr:.1f}% | ${v7g_avg:.2f} |")
    
    report.append("")
    
    # =================
    # 5-MINUTE BUCKET ANALYSIS (First Hour Focus)
    # =================
    report.append("### 5-Minute Bucket Analysis (9:30-10:30 AM Focus)")
    report.append("")
    report.append("| Time | V2 Trades | V2 Win% | V2 P&L | V7G Trades | V7G Win% | V7G P&L |")
    report.append("|------|-----------|---------|--------|------------|----------|---------|")
    
    for hour in [9, 10]:
        start_min = 30 if hour == 9 else 0
        end_min = 60 if hour == 9 else 35
        
        for minute in range(start_min, end_min, 5):
            bucket_label = f"{hour:02d}:{minute:02d}"
            
            v2_b = v2[(v2['Hour'] == hour) & (v2['5min_bucket'] == minute)]
            v7g_b = v7g[(v7g['Hour'] == hour) & (v7g['5min_bucket'] == minute)]
            
            if len(v2_b) == 0 and len(v7g_b) == 0:
                continue
            
            v2_trades = len(v2_b)
            v2_wr = v2_b['Is_Winner'].mean() * 100 if v2_trades > 0 else 0
            v2_pnl = v2_b['Net P&L USD'].sum()
            
            v7g_trades = len(v7g_b)
            v7g_wr = v7g_b['Is_Winner'].mean() * 100 if v7g_trades > 0 else 0
            v7g_pnl = v7g_b['Net P&L USD'].sum()
            
            report.append(f"| {bucket_label} | {v2_trades} | {v2_wr:.1f}% | ${v2_pnl:,.0f} | {v7g_trades} | {v7g_wr:.1f}% | ${v7g_pnl:,.0f} |")
    
    report.append("")
    
    # =================
    # ENTRY TIME MODE/MEDIAN ANALYSIS
    # =================
    report.append("### Entry Time Analysis (Mode/Median)")
    report.append("")
    
    for df, name in [(v2, 'V2'), (v7g, 'V7G')]:
        wins = df[df['Is_Winner']]
        losses = df[~df['Is_Winner']]
        
        win_mode_hour = wins['Hour'].mode().iloc[0] if len(wins) > 0 else 'N/A'
        win_mode_min = wins['Minute'].mode().iloc[0] if len(wins) > 0 else 'N/A'
        loss_mode_hour = losses['Hour'].mode().iloc[0] if len(losses) > 0 else 'N/A'
        loss_mode_min = losses['Minute'].mode().iloc[0] if len(losses) > 0 else 'N/A'
        
        report.append(f"#### {name} Entry Time Patterns")
        report.append("")
        report.append(f"- **Winning trades mode time**: {win_mode_hour}:{str(win_mode_min).zfill(2) if isinstance(win_mode_min, int) else win_mode_min}")
        report.append(f"- **Losing trades mode time**: {loss_mode_hour}:{str(loss_mode_min).zfill(2) if isinstance(loss_mode_min, int) else loss_mode_min}")
        report.append(f"- **Most successful hour**: {wins.groupby('Hour')['Net P&L USD'].sum().idxmax()} (${wins.groupby('Hour')['Net P&L USD'].sum().max():,.0f})")
        report.append(f"- **Least successful hour**: {df.groupby('Hour')['Net P&L USD'].sum().idxmin()} (${df.groupby('Hour')['Net P&L USD'].sum().min():,.0f})")
        report.append("")
    
    report.append("---")
    report.append("")
    
    # =================
    # DAY OF WEEK ANALYSIS
    # =================
    report.append("## 📅 DAY OF WEEK ANALYSIS")
    report.append("")
    report.append("| Day | V2 Trades | V2 Win% | V2 P&L | V7G Trades | V7G Win% | V7G P&L |")
    report.append("|-----|-----------|---------|--------|------------|----------|---------|")
    
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    for day in day_order:
        v2_d = v2[v2['DayOfWeek'] == day]
        v7g_d = v7g[v7g['DayOfWeek'] == day]
        
        v2_trades = len(v2_d)
        v2_wr = v2_d['Is_Winner'].mean() * 100 if v2_trades > 0 else 0
        v2_pnl = v2_d['Net P&L USD'].sum()
        
        v7g_trades = len(v7g_d)
        v7g_wr = v7g_d['Is_Winner'].mean() * 100 if v7g_trades > 0 else 0
        v7g_pnl = v7g_d['Net P&L USD'].sum()
        
        report.append(f"| {day} | {v2_trades} | {v2_wr:.1f}% | ${v2_pnl:,.0f} | {v7g_trades} | {v7g_wr:.1f}% | ${v7g_pnl:,.0f} |")
    
    report.append("")
    report.append("---")
    report.append("")
    
    # =================
    # MONTH BY MONTH ANALYSIS
    # =================
    report.append("## 📆 MONTH BY MONTH ANALYSIS")
    report.append("")
    report.append("| Year-Month | V2 Trades | V2 Win% | V2 P&L | V7G Trades | V7G Win% | V7G P&L |")
    report.append("|------------|-----------|---------|--------|------------|----------|---------|")
    
    # Get all unique year-months
    v2['YearMonth'] = v2['Entry Time'].dt.to_period('M')
    v7g['YearMonth'] = v7g['Entry Time'].dt.to_period('M')
    
    all_months = sorted(set(v2['YearMonth'].unique()) | set(v7g['YearMonth'].unique()))
    
    for ym in all_months:
        v2_m = v2[v2['YearMonth'] == ym]
        v7g_m = v7g[v7g['YearMonth'] == ym]
        
        v2_trades = len(v2_m)
        v2_wr = v2_m['Is_Winner'].mean() * 100 if v2_trades > 0 else 0
        v2_pnl = v2_m['Net P&L USD'].sum()
        
        v7g_trades = len(v7g_m)
        v7g_wr = v7g_m['Is_Winner'].mean() * 100 if v7g_trades > 0 else 0
        v7g_pnl = v7g_m['Net P&L USD'].sum()
        
        report.append(f"| {ym} | {v2_trades} | {v2_wr:.1f}% | ${v2_pnl:,.0f} | {v7g_trades} | {v7g_wr:.1f}% | ${v7g_pnl:,.0f} |")
    
    report.append("")
    report.append("---")
    report.append("")
    
    # =================
    # YEAR BY YEAR ANALYSIS
    # =================
    report.append("## 📊 YEAR BY YEAR ANALYSIS")
    report.append("")
    report.append("| Year | V2 Trades | V2 Win% | V2 P&L | V2 Avg Trade | V7G Trades | V7G Win% | V7G P&L | V7G Avg Trade |")
    report.append("|------|-----------|---------|--------|--------------|------------|----------|---------|---------------|")
    
    all_years = sorted(set(v2['Year'].unique()) | set(v7g['Year'].unique()))
    
    for year in all_years:
        v2_y = v2[v2['Year'] == year]
        v7g_y = v7g[v7g['Year'] == year]
        
        v2_trades = len(v2_y)
        v2_wr = v2_y['Is_Winner'].mean() * 100 if v2_trades > 0 else 0
        v2_pnl = v2_y['Net P&L USD'].sum()
        v2_avg = v2_y['Net P&L USD'].mean() if v2_trades > 0 else 0
        
        v7g_trades = len(v7g_y)
        v7g_wr = v7g_y['Is_Winner'].mean() * 100 if v7g_trades > 0 else 0
        v7g_pnl = v7g_y['Net P&L USD'].sum()
        v7g_avg = v7g_y['Net P&L USD'].mean() if v7g_trades > 0 else 0
        
        report.append(f"| {year} | {v2_trades} | {v2_wr:.1f}% | ${v2_pnl:,.0f} | ${v2_avg:.2f} | {v7g_trades} | {v7g_wr:.1f}% | ${v7g_pnl:,.0f} | ${v7g_avg:.2f} |")
    
    report.append("")
    report.append("---")
    report.append("")
    
    # =================
    # MINUTE-BY-MINUTE OPTIMAL ENTRY ANALYSIS
    # =================
    report.append("## 🎯 OPTIMAL ENTRY TIME ANALYSIS")
    report.append("")
    report.append("### Best Entry Minutes (Ranked by Win Rate, min 10 trades)")
    report.append("")
    
    for df, name in [(v2, 'V2'), (v7g, 'V7G')]:
        report.append(f"#### {name} Top 10 Entry Minutes")
        report.append("")
        report.append("| Time (ET) | Trades | Win Rate | Avg P&L | Total P&L |")
        report.append("|-----------|--------|----------|---------|-----------|")
        
        # Group by Hour:Minute
        grouped = df.groupby('Hour_Minute').agg({
            'Net P&L USD': ['count', 'sum', 'mean'],
            'Is_Winner': 'mean'
        }).reset_index()
        grouped.columns = ['Time', 'Trades', 'Total P&L', 'Avg P&L', 'Win Rate']
        grouped = grouped[grouped['Trades'] >= 10]
        grouped = grouped.sort_values('Win Rate', ascending=False).head(10)
        
        for _, row in grouped.iterrows():
            report.append(f"| {row['Time']} | {int(row['Trades'])} | {row['Win Rate']*100:.1f}% | ${row['Avg P&L']:.2f} | ${row['Total P&L']:,.0f} |")
        
        report.append("")
    
    report.append("### Worst Entry Minutes (Ranked by Win Rate, min 10 trades)")
    report.append("")
    
    for df, name in [(v2, 'V2'), (v7g, 'V7G')]:
        report.append(f"#### {name} Bottom 10 Entry Minutes")
        report.append("")
        report.append("| Time (ET) | Trades | Win Rate | Avg P&L | Total P&L |")
        report.append("|-----------|--------|----------|---------|-----------|")
        
        grouped = df.groupby('Hour_Minute').agg({
            'Net P&L USD': ['count', 'sum', 'mean'],
            'Is_Winner': 'mean'
        }).reset_index()
        grouped.columns = ['Time', 'Trades', 'Total P&L', 'Avg P&L', 'Win Rate']
        grouped = grouped[grouped['Trades'] >= 10]
        grouped = grouped.sort_values('Win Rate', ascending=True).head(10)
        
        for _, row in grouped.iterrows():
            report.append(f"| {row['Time']} | {int(row['Trades'])} | {row['Win Rate']*100:.1f}% | ${row['Avg P&L']:.2f} | ${row['Total P&L']:,.0f} |")
        
        report.append("")
    
    report.append("---")
    report.append("")
    
    # =================
    # DISCREPANCY ANALYSIS
    # =================
    report.append("## 🔍 STRATEGY DISCREPANCY ANALYSIS")
    report.append("")
    
    # Entry type comparison
    v2_entry_types = set(v2['Entry Signal'].unique())
    v7g_entry_types = set(v7g['Entry Signal'].unique())
    
    report.append("### Entry Signal Differences")
    report.append("")
    report.append(f"- **V2 Entry Signals**: {', '.join(v2_entry_types)}")
    report.append(f"- **V7G Entry Signals**: {', '.join(v7g_entry_types)}")
    report.append(f"- **V7G-only signals**: {', '.join(v7g_entry_types - v2_entry_types) or 'None'}")
    report.append(f"- **V2-only signals**: {', '.join(v2_entry_types - v7g_entry_types) or 'None'}")
    report.append("")
    
    # Exit type comparison
    v2_exit_types = set(v2['Exit Signal'].unique())
    v7g_exit_types = set(v7g['Exit Signal'].unique())
    
    report.append("### Exit Signal Differences")
    report.append("")
    report.append(f"- **V2 Exit Signals**: {', '.join(str(x) for x in v2_exit_types)}")
    report.append(f"- **V7G Exit Signals**: {', '.join(str(x) for x in v7g_exit_types)}")
    report.append(f"- **V7G-only exits**: {', '.join(str(x) for x in (v7g_exit_types - v2_exit_types)) or 'None'}")
    report.append(f"- **V2-only exits**: {', '.join(str(x) for x in (v2_exit_types - v7g_exit_types)) or 'None'}")
    report.append("")
    
    # Trade count by date comparison
    v2_dates = v2.groupby('Date').size()
    v7g_dates = v7g.groupby('Date').size()
    
    report.append("### Daily Trade Count Comparison")
    report.append("")
    report.append(f"- **V2 avg trades/day**: {v2_dates.mean():.1f}")
    report.append(f"- **V7G avg trades/day**: {v7g_dates.mean():.1f}")
    report.append(f"- **V2 max trades/day**: {v2_dates.max()}")
    report.append(f"- **V7G max trades/day**: {v7g_dates.max()}")
    report.append("")
    
    report.append("---")
    report.append("")
    
    # =================
    # LOSS ANALYSIS
    # =================
    report.append("## 💔 LOSING TRADE ANALYSIS")
    report.append("")
    
    for df, name in [(v2, 'V2'), (v7g, 'V7G')]:
        losses = df[~df['Is_Winner']]
        
        report.append(f"### {name} Losing Trade Breakdown")
        report.append("")
        report.append(f"- **Total losing trades**: {len(losses)}")
        report.append(f"- **Total loss**: ${losses['Net P&L USD'].sum():,.2f}")
        report.append(f"- **Avg loss**: ${losses['Net P&L USD'].mean():.2f}")
        report.append(f"- **Median loss**: ${losses['Net P&L USD'].median():.2f}")
        report.append(f"- **Worst loss**: ${losses['Net P&L USD'].min():.2f}")
        report.append("")
        
        # Losing trades by exit type
        report.append(f"#### {name} Losses by Exit Signal")
        report.append("")
        report.append("| Exit Signal | Count | Total Loss | Avg Loss |")
        report.append("|-------------|-------|------------|----------|")
        
        for signal in losses['Exit Signal'].unique():
            subset = losses[losses['Exit Signal'] == signal]
            report.append(f"| {signal} | {len(subset)} | ${subset['Net P&L USD'].sum():,.2f} | ${subset['Net P&L USD'].mean():.2f} |")
        
        report.append("")
        
        # Losing trades by hour
        report.append(f"#### {name} Losses by Hour")
        report.append("")
        report.append("| Hour | Count | Total Loss | Avg Loss |")
        report.append("|------|-------|------------|----------|")
        
        for hour in sorted(losses['Hour'].unique()):
            subset = losses[losses['Hour'] == hour]
            report.append(f"| {hour:02d}:00 | {len(subset)} | ${subset['Net P&L USD'].sum():,.2f} | ${subset['Net P&L USD'].mean():.2f} |")
        
        report.append("")
    
    report.append("---")
    report.append("")
    
    # =================
    # KEY INSIGHTS
    # =================
    report.append("## 💡 KEY INSIGHTS & RECOMMENDATIONS")
    report.append("")
    
    # Calculate some key insights
    v2_best_hour = v2.groupby('Hour')['Net P&L USD'].sum().idxmax()
    v7g_best_hour = v7g.groupby('Hour')['Net P&L USD'].sum().idxmax()
    
    v2_best_day = v2.groupby('DayOfWeek')['Net P&L USD'].sum().idxmax()
    v7g_best_day = v7g.groupby('DayOfWeek')['Net P&L USD'].sum().idxmax()
    
    report.append("### Timing Insights")
    report.append("")
    report.append(f"- **V2 best hour**: {v2_best_hour}:00 ET (${v2.groupby('Hour')['Net P&L USD'].sum().max():,.0f})")
    report.append(f"- **V7G best hour**: {v7g_best_hour}:00 ET (${v7g.groupby('Hour')['Net P&L USD'].sum().max():,.0f})")
    report.append(f"- **V2 best day**: {v2_best_day} (${v2.groupby('DayOfWeek')['Net P&L USD'].sum().max():,.0f})")
    report.append(f"- **V7G best day**: {v7g_best_day} (${v7g.groupby('DayOfWeek')['Net P&L USD'].sum().max():,.0f})")
    report.append("")
    
    report.append("### Risk/Reward Insights")
    report.append("")
    report.append(f"- **V2 MFE/MAE ratio**: {abs(v2['MFE %'].mean() / v2['MAE %'].mean()):.2f}")
    report.append(f"- **V7G MFE/MAE ratio**: {abs(v7g['MFE %'].mean() / v7g['MAE %'].mean()):.2f}")
    report.append("")
    
    # Save report
    return '\n'.join(report)

# Main execution
if __name__ == '__main__':
    print("Loading V2 data...")
    v2_data = load_strategy_data(V2_FILE, 'V2')
    print(f"  Loaded {len(v2_data['merged'])} V2 trades")
    
    print("Loading V7G data...")
    v7g_data = load_strategy_data(V7G_FILE, 'V7G')
    print(f"  Loaded {len(v7g_data['merged'])} V7G trades")
    
    print("Generating comprehensive report...")
    report = generate_report(v2_data, v7g_data)
    
    output_file = 'V2_vs_V7G_Comprehensive_Analysis.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ Report saved to: {output_file}")
    print("\n" + "="*60)
    print(report[:3000] + "\n...[truncated]...")
