"""
Visualize NY Levels Statistics.
Reads JSON stats and prints a formatted report/markdown.
"""

import json
import pandas as pd
from pathlib import Path
import argparse

DATA_DIR = Path("data")

def format_distribution(dist_dict, title):
    if not dist_dict: return "No data"
    
    # Sort keys (percentiles)
    items = sorted([(int(k), v) for k, v in dist_dict.items()])
    
    report = [f"### {title}"]
    report.append(f"| Percentile | Value (%) |")
    report.append(f"|------------|-----------|")
    for p, v in items:
        # Show key milestones
        if p % 10 == 0 or p in [2, 5, 95, 98]:
            report.append(f"| {p}% | {v:.4f}% |")
    
    return "\n".join(report)

def format_time_dist(time_dict, title, top_n=10):
    if not time_dict: return "No data"
    
    sorted_times = sorted(time_dict.items(), key=lambda x: x[1], reverse=True)
    
    report = [f"### {title} (Top {top_n})"]
    report.append(f"| Time | Count |")
    report.append(f"|------|-------|")
    for t, c in sorted_times[:top_n]:
        report.append(f"| {t} | {c} |")
        
    return "\n".join(report)

def generate_report(ticker: str, grouping='D'):
    suffix = f"_{grouping}" if grouping != 'D' else ""
    file_path = DATA_DIR / f"{ticker}_ny_levels_stats{suffix}.json"
    
    if not file_path.exists():
        print(f"Stats file not found: {file_path}")
        return

    with open(file_path, 'r') as f:
        data = json.load(f)
        
    print(f"\n{'='*40}")
    print(f"NY LEVELS REPORT: {ticker} ({grouping})")
    print(f"{'='*40}")
    
    if grouping == 'D':
        print(f"\nTotal Days: {data['count']}")
        print(f"Median Peak Time (Bull): {data['median_peak_time_bull']}")
        print(f"Median Peak Time (Bear): {data['median_peak_time_bear']}")
        
        print("\n" + format_distribution(data['bull_mfe_dist'], "Bullish MFE Distribution"))
        print("\n" + format_distribution(data['bear_mfe_dist'], "Bearish MFE Distribution"))
        print("\n" + format_time_dist(data['time_dist_bull'], "Bullish Peak Time Distribution"))
    else:
        # Grouped data
        for group_name, group_stats in data.items():
            print(f"\n--- Group: {group_name} (Count: {group_stats['count']}) ---")
            print(f"Median Peak Time (Bull): {group_stats['median_peak_time_bull']}")
            print(f"Median Peak Time (Bear): {group_stats['median_peak_time_bear']}")
            # Summarize 50th percentile for quick look
            p50_bull = group_stats['bull_mfe_dist'].get('50', 'N/A')
            p50_bear = group_stats['bear_mfe_dist'].get('50', 'N/A')
            print(f"50th Percentile MFE: Bull {p50_bull}% | Bear {p50_bear}%")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="NQ1")
    parser.add_argument("--grouping", choices=['D', 'M', 'Q', 'Y'], default='D')
    args = parser.parse_args()
    
    generate_report(args.ticker, args.grouping)
