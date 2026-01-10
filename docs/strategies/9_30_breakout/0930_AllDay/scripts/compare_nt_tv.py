"""
NT vs TV Trade Comparison Script
Analyzes differences between NinjaTrader and TradingView trade execution
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

# Timezone conversion
LOCAL_TZ = pytz.timezone('US/Pacific')
EST_TZ = pytz.timezone('US/Eastern')

def convert_to_est(dt_series, source_tz=LOCAL_TZ):
    """Convert datetime series from source timezone to EST."""
    try:
        localized = dt_series.dt.tz_localize(source_tz, ambiguous='NaT', nonexistent='NaT')
        est_times = localized.dt.tz_convert(EST_TZ)
        return est_times.dt.tz_localize(None)
    except:
        return dt_series  # Already converted or error


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


def load_nt_trades(filepath):
    """Load NinjaTrader trades CSV."""
    df = pd.read_csv(filepath)
    
    # Rename columns
    df.rename(columns={
        'Trade number': 'Trade #',
        'Entry time': 'Entry Time',
        'Exit time': 'Exit Time',
        'Entry price': 'Entry Price',
        'Exit price': 'Exit Price',
        'Profit': 'Net P&L',
        'Market pos.': 'Direction',
        'Exit name': 'Exit Signal',
        'Commission': 'Commission',
    }, inplace=True)
    
    # Parse columns
    df['Entry Time'] = pd.to_datetime(df['Entry Time'])
    df['Exit Time'] = pd.to_datetime(df['Exit Time'])
    df['Entry Time'] = convert_to_est(df['Entry Time'])
    df['Exit Time'] = convert_to_est(df['Exit Time'])
    df['Net P&L'] = df['Net P&L'].apply(parse_currency)
    
    if 'Commission' in df.columns:
        df['Commission'] = df['Commission'].apply(parse_currency)
    else:
        df['Commission'] = 0.0
    
    # Add date
    df['Date'] = df['Entry Time'].dt.date
    df['Source'] = 'NinjaTrader'
    
    return df


def load_tv_trades(filepath):
    """Load TradingView trades Excel."""
    xl = pd.ExcelFile(filepath)
    sheet = next((s for s in xl.sheet_names if s.lower() == "list of trades"), "List of trades")
    trade_list = pd.read_excel(xl, sheet_name=sheet)
    
    # Separate entries and exits
    entries = trade_list[trade_list['Type'].str.contains('Entry', case=False, na=False)].copy()
    exits = trade_list[trade_list['Type'].str.contains('Exit', case=False, na=False)].copy()
    
    entries = entries[['Trade #', 'Date and time', 'Type', 'Price USD']].copy()
    entries.columns = ['Trade #', 'Entry Time', 'Entry Type', 'Entry Price']
    
    exit_cols = ['Trade #', 'Date and time', 'Type', 'Signal', 'Price USD', 'Net P&L USD']
    exit_cols = [c for c in exit_cols if c in exits.columns]
    exits = exits[exit_cols].copy()
    exits.rename(columns={'Date and time': 'Exit Time', 'Price USD': 'Exit Price', 
                          'Net P&L USD': 'Net P&L', 'Signal': 'Exit Signal'}, inplace=True)
    
    merged = pd.merge(exits, entries, on='Trade #', how='left')
    merged['Entry Time'] = pd.to_datetime(merged['Entry Time'])
    merged['Exit Time'] = pd.to_datetime(merged['Exit Time'])
    merged['Direction'] = merged['Entry Type'].apply(lambda x: 'Long' if 'long' in str(x).lower() else 'Short')
    merged['Date'] = merged['Entry Time'].dt.date
    merged['Source'] = 'TradingView'
    
    return merged



def compare_trades(nt_df, tv_df, start_date, end_date):
    """Compare trades between NT and TV for a date range."""
    
    # Filter by date
    nt = nt_df[(nt_df['Date'] >= start_date) & (nt_df['Date'] <= end_date)].copy()
    tv = tv_df[(tv_df['Date'] >= start_date) & (tv_df['Date'] <= end_date)].copy()
    
    report = []
    report.append(f"# NT vs TV Deep P&L Analysis")
    report.append(f"**Period**: {start_date} to {end_date}")
    
    # Global Stats
    nt_pnl = nt['Net P&L'].sum()
    tv_pnl = tv['Net P&L'].sum()
    nt_comm = nt['Commission'].sum() if 'Commission' in nt.columns else 0
    
    report.append(f"## Global Financials")
    report.append(f"| Metric | NinjaTrader | TradingView | Diff |")
    report.append(f"|---|---|---|---|")
    report.append(f"| **Total Net P&L** | **${nt_pnl:,.2f}** | **${tv_pnl:,.2f}** | **${nt_pnl - tv_pnl:,.2f}** |")
    report.append(f"| **Avg Trade P&L** | ${nt['Net P&L'].mean():.2f} | ${tv['Net P&L'].mean():.2f} | ${(nt['Net P&L'].mean() - tv['Net P&L'].mean()):.2f} |")
    report.append(f"| **Total Trades** | {len(nt)} | {len(tv)} | {len(nt) - len(tv)} |")
    report.append(f"| **Commission Paid** | ${nt_comm:,.2f} | (Not in Export) | - |")
    report.append("")

    # Matched Trade Analysis
    report.append("## Matched Trade Analysis")
    report.append("Matching trades by Date and approx Time (within 5 mins)...")
    
    matches = []
    unmatched_nt = []
    
    tv_indices_matched = set()
    
    for i, nt_row in nt.iterrows():
        # Find matching TV trade
        best_match = None
        min_time_diff = float('inf')
        
        # Look for TV trades on same day
        tv_candidates = tv[tv['Date'] == nt_row['Date']]
        
        for j, tv_row in tv_candidates.iterrows():
            if j in tv_indices_matched: continue
            
            # Check time diff (NT usually 1 min later)
            time_diff = abs((nt_row['Entry Time'] - tv_row['Entry Time']).total_seconds()) / 60
            
            if time_diff < 5: # Within 5 mins
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    best_match = (j, tv_row)
        
        if best_match:
            idx, tv_row = best_match
            tv_indices_matched.add(idx)
            
            # Analyze P&L diff
            pnl_diff = nt_row['Net P&L'] - tv_row['Net P&L']
            
            matches.append({
                'Date': nt_row['Date'],
                'Time': nt_row['Entry Time'].strftime('%H:%M'),
                'NT_PnL': nt_row['Net P&L'],
                'TV_PnL': tv_row['Net P&L'],
                'Diff': pnl_diff,
                'NT_Dir': nt_row['Direction'],
                'TV_Dir': tv_row['Direction'],
                'NT_Exit': nt_row['Exit Signal'],
                'TV_Exit': tv_row.get('Exit Signal', 'N/A')
            })
        else:
            unmatched_nt.append(nt_row)
            
    # Report on P&L Divergence
    matches_df = pd.DataFrame(matches)
    if not matches_df.empty:
        # Sort by biggest absolute difference
        matches_df['AbsDiff'] = matches_df['Diff'].abs()
        divergence = matches_df[matches_df['AbsDiff'] > 20].sort_values('AbsDiff', ascending=False)
        
        report.append(f"### Significant P&L Divergences (>{'$20'})")
        report.append(f"Found {len(divergence)} trades with significant P&L difference.")
        report.append("")
        report.append("| Date | Time | Dir | NT P&L | TV P&L | Diff | NT Exit | TV Exit |")
        report.append("|---|---|---|---|---|---|---|---|")
        
        for _, row in divergence.iterrows():
            diff_str = f"**${row['Diff']:.2f}**"
            report.append(f"| {row['Date']} | {row['Time']} | {row['NT_Dir']} | ${row['NT_PnL']:.2f} | ${row['TV_PnL']:.2f} | {diff_str} | {row['NT_Exit']} | {row['TV_Exit']} |")
    else:
        report.append("No matches found to analyze.")

    report.append("")
    report.append("## Hypotheses Checklist")
    report.append("1. **Commission**: Is NT P&L net of commissions? (Check 'Global Financials' table)")
    report.append("2. **Contract Value**: Are huge differences multiples of 2? (MNQ is $2/pt)")
    report.append("3. **Outcome Flip**: Did one hit TP and the other MAE/SL?")
    
    return '\n'.join(report)


if __name__ == '__main__':
    # File paths
    nt_file = r"..\ninjascript\NinjaTrader Grid 2026-01-10 02-38 PM.csv"
    tv_file = r"..\ninjascript\ORBv5_CME_MINI_MNQ1!_2026-01-10_4e918.xlsx"
    
    print("Loading NinjaTrader trades...")
    nt_df = load_nt_trades(nt_file)
    print(f"  Loaded {len(nt_df)} NT trades")
    
    print("Loading TradingView trades...")
    tv_df = load_tv_trades(tv_file)
    print(f"  Loaded {len(tv_df)} TV trades")
    
    # Compare larger overlapping range to get good sample size
    from datetime import date
    start = date(2023, 1, 12)
    end = date(2023, 12, 31)  # Full year 2023
    
    print(f"\nComparing period: {start} to {end}")
    
    report = compare_trades(nt_df, tv_df, start, end)
    
    # Save report
    output_file = "NT_vs_TV_PnL_DeepDive.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ Report saved to: {output_file}")
    print("\n" + "="*50)
    print(report[:2000])  # Preview
