"""
Unified Strategy Analysis Tool
==============================
A robust CLI for analyzing TradingView strategy exports.

Modes:
1. Standard: Calculate Grade, EV, RoR, and full stats.
2. Comparative: Compare multiple datasets to find the "Delta" (Cost vs Benefit).
3. Forensic: Enrich dataset with external context (News, Profiler, VWAP).

Usage:
    python analyze_strategy.py [FILES...] --mode [standard|compare|forensic]
    
Examples:
    python analyze_strategy.py data/strat_v3.xlsx --mode standard
    python analyze_strategy.py data/v3_base.xlsx data/v3_filter.xlsx --mode compare
    python analyze_strategy.py data/v3_losers.xlsx --mode forensic
"""

import argparse
import glob
import os
import pandas as pd
from modules import loaders, metrics, forensics, reporting

def run_standard_analysis(files):
    print(f"--- STANDARD ANALYSIS ({len(files)} files) ---")
    datasets = []
    for f in files:
        print(f"Loading {f}...")
        df = loaders.load_strategy_data(f)
        if df is not None:
            stats = metrics.calculate_edge_metrics(df)
            datasets.append({'name': os.path.basename(f), 'df': df, 'stats': stats})
            
    if not datasets:
        print("No valid data loaded.")
        return

    # Generate Report
    report = reporting.generate_standard_report(datasets, [d['stats'] for d in datasets])
    
    # Save
    out_path = "Analysis_Report_Standard.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to {out_path}")
    print(report) # Print to stdout for immediate view

def run_comparative_analysis(files):
    print(f"--- COMPARATIVE ANALYSIS ({len(files)} files) ---")
    datasets = []
    for f in files:
        df = loaders.load_strategy_data(f)
        if df is not None:
            # We need stats for P&L sum
            stats = metrics.calculate_edge_metrics(df)
            datasets.append({'name': os.path.basename(f), 'df': df, 'stats': stats})
            
    if len(datasets) < 2:
        print("Need at least 2 datasets to compare.")
        return
        
    # Sort by Trade Count DESC (Assume Baseline = Most Trades)
    datasets.sort(key=lambda x: len(x['df']), reverse=True)
    base = datasets[0]
    others = datasets[1:]
    
    print(f"Base Case identified: {base['name']} ({len(base['df'])} trades)")
    
    deltas = []
    for comp in others:
        # Calculate Delta
        # Logic: Find trades in Base that are NOT in Comp
        # Key: Entry Time (String format for easy matching)
        base_df = base['df'].copy()
        comp_df = comp['df'].copy()
        
        base_df['_key'] = base_df['Entry Time'].astype(str)
        comp_df['_key'] = comp_df['Entry Time'].astype(str)
        
        # Filtered Out = In Base but Not in Comp
        filtered_out = base_df[~base_df['_key'].isin(comp_df['_key'])]
        
        missed_wins = filtered_out[filtered_out['Net P&L USD'] > 0]
        avoided_losses = filtered_out[filtered_out['Net P&L USD'] <= 0]
        
        deltas.append({
            'missed_wins_count': len(missed_wins),
            'missed_pnl': missed_wins['Net P&L USD'].sum(),
            'avoided_loss_count': len(avoided_losses),
            'avoided_loss_val': abs(avoided_losses['Net P&L USD'].sum()),
            'net_impact': abs(avoided_losses['Net P&L USD'].sum()) - missed_wins['Net P&L USD'].sum()
        })
        
    # Generate Report
    report = reporting.generate_comparison_report(base, others, deltas)
    
    # Save
    out_path = "Analysis_Report_Comparative.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to {out_path}")

def run_forensic_analysis(files):
    # Usually run on just one file (the Losers file), but can handle list
    print(f"--- FORENSIC ANALYSIS ({len(files)} files) ---")
    
    # Load Context
    print("Loading Context Data...")
    news = loaders.load_news_events()
    profiler = loaders.load_profiler()
    or_data = loaders.load_or_data()
    vwap = loaders.load_vwap()
    
    for f in files:
        print(f"\nAnalyzing {f}...")
        df = loaders.load_strategy_data(f)
        if df is None: continue
        
        # Enrich
        enriched = forensics.enrich_with_context(df, news, profiler, or_data, vwap)
        
        # Stats
        summary_text = forensics.generate_forensic_summary(enriched)
        
        # Report
        report = reporting.generate_forensic_report({'name': os.path.basename(f)}, summary_text)
        
        out_path = f"Forensic_{os.path.basename(f)}.md"
        with open(out_path, "w", encoding="utf-8") as outfile:
            outfile.write(report)
        print(f"Saved to {out_path}")
        print(summary_text)

def main():
    parser = argparse.ArgumentParser(description="Unified Strategy Analysis Tool")
    parser.add_argument('files', nargs='+', help='Path to Excel files (supports glob like data/*.xlsx)')
    parser.add_argument('--mode', choices=['standard', 'compare', 'forensic'], default='standard', help='Analysis Mode')
    
    args = parser.parse_args()
    
    # Expand globs
    expanded_files = []
    for f_pattern in args.files:
        expanded_files.extend(glob.glob(f_pattern))
        
    # Filter duplicates and non-existent
    valid_files = sorted(list(set([f for f in expanded_files if os.path.exists(f)])))
    
    if not valid_files:
        print("No valid files found.")
        return
        
    if args.mode == 'standard':
        run_standard_analysis(valid_files)
    elif args.mode == 'compare':
        run_comparative_analysis(valid_files)
    elif args.mode == 'forensic':
        run_forensic_analysis(valid_files)

if __name__ == '__main__':
    main()
