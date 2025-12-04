import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta

DATA_DIR = Path("data")

def get_expected_delta(timeframe):
    if timeframe == "1m": return pd.Timedelta(minutes=1)
    if timeframe == "5m": return pd.Timedelta(minutes=5)
    if timeframe == "15m": return pd.Timedelta(minutes=15)
    if timeframe == "30m": return pd.Timedelta(minutes=30)
    if timeframe == "1h": return pd.Timedelta(hours=1)
    if timeframe == "4h": return pd.Timedelta(hours=4)
    if timeframe == "1D": return pd.Timedelta(days=1)
    if timeframe == "1W": return pd.Timedelta(weeks=1)
    return None

def analyze_file(filepath):
    try:
        df = pd.read_parquet(filepath)
    except Exception as e:
        return f"Error reading {filepath.name}: {e}"

    if df.empty:
        return f"File {filepath.name} is empty."

    parts = filepath.stem.split('_')
    if len(parts) < 2:
        return f"Skipping {filepath.name}: Cannot parse ticker/timeframe."
    
    ticker = parts[0]
    timeframe = parts[1]
    
    expected_delta = get_expected_delta(timeframe)
    if not expected_delta:
        return f"Skipping {filepath.name}: Unknown timeframe {timeframe}."

    report = []
    report.append(f"## {ticker} - {timeframe}")
    report.append(f"- **Range:** {df.index.min()} to {df.index.max()}")
    report.append(f"- **Total Bars:** {len(df):,}")

    # 1. Analyze Time Gaps
    # Calculate time difference between consecutive bars
    df['time_diff'] = df.index.to_series().diff()
    
    # Filter for gaps significantly larger than expected (e.g., > 3x interval to skip minor hiccups, 
    # but we need to handle weekends for intraday data). 
    # For simplicity, let's look for gaps > 2 days for intraday, and > 4 days for daily.
    
    gap_threshold = expected_delta * 1.5 # Strict check first
    
    gaps = df[df['time_diff'] > gap_threshold].copy()
    
    if not gaps.empty:
        report.append(f"- **Significant Time Gaps (Top 10):**")
        # Sort by size of gap
        gaps = gaps.sort_values('time_diff', ascending=False).head(10)
        
        for idx, row in gaps.iterrows():
            prev_idx = idx - row['time_diff']
            duration = row['time_diff']
            # Simple heuristic to label weekends
            is_weekend = duration >= pd.Timedelta(days=2) and duration <= pd.Timedelta(days=3)
            note = " (Likely Weekend)" if is_weekend and timeframe not in ['1W', '1M'] else ""
            
            report.append(f"  - {prev_idx} -> {idx} : Gap of {duration}{note}")
    else:
        report.append("- No significant time gaps found.")

    # 2. Analyze Volume Gaps (0 or NaN)
    if 'volume' in df.columns:
        # Check for NaN
        nan_vol = df['volume'].isna().sum()
        # Check for 0
        zero_vol = (df['volume'] == 0).sum()
        
        report.append(f"- **Volume Analysis:**")
        report.append(f"  - NaN Volume Bars: {nan_vol:,}")
        report.append(f"  - Zero Volume Bars: {zero_vol:,}")
        
        if zero_vol > 0:
            # Find ranges of zero volume
            is_zero = df['volume'] == 0
            # Group consecutive zeros
            # Create a group id that changes when is_zero changes
            groups = (is_zero != is_zero.shift()).cumsum()
            zero_ranges = df[is_zero].groupby(groups)
            
            significant_zero_ranges = []
            for _, group in zero_ranges:
                if len(group) > 10: # Only report if > 10 consecutive bars
                    start = group.index.min()
                    end = group.index.max()
                    count = len(group)
                    significant_zero_ranges.append((start, end, count))
            
            if significant_zero_ranges:
                report.append("  - **Significant Zero Volume Ranges (>10 bars):**")
                # Sort by count descending
                significant_zero_ranges.sort(key=lambda x: x[2], reverse=True)
                for start, end, count in significant_zero_ranges[:10]:
                    report.append(f"    - {start} to {end} ({count} bars)")
    else:
        report.append("- **Volume Analysis:** No volume column found.")

    return "\n".join(report)

def main():
    print("Analyzing Parquet files for data gaps...\n")
    
    report_lines = []
    files = sorted(list(DATA_DIR.glob("*.parquet")))
    
    for f in files:
        print(f"Processing {f.name}...")
        result = analyze_file(f)
        report_lines.append(result)
        report_lines.append("\n" + "-"*40 + "\n")
        
    output_path = "DATA_GAPS_REPORT.md"
    with open(output_path, "w") as f:
        f.write("# Data Gaps Report\n\n")
        f.write("\n".join(report_lines))
        
    print(f"\nAnalysis complete. Report saved to {output_path}")

if __name__ == "__main__":
    main()
