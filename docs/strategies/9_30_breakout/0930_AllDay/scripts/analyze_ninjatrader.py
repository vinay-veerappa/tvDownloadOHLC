"""
NinjaTrader Strategy Analyzer CSV Analysis Script
==================================================
Purpose: Load NinjaTrader Strategy Analyzer CSV exports and generate
         comprehensive analysis report matching TradingView format.

Usage: python analyze_ninjatrader.py [trades_csv] [settings_csv] [summary_csv]
       If no args provided, will auto-detect files matching "NinjaTrader*" pattern.

Note: All times are converted to EST for consistency with TradingView reports.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import glob
import sys
import pytz

warnings.filterwarnings('ignore')

# --- TIMEZONE CONFIGURATION ---
# NinjaTrader exports in local time (Pacific for this user)
# We convert all times to EST for consistency
LOCAL_TZ = pytz.timezone('US/Pacific')  # Chart timezone
EST_TZ = pytz.timezone('US/Eastern')    # Report timezone

# For NinjaTrader, always use local implementations to ensure correct config keys
# The shared module has TradingView-specific configuration that doesn't match NT
IMPORTED_SHARED = False


# --- MARKET CONTEXT KNOWLEDGE BASE ---
MACRO_CONTEXT = {
    (2020, 1): "COVID Crash", (2020, 2): "Fed Stimulus Injection",
    (2021, 1): "Meme Stock Mania", (2021, 4): "Peak Liquidity",
    (2022, 1): "Rate Hike Begins", (2022, 2): "Inflation Panic",
    (2023, 1): "AI Rally Start", (2023, 3): "Higher for Longer",
    (2024, 4): "Election Rally", 
    (2025, 1): "Soft Landing Confirmed",
}


def load_ninjatrader_settings(filepath):
    """Load NinjaTrader settings CSV into properties dict."""
    props = {}
    try:
        # Read CSV with proper handling
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            # Split by comma, handling potential trailing comma
            parts = line.strip().rstrip(',').split(',')
            if len(parts) >= 2:
                key = parts[0].strip()
                val = parts[1].strip()
                if key and val:
                    props[key] = val
        
        print(f"  Loaded {len(props)} settings parameters")
    except Exception as e:
        print(f"Warning: Could not load settings: {e}")
    return props


def convert_to_est(dt_series, source_tz=LOCAL_TZ):
    """Convert datetime series from source timezone to EST."""
    # Localize to source timezone, then convert to EST
    localized = dt_series.dt.tz_localize(source_tz, ambiguous='NaT', nonexistent='NaT')
    est_times = localized.dt.tz_convert(EST_TZ)
    # Remove timezone info for cleaner display
    return est_times.dt.tz_localize(None)


def load_ninjatrader_trades(filepath, name="NinjaTrader"):
    """
    Load NinjaTrader trades CSV and convert to common format used by report generator.
    All times are converted to EST.
    """
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None
    
    # Rename columns to match TradingView format
    rename_map = {
        'Trade number': 'Trade #',
        'Entry time': 'Entry Time',
        'Exit time': 'Exit Time',
        'Entry price': 'Entry Price',
        'Exit price': 'Exit Price',
        'Entry name': 'Entry Signal',
        'Exit name': 'Exit Signal',
        'Profit': 'Net P&L USD',
        'Market pos.': 'Type',
        'MAE': 'MAE USD',
        'MFE': 'MFE USD',
    }
    
    df.rename(columns=rename_map, inplace=True)
    
    # Parse currency columns
    def parse_currency(val):
        if pd.isna(val):
            return 0.0
        s = str(val).replace('$', '').replace(',', '').strip()
        if s.startswith('(') and s.endswith(')'):
            s = '-' + s[1:-1]
        try:
            return float(s)
        except:
            return 0.0
    
    for col in ['Net P&L USD', 'MAE USD', 'MFE USD', 'ETD', 'Cum. net profit']:
        if col in df.columns:
            df[col] = df[col].apply(parse_currency)
    
    # Parse datetime and convert to EST
    df['Entry Time'] = pd.to_datetime(df['Entry Time'])
    df['Exit Time'] = pd.to_datetime(df['Exit Time'])
    
    # Convert to EST
    print("  Converting times to EST...")
    df['Entry Time'] = convert_to_est(df['Entry Time'])
    df['Exit Time'] = convert_to_est(df['Exit Time'])
    
    # Add time columns (now in EST)
    df['Hour'] = df['Entry Time'].dt.hour
    df['Minute'] = df['Entry Time'].dt.minute
    df['Month'] = df['Entry Time'].dt.month
    df['Quarter'] = df['Entry Time'].dt.quarter
    df['Year'] = df['Entry Time'].dt.year
    df['Date'] = df['Entry Time'].dt.date
    df['DayOfWeek'] = df['Entry Time'].dt.day_name()
    df['TimeSlot'] = df['Entry Time'].dt.strftime('%H:%M')
    
    # Granular buckets
    df['15min_bucket'] = (df['Minute'] // 15) * 15
    df['5min_bucket'] = (df['Minute'] // 5) * 5
    df['Q_Hour'] = pd.cut(df['Minute'], bins=[-1, 14, 29, 44, 59], labels=['Q1', 'Q2', 'Q3', 'Q4'])
    
    # Helper flags
    df['Is_Winner'] = df['Net P&L USD'] > 0
    
    # Strategy name
    df['Strategy'] = name
    
    return df


def load_ninjatrader_data(trades_path, settings_path=None, name="NinjaTrader"):
    """Load NinjaTrader exports and return in common format."""
    df = load_ninjatrader_trades(trades_path, name)
    if df is None:
        return None
    
    props = {}
    if settings_path and os.path.exists(settings_path):
        props = load_ninjatrader_settings(settings_path)
    
    return {
        'name': name,
        'merged': df,
        'props': props,
        'ticker': df['Instrument'].iloc[0] if 'Instrument' in df.columns else 'UNKNOWN'
    }

# ============================================================================
# NINJATRADER-SPECIFIC REPORT GENERATION
# These functions are always used for NinjaTrader reports (not imported from shared)
# ============================================================================

if not IMPORTED_SHARED:
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
        df = df.copy()
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

        return {
            'Trades': trades, 'Win Rate %': win_rate * 100, 'Total P&L': total_pnl, 'Profit Factor': pf,
            'Max Trailing DD': max_dd, 'Max Daily Loss': max_daily_loss, 'SQN': sqn, 'Combined Edge': combined_edge_raw,
            'Grade': grade, 'Risk ($)': risk_r, 'Max Loss Streak': max_losing_streak, 'Avg Win': avg_win,
            'Avg Loss': -risk_r, 'DRR': drr, 'MC Median DD': mc_results['mc_median_dd'], 'MC 95% DD': mc_results['mc_95_dd'],
            'MC Prob >2k': mc_results['mc_prob_2k']
        }

    def get_recommendations(stats):
        recs = []
        if stats.get('Profit Factor', 0) < 1.4: recs.append("🟠 **Fix PF**: Tighten stops.")
        if stats.get('MC Prob >2k', 0) > 1.0: recs.append("🔴 **High Risk**: >1% chance of $2k DD.")
        if stats.get('DRR', 0) > 10: recs.append("🔴 **Deep Drawdown**: Volatile.")
        if not recs: recs.append("🟢 **System Healthy**")
        return recs

    def generate_entry_timing_analysis(df, name):
        lines = []
        lines.append(f"#### {name} Precision Matrices (EST)")
        
        lines.append("**Day of Week x Hour Performance ($)**")
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        df = df.copy()
        df['DayOfWeek'] = pd.Categorical(df['DayOfWeek'], categories=day_order, ordered=True)
        
        dh_pivot = df.pivot_table(index='DayOfWeek', columns='Hour', values='Net P&L USD', aggfunc='sum').fillna(0)
        
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
        ts_stats = df.groupby('TimeSlot').agg({
            'Net P&L USD': 'sum', 
            'Trade #': 'count', 
            'Is_Winner': 'mean'
        }).reset_index()
        
        ts_stats = ts_stats[ts_stats['Trade #'] >= 5]
        
        best = ts_stats.sort_values('Net P&L USD', ascending=False).head(5)
        worst = ts_stats.sort_values('Net P&L USD', ascending=True).head(5)
        
        lines.append(f"#### {name} - Golden Minutes EST")
        lines.append("| Time (EST) | P&L | Win% | Trades |")
        lines.append("|---|---|---|---|")
        for _, r in best.iterrows():
            lines.append(f"| **{r['TimeSlot']}** | ${r['Net P&L USD']:,.0f} | {r['Is_Winner']*100:.1f}% | {int(r['Trade #'])} |")
            
        lines.append(f"#### {name} - Toxic Minutes EST")
        lines.append("| Time (EST) | P&L | Win% | Trades |")
        lines.append("|---|---|---|---|")
        for _, r in worst.iterrows():
            lines.append(f"| **{r['TimeSlot']}** | ${r['Net P&L USD']:,.0f} | {r['Is_Winner']*100:.1f}% | {int(r['Trade #'])} |")
        lines.append("")
        return lines

    def generate_report(datasets):
        report = []
        report.append("# NinjaTrader Strategy Grade & Comprehensive Metrics")
        report.append(f"## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("**Note**: All times are in EST for consistency with TradingView reports.")
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
        
        # 2. CONFIGURATION VERIFICATION - Use actual NinjaTrader setting keys
        report.append("## ⚙️ CONFIGURATION VERIFICATION (NinjaTrader)")
        keys_to_check = [
            "Use Immediate Entry", "Min Displacement %",
            "Require Fresh Breakout", "Max Attempts Per Day",
            "Use Single TP", "TP1 %", "TP2 %",
            "Use Trailing Stop", "Use Adaptive Trail", "Move to Breakeven After TP1",
            "Use Fixed SL", "Fixed SL %", "Risk per Trade %", 
            "Min Contracts", "Max Contracts",
            "Use MAE Filter", "MAE Threshold %",
            "Max Range %", "Min Range %",
        ]
        
        report.append("| Parameter | " + " | ".join([d['name'] for d in datasets]) + " |")
        report.append("|" + "|".join(["---"] * (len(datasets)+1)) + "|")
        
        for key in keys_to_check:
            row = [f"**{key}**"]
            for d in datasets:
                val = d['props'].get(key, "-")
                row.append(str(val))
            report.append("| " + " | ".join(row) + " |")

        report.append("")
        report.append("---")
        
        # 3. HYPER-PRECISION MATRIX
        report.append("## ⏰ HYPER-PRECISION TIME ANALYSIS (EST)")
        
        for d in datasets:
            report.extend(generate_entry_timing_analysis(d['merged'], d['name']))
            
        report.append("### ⚡ PRECISE ENTRY OPTIMIZATION")
        for d in datasets:
            report.extend(generate_golden_minutes(d['merged'], d['name']))
            
        # 4. 5-Min Distribution
        for d in datasets:
            report.append(f"#### {d['name']} 5-Minute Distribution Matrices (EST)")
            df = d['merged'].copy()
            df['Bucket5'] = (df['Minute'] // 5) * 5
            
            pnl = df.pivot_table(index='Hour', columns='Bucket5', values='Net P&L USD', aggfunc='sum').fillna(0)
            def wl_fmt(s): return f"{int(s.sum())}/{int(s.count()-s.sum())}"
            wl = df.pivot_table(index='Hour', columns='Bucket5', values='Is_Winner', aggfunc=wl_fmt).fillna("-")
            
            def render(pivot, title, fmt):
                ls = []
                ls.append(f"**{title}**")
                for c in range(0, 60, 5): 
                    if c not in pivot.columns: pivot[c] = 0
                cols = sorted(list(pivot.columns))
                ls.append(f"| Hour (EST) | {' | '.join([f':{c:02d}' for c in cols])} |")
                ls.append("|---" + "|---" * len(cols) + "|")
                for h, r in pivot.iterrows():
                    vals = [fmt(r[c]) for c in cols]
                    ls.append(f"| **{h}:00** | {' | '.join(vals)} |")
                ls.append("")
                return ls
                
            report.extend(render(pnl, "5-Minute P&L ($)", lambda v: f"${v/1000:.1f}k" if abs(v)>999 else f"${v:.0f}"))
            report.extend(render(wl, "5-Minute W/L Count", lambda v: str(v)))

        return '\n'.join(report)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def find_ninjatrader_files(directory="."):
    """Auto-detect NinjaTrader export files in directory."""
    files = {
        'trades': None,
        'settings': None,
        'summary': None
    }
    
    pattern = os.path.join(directory, "NinjaTrader*")
    matches = glob.glob(pattern)
    
    for f in matches:
        lower = f.lower()
        if '_trades' in lower or 'trades' in lower:
            files['trades'] = f
        elif '_settings' in lower or 'settings' in lower:
            files['settings'] = f
        elif '_summary' in lower or 'summary' in lower:
            files['summary'] = f
    
    return files


if __name__ == '__main__':
    print("=== NinjaTrader Strategy Analyzer ===")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("All times will be converted to EST.\n")
    
    # Determine input files
    if len(sys.argv) >= 2:
        trades_path = sys.argv[1]
        settings_path = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        print("Auto-detecting NinjaTrader files...")
        files = find_ninjatrader_files(".")
        
        if not files['trades']:
            files = find_ninjatrader_files("ninjascript")
        
        if not files['trades']:
            print("ERROR: No NinjaTrader trades CSV found!")
            print("Usage: python analyze_ninjatrader.py trades.csv [settings.csv]")
            sys.exit(1)
        
        trades_path = files['trades']
        settings_path = files['settings']
        
        print(f"  Trades: {trades_path}")
        print(f"  Settings: {settings_path}")
    
    # Load data
    print(f"\nLoading trades from: {trades_path}")
    name = os.path.basename(trades_path).split('_')[0] + "_NT"
    
    data = load_ninjatrader_data(trades_path, settings_path, name)
    
    if data is None:
        print("ERROR: Failed to load data!")
        sys.exit(1)
    
    print(f"  Loaded {len(data['merged'])} trades")
    print(f"  Ticker: {data['ticker']}")
    print(f"  Date Range: {data['merged']['Entry Time'].min()} to {data['merged']['Entry Time'].max()}")
    print(f"  Settings loaded: {len(data['props'])} parameters")
    
    # Generate report
    print("\nGenerating comprehensive report...")
    datasets = [data]
    
    report_content = generate_report(datasets)
    
    # Add header with ticker info
    header = f"""# {data['ticker']} NinjaTrader Strategy Analysis
**Source**: NinjaTrader Strategy Analyzer Export
**Strategy**: {data['props'].get('Label', 'ORBv5Strategy')}
**Period**: {data['merged']['Entry Time'].min().strftime('%Y-%m-%d')} to {data['merged']['Entry Time'].max().strftime('%Y-%m-%d')}
**Total Trades**: {len(data['merged'])}
**Timezone**: All times are in EST

---

"""
    
    report_content = header + report_content
    
    # Save report
    output_file = f"NinjaTrader_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"\n✅ Report saved to: {output_file}")
    
    # Print summary stats
    stats = calc_stats_extended(data['merged'])
    print("\n=== QUICK SUMMARY ===")
    print(f"  Trades: {stats['Trades']}")
    print(f"  Win Rate: {stats['Win Rate %']:.1f}%")
    print(f"  Total P&L: ${stats['Total P&L']:,.2f}")
    print(f"  Profit Factor: {stats['Profit Factor']:.2f}")
    print(f"  Max DD: ${stats['Max Trailing DD']:,.0f}")
    print(f"  Grade: {stats['Grade']}")
    print()
