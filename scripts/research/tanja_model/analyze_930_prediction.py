"""
9:30 Candle Direction Prediction (Vectorized MFE/MAE)
=====================================================
Highly optimized version using Pandas/Numpy vectorization.
Calculates MFE/MAE extension stats for 9:30 breakout across multiple windows.

Output:
- Saves results to docs/strategies/9_30_breakout/tanja_model/output/
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import time

DATA_DIR = Path("data")
DOCS_DIR = Path("docs/strategies/9_30_breakout/tanja_model/output")
TICKER = "NQ1"

def load_data():
    """Load and prep 1-minute data."""
    file_path = DATA_DIR / f"{TICKER}_1m.parquet"
    print(f"Loading {file_path}...")
    df = pd.read_parquet(file_path)
    
    # Ensure datetime index in EST
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
        df = df.set_index('datetime')
    
    # Create Date and Time columns for grouping
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    
    return df

def main():
    print("="*70)
    print(f"9:30 VECTORIZED ANALYSIS ({TICKER})")
    print("="*70)
    
    # Ensure output dir exists
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    
    df = load_data()
    print(f"Loaded {len(df)} rows. Range: {df.index.min()} to {df.index.max()}")
    
    # 1. Isolate 9:30 Candle
    print("Extracting 9:30 ranges...")
    df_930 = df[df['time_only'] == time(9, 30)].copy()
    df_930['dir_930'] = np.where(df_930['close'] > df_930['open'], 'BULLISH',
                        np.where(df_930['close'] < df_930['open'], 'BEARISH', 'DOJI'))
    
    # Drop Dojis (optional, but consistent with previous logic)
    df_930 = df_930[df_930['dir_930'] != 'DOJI']
    
    # Key stats to join later
    daily_stats = df_930[['date', 'open', 'close', 'high', 'low', 'dir_930']].rename(
        columns={'open': 'open930', 'close': 'close930', 'high': 'high930', 'low': 'low930'}
    )
    daily_stats = daily_stats.set_index('date')
    
    # 2. Define Windows
    windows = [
        (time(9, 30), time(9, 44), "09:30-09:44"),
        (time(9, 45), time(10, 0), "09:45-10:00"),
        (time(10, 0), time(10, 30), "10:00-10:30"),
        (time(10, 30), time(11, 0), "10:30-11:00"),
        (time(11, 0), time(11, 30), "11:00-11:30"),
        (time(11, 30), time(12, 0), "11:30-12:00"),
    ]
    
    # Consolidate results
    results = daily_stats.copy()
    
    # Filter main DF to relevant hours (opt)
    df_rth = df[(df.index.time >= time(9, 30)) & (df.index.time <= time(12, 0))]
    
    print("Processing windows (Vectorized)...")
    for start_t, end_t, label in windows:
        # Filter rows in this time window
        mask = (df_rth['time_only'] >= start_t) & (df_rth['time_only'] <= end_t)
        df_win = df_rth[mask]
        
        # Groupby Date -> Get Max High, Min Low
        win_stats = df_win.groupby('date').agg(
            win_high=('high', 'max'),
            win_low=('low', 'min')
        )
        
        # Merge with daily stats
        # using 'left' to keep only days where we have 9:30 data
        temp = results.merge(win_stats, left_index=True, right_index=True, how='left')
        
        # Vectorized MFE/MAE calculation
        # MFE = Extension in 9:30 Direction
        # MAE = Extension Against
        
        # Pre-calculate Up/Down Extensions
        # Clip at 0 (meaning price must break range to count)
        ext_up = (temp['win_high'] - temp['high930']) / temp['high930'] * 100
        ext_up = ext_up.clip(lower=0)
        
        ext_down = (temp['low930'] - temp['win_low']) / temp['low930'] * 100
        ext_down = ext_down.clip(lower=0)
        
        # Assign based on Direction
        mfe_col = f'mfe_{label}'
        mae_col = f'mae_{label}'
        
        temp[mfe_col] = np.where(temp['dir_930'] == 'BULLISH', ext_up, ext_down)
        temp[mae_col] = np.where(temp['dir_930'] == 'BULLISH', ext_down, ext_up)
        
        # Save back to results
        results[mfe_col] = temp[mfe_col]
        results[mae_col] = temp[mae_col]
    
    # Helper for Mode (Histogram based)
    def calc_mode_bin(series, bin_size=0.02):
        if len(series) == 0: return 0
        bins = np.arange(0, series.max() + bin_size, bin_size)
        counts, edges = np.histogram(series, bins=bins)
        max_idx = np.argmax(counts)
        # Return center of the most frequent bin
        return (edges[max_idx] + edges[max_idx+1]) / 2

    # 3. Aggregation & Report
    print("\n" + "="*70)
    print(f"RESULTS: {len(results)} Days Analyzed")
    print("="*70)
    
    # Header for console
    print(f"\n{'Window':<15} | {'Med MFE':>9} | {'Mode MFE':>9} | {'Med MAE':>9} | {'Mode MAE':>9} | {'Ratio(Mode)':>11} | {'Win Rate':>9}")
    print("-" * 100)
    
    final_stats = []
    
    for _, _, label in windows:
        mfe_col = f'mfe_{label}'
        mae_col = f'mae_{label}'
        
        # Drop NaNs (days missing specific windows)
        valid = results[[mfe_col, mae_col]].dropna()
        
        avg_mfe = valid[mfe_col].mean()
        med_mfe = valid[mfe_col].median()
        mod_mfe = calc_mode_bin(valid[mfe_col])
        
        avg_mae = valid[mae_col].mean()
        med_mae = valid[mae_col].median()
        mod_mae = calc_mode_bin(valid[mae_col])
        
        ratio_med = med_mfe / med_mae if med_mae > 0 else 0
        ratio_mod = mod_mfe / mod_mae if mod_mae > 0 else 0
        
        win_count = (valid[mfe_col] > valid[mae_col]).sum()
        win_rate = win_count / len(valid) * 100
        
        print(f"{label:<15} | {med_mfe:>8.3f}% | {mod_mfe:>8.3f}% | {med_mae:>8.3f}% | {mod_mae:>8.3f}% | {ratio_mod:>11.2f} | {win_rate:>8.1f}%")
        
        final_stats.append({
            'Window': label,
            'Avg MFE': f"{avg_mfe:.3f}%",
            'Median MFE': f"{med_mfe:.3f}%",
            'Mode MFE': f"{mod_mfe:.3f}%",
            'Avg MAE': f"{avg_mae:.3f}%",
            'Median MAE': f"{med_mae:.3f}%",
            'Mode MAE': f"{mod_mae:.3f}%",
            'Ratio (Med)': f"{ratio_med:.2f}",
            'Ratio (Mode)': f"{ratio_mod:.2f}",
            'Win Rate': f"{win_rate:.1f}%"
        })
        
    # Save CSV Outputs
    csv_path = DOCS_DIR / "tanja_930_breakout_stats.csv"
    results.to_csv(csv_path)
    print(f"\nDetailed daily stats saved to: {csv_path}")
    
    summary_path = DOCS_DIR / "tanja_930_summary.csv"
    pd.DataFrame(final_stats).to_csv(summary_path, index=False)
    print(f"Summary stats saved to: {summary_path}")
    
    # 4. Generate Markdown Report
    report_path = DOCS_DIR / "ANALYSIS_REPORT.md"
    
    md_content = f"""# 9:30 Breakout Analysis Report ({TICKER})
