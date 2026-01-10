"""
OR Size Impact Analyzer
=======================
Comparing multiple strategy runs to determine the "Cost vs Benefit" of the Min OR Filter.

Logic:
1. Load all Excel files found in the directory matching the pattern.
2. Sort them by "Number of Trades" (Most Trades = Base Case / Loosest Filter).
3. Compare the "Filtered" datasets against the "Base" dataset.
4. Answer: "What did we lose by filtering?" (Profitable trades missed) vs "What did we save?" (Losses avoided).
"""

import pandas as pd
import glob
import os

# Path to look for files
DIR = r'docs\strategies\9_30_breakout\0930_AllDay'
PATTERN = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_*.xlsx'

def load_and_process(filepath):
    try:
        xl = pd.ExcelFile(filepath)
        sheet = next((s for s in xl.sheet_names if s.lower() == "list of trades"), "List of trades")
        df = pd.read_excel(xl, sheet_name=sheet)
        
        # Merge columns similar to previous scripts
        entries = df[df['Type'].str.contains('Entry', case=False, na=False)][['Trade #', 'Date and time', 'Signal', 'Price USD']].copy()
        entries.columns = ['Trade #', 'Entry Time', 'Entry Signal', 'Entry Price']
        
        exits = df[df['Type'].str.contains('Exit', case=False, na=False)].copy()
        merged = pd.merge(exits, entries, on='Trade #', how='inner')
        
        # Key Stats
        total_pnl = merged['Net P&L USD'].sum()
        count = len(merged)
        avg_pnl = total_pnl / count if count > 0 else 0
        
        return {
            'file': os.path.basename(filepath),
            'df': merged,
            'count': count,
            'pnl': total_pnl,
            'avg_pnl': avg_pnl
        }
    except Exception as e:
        print(f"Skipping {filepath}: {e}")
        return None

def analyze_impact():
    # 1. Find Files
    files = glob.glob(os.path.join(DIR, PATTERN))
    # Exclude the original huge files from earlier in session if they exist (based on size maybe? or just process all)
    # The user generated new ones. Let's look at the 3 specific ones found in ls: 14657, d3126, d9c4a.
    # Those had sizes ~700KB - 1MB. The older ones were 2.2MB.
    # Let's filter by size < 1.5MB to target the "1 contract" runs.
    
    targets = []
    for f in files:
        if os.path.getsize(f) < 1500000: # Filter for the new smaller files (1 contract)
            targets.append(f)
            
    if not targets:
        print("No suitable new files found (checked < 1.5MB).")
        return

    print(f"Found {len(targets)} datasets to compare.")
    
    # 2. Load
    datasets = []
    for f in targets:
        res = load_and_process(f)
        if res: datasets.append(res)
        
    # Sort by Trade Count DESC (Base case first)
    datasets.sort(key=lambda x: x['count'], reverse=True)
    
    base = datasets[0]
    print(f"\nBASE CASE (Loosest Filter): {base['file']}")
    print(f"Trades: {base['count']}, P&L: ${base['pnl']:,.2f}")
    
    report = []
    report.append("# OR Size Impact Analysis")
    report.append(f"**Base Case**: `{base['file']}` ({base['count']} trades, ${base['pnl']:,.2f})")
    report.append("")
    
    # 3. Compare Rest to Base
    for ds in datasets[1:]:
        name = ds['file']
        count = ds['count']
        pnl = ds['pnl']
        
        print(f"\nCOMPARING: {name} ({count} trades)")
        
        # Identify Missing Trades (The Delta)
        # Using Trade # might be risky if they generate differently? 
        # Usually Trade # resets. Better to join on 'Entry Time'.
        
        base_df = base['df'].copy()
        curr_df = ds['df'].copy()
        
        # Create unique key
        base_df['key'] = base_df['Entry Time'].astype(str)
        curr_df['key'] = curr_df['Entry Time'].astype(str)
        
        # Filtered Out = In Base but NOT in Curr
        filtered_out = base_df[~base_df['key'].isin(curr_df['key'])]
        
        missed_wins = filtered_out[filtered_out['Net P&L USD'] > 0]
        avoided_losses = filtered_out[filtered_out['Net P&L USD'] < 0]
        
        missed_pnl = missed_wins['Net P&L USD'].sum()
        avoided_loss_val = abs(avoided_losses['Net P&L USD'].sum())
        
        net_impact = avoided_loss_val - missed_pnl # Positive means "Good Filter" (Saved more than lost)
        
        report.append(f"## Comparison vs `{name}`")
        report.append(f"- **Trades Taken**: {count} (Filtered out {len(filtered_out)})")
        report.append(f"- **Total P&L**: ${pnl:,.2f} (vs Base ${base['pnl']:,.2f})")
        report.append(f"- **P&L Delta**: ${pnl - base['pnl']:,.2f}")
        report.append("")
        report.append("### The Cost of Filtering (What did we miss?)")
        report.append(f"- **Missed Winners**: {len(missed_wins)} trades")
        report.append(f"- **Opportunity Cost**: ${missed_pnl:,.2f} (Profit missed)")
        report.append("")
        report.append("### The Benefit of Filtering (What did we save?)")
        report.append(f"- **Avoided Losers**: {len(avoided_losses)} trades")
        report.append(f"- **Risk Savings**: ${avoided_loss_val:,.2f} (Losses avoided)")
        report.append("")
        report.append(f"### Net Efficiency: ${net_impact:,.2f}")
        report.append(f"*(Did we save more than we lost? { 'YES ✅' if net_impact > 0 else 'NO ❌' })*")
        report.append("---")
        
    # Save Report
    with open("OR_Impact_Analysis.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        
    print("\nAnalysis saved to OR_Impact_Analysis.md")

if __name__ == '__main__':
    analyze_impact()
