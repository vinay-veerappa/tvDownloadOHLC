"""
Extrapolate SPY EM Analysis to Futures (/ES) and SPX

This script takes the SPY-based EM analysis and creates equivalent datasets
for /ES futures and SPX index by applying price scaling factors.
"""

import pandas as pd
import numpy as np
import os

def extrapolate_to_futures_and_spx():
    print("\n" + "="*80)
    print("=== EXTRAPOLATING SPY EM ANALYSIS TO /ES AND SPX ===")
    print("="*80)
    
    # Load SPY analysis data
    spy_levels = pd.read_csv('docs/expected_moves/analysis_data/em_daily_levels.csv')
    spy_perf = pd.read_csv('docs/expected_moves/analysis_data/em_daily_performance.csv')
    spy_summary = pd.read_csv('docs/expected_moves/analysis_data/em_method_summary.csv')
    
    # Load price data for scaling
    spy_df = pd.read_parquet('data/SPY_1d.parquet')
    es_df = pd.read_parquet('data/ES1_1d.parquet')
    spx_df = pd.read_parquet('data/SPX_1d.parquet')
    
    # Normalize index
    if spy_df.index.name == 'datetime': spy_df = spy_df.reset_index()
    if es_df.index.name == 'datetime': es_df = es_df.reset_index()
    if spx_df.index.name == 'datetime': spx_df = spx_df.reset_index()
    
    spy_df['date'] = pd.to_datetime(spy_df['datetime']).dt.strftime('%Y-%m-%d')
    
    # Correction: Futures daily bars often start the previous evening (e.g., 23:00 UTC / 18:00 ET)
    # If the bar refers to the session starting "Nov 30 23:00", it is the "Dec 1" trading day.
    # We must shift dates if the hour is > 16 (4 PM)
    def normalize_trade_date(dt):
        if dt.hour > 16:
            return (dt + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        return dt.strftime('%Y-%m-%d')

    es_df['datetime_obj'] = pd.to_datetime(es_df['datetime'])
    es_df['date'] = es_df['datetime_obj'].apply(normalize_trade_date)
    
    spx_df['date'] = pd.to_datetime(spx_df['datetime']).dt.strftime('%Y-%m-%d')
    
    # Get overlapping dates in our analysis range
    analysis_dates = spy_levels['date'].unique()
    
    # Calculate scaling factors for each day
    print("\n[1] Calculating daily scaling factors...")
    
    scaling_data = []
    for date in analysis_dates:
        spy_row = spy_df[spy_df['date'] == date]
        es_row = es_df[es_df['date'] == date]
        spx_row = spx_df[spx_df['date'] == date]
        
        if spy_row.empty: continue
        spy_close = spy_row['close'].values[0]
        
        es_close = es_row['close'].values[0] if not es_row.empty else None
        spx_close = spx_row['close'].values[0] if not spx_row.empty else None
        
        es_scale = es_close / spy_close if es_close else None
        spx_scale = spx_close / spy_close if spx_close else None
        
        scaling_data.append({
            'date': date,
            'spy_close': spy_close,
            'es_close': es_close,
            'spx_close': spx_close,
            'es_scale': es_scale,
            'spx_scale': spx_scale
        })
        
    print(f"Debug: SPY Sample Dates: {spy_df['date'].head().tolist()}")
    print(f"Debug: ES Sample Dates: {es_df['date'].head().tolist()}")
    print(f"Debug: Analysis Dates matches in ES: {es_df['date'].isin(analysis_dates).sum()} / {len(analysis_dates)}")
    
    scale_df = pd.DataFrame(scaling_data)
    
    # Calculate average scaling factors
    avg_es_scale = scale_df['es_scale'].dropna().mean()
    avg_spx_scale = scale_df['spx_scale'].dropna().mean()
    
    print(f"  Average /ES to SPY scale: {avg_es_scale:.4f}")
    print(f"  Average SPX to SPY scale: {avg_spx_scale:.4f}")
    
    # ==========================================
    # Create /ES Extrapolated Data
    # ==========================================
    
    print("\n[2] Creating /ES extrapolated levels...")
    
    es_levels = spy_levels.merge(scale_df[['date', 'es_scale', 'es_close']], on='date', how='inner')
    es_levels = es_levels.dropna(subset=['es_scale'])
    
    # Scale price columns
    price_cols = ['prev_close', 'open', 'high', 'low', 'close', 'prev_week_close', 'anchor', 'level_upper', 'level_lower', 'em_value']
    for col in price_cols:
        if col in es_levels.columns:
            es_levels[col] = es_levels[col] * es_levels['es_scale']
    
    es_levels['ticker'] = 'ES'
    es_levels = es_levels.drop(columns=['es_scale', 'es_close'])
    
    # ==========================================
    # Create SPX Extrapolated Data
    # ==========================================
    
    print("[3] Creating SPX extrapolated levels...")
    
    spx_levels = spy_levels.merge(scale_df[['date', 'spx_scale', 'spx_close']], on='date', how='inner')
    spx_levels = spx_levels.dropna(subset=['spx_scale'])
    
    for col in price_cols:
        if col in spx_levels.columns:
            spx_levels[col] = spx_levels[col] * spx_levels['spx_scale']
    
    spx_levels['ticker'] = 'SPX'
    spx_levels = spx_levels.drop(columns=['spx_scale', 'spx_close'])
    
    # ==========================================
    # Save Extrapolated Data
    # ==========================================
    
    print("\n[4] Saving extrapolated datasets...")
    
    es_levels.to_csv('docs/expected_moves/analysis_data/em_daily_levels_ES.csv', index=False)
    spx_levels.to_csv('docs/expected_moves/analysis_data/em_daily_levels_SPX.csv', index=False)
    
    print(f"  Saved {len(es_levels)} rows to em_daily_levels_ES.csv")
    print(f"  Saved {len(spx_levels)} rows to em_daily_levels_SPX.csv")
    
    # ==========================================
    # Verify Performance (should match SPY)
    # ==========================================
    
    print("\n[5] Performance Verification (should match SPY)...")
    
    # The performance metrics (containment %, MFE, MAE) should be identical
    # because we're scaling both the EM levels AND the price data proportionally
    
    print("\n  Since we scale both EM and price by the same factor,")
    print("  the percentage-based metrics (containment, MFE/MAE ratios)")
    print("  remain identical to SPY. See em_method_summary.csv for stats.")
    
    # Create summary with ticker labels
    spy_summary['ticker'] = 'SPY'
    es_summary = spy_summary.copy()
    es_summary['ticker'] = 'ES'
    spx_summary = spy_summary.copy()
    spx_summary['ticker'] = 'SPX'
    
    combined_summary = pd.concat([spy_summary, es_summary, spx_summary])
    combined_summary.to_csv('docs/expected_moves/analysis_data/em_method_summary_all.csv', index=False)
    
    print(f"  Saved combined summary to em_method_summary_all.csv")
    
    # ==========================================
    # Create Practical Levels Table
    # ==========================================
    
    print("\n[6] Creating practical levels lookup table...")
    
    # For a random recent day, show the actual levels
    sample_date = analysis_dates[-5]  # 5 days ago
    
    spy_sample = spy_levels[
        (spy_levels['date'] == sample_date) & 
        (spy_levels['method'] == 'synth_vix_100_open') &
        (spy_levels['multiple'].isin([0.5, 1.0, 1.5]))
    ][['date', 'method', 'multiple', 'anchor', 'level_upper', 'level_lower']]
    
    es_sample = es_levels[
        (es_levels['date'] == sample_date) & 
        (es_levels['method'] == 'synth_vix_100_open') &
        (es_levels['multiple'].isin([0.5, 1.0, 1.5]))
    ][['date', 'method', 'multiple', 'anchor', 'level_upper', 'level_lower']]
    
    spx_sample = spx_levels[
        (spx_levels['date'] == sample_date) & 
        (spx_levels['method'] == 'synth_vix_100_open') &
        (spx_levels['multiple'].isin([0.5, 1.0, 1.5]))
    ][['date', 'method', 'multiple', 'anchor', 'level_upper', 'level_lower']]
    
    print(f"\n  Sample Date: {sample_date}")
    print("\n  SPY Levels:")
    print(spy_sample.to_string(index=False))
    print("\n  /ES Levels:")
    print(es_sample.to_string(index=False))
    print("\n  SPX Levels:")
    print(spx_sample.to_string(index=False))
    
    print("\n" + "="*80)
    print("=== EXTRAPOLATION COMPLETE ===")
    print("="*80)
    print("\nOutput Files:")
    print("  - docs/expected_moves/analysis_data/em_daily_levels_ES.csv")
    print("  - docs/expected_moves/analysis_data/em_daily_levels_SPX.csv")
    print("  - docs/expected_moves/analysis_data/em_method_summary_all.csv")

if __name__ == "__main__":
    extrapolate_to_futures_and_spx()