**Generated Algorithmically**
**Range Analyzed:** {df.index.min().date()} to {df.index.max().date()} ({len(results)} Trading Days)

## Executive Summary
This analysis tests the predictive power of the **9:30 AM 1-minute candle direction**.
- **Theory:** If the 9:30 candle is Green (Bullish), the market should extend further UP (MFE) than DOWN (MAE).
- **Metric:** Extensions are measured as % change from the 9:30 High/Low.

## Statistical Findings

| Window | Win Rate | Median MFE | Mode MFE | Median MAE | Mode MAE | R/R (Mode) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for stat in final_stats:
        md_content += f"| **{stat['Window']}** | {stat['Win Rate']} | {stat['Median MFE']} | {stat['Mode MFE']} | {stat['Median MAE']} | {stat['Mode MAE']} | {stat['Ratio (Mode)']} |\n"

    md_content += """
## Definitions
- **MFE**: Max Favorable Excursion (extension in 9:30 direction).
- **MAE**: Max Adverse Excursion (extension against 9:30 direction).
- **Mode**: The most frequent extension value (calculated using 0.02% bins). Ideally represents the "typical" move.
- **Ratio (Mode)**: Mode MFE / Mode MAE. High ratio = The "typical" win is much larger than the "typical" adverse move.

## Detailed Data
Raw data and daily logs are available in:
- [Summary CSV](tanja_930_summary.csv)
- [Daily Log CSV](tanja_930_breakout_stats.csv)
"""

    with open(report_path, "w") as f:
        f.write(md_content)
        
    print(f"Detailed analysis report saved to: {report_path}")

if __name__ == "__main__":
    main()
