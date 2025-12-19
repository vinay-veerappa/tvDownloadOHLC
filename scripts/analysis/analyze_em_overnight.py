"""
Overnight Session EM Analysis for ES Futures

This script analyzes how Close-based EM levels (from SPY) perform during the
ES futures overnight session (16:00 to 09:30 next day).

Key Questions:
1. How often do overnight ES prices reach the previous day's EM levels?
2. Do the levels act as S/R during the overnight session?
3. Should we use yesterday's Open or yesterday's Close as the anchor for overnight?
"""

import pandas as pd
import numpy as np
import os

def analyze_overnight_em():
    print("\n" + "="*80)
    print("=== ES OVERNIGHT SESSION EM ANALYSIS ===")
    print("="*80)
    
    # Load ES 5m data for overnight analysis
    es_5m = pd.read_parquet('data/ES1_5m.parquet')
    if es_5m.index.name == 'datetime': es_5m = es_5m.reset_index()
    es_5m['dt'] = pd.to_datetime(es_5m['datetime'])
    es_5m['date'] = es_5m['dt'].dt.strftime('%Y-%m-%d')
    es_5m['time'] = es_5m['dt'].dt.time
    
    # Load SPY EM data (we'll scale to ES)
    spy_master = pd.read_csv('docs/expected_moves/analysis_data/em_master_dataset.csv')
    
    # Load ES daily for scaling
    es_daily = pd.read_parquet('data/ES1_1d.parquet')
    if es_daily.index.name == 'datetime': es_daily = es_daily.reset_index()
    es_daily['date'] = pd.to_datetime(es_daily['datetime']).dt.strftime('%Y-%m-%d')
    
    # Load SPY daily for scaling
    spy_daily = pd.read_parquet('data/SPY_1d.parquet')
    if spy_daily.index.name == 'datetime': spy_daily = spy_daily.reset_index()
    spy_daily['date'] = pd.to_datetime(spy_daily['datetime']).dt.strftime('%Y-%m-%d')
    
    # Merge to get scaling factors
    scale_df = pd.merge(
        spy_daily[['date', 'close']].rename(columns={'close': 'spy_close'}),
        es_daily[['date', 'close', 'open', 'high', 'low']].rename(columns={
            'close': 'es_close', 'open': 'es_open', 'high': 'es_high', 'low': 'es_low'
        }),
        on='date', how='inner'
    )
    scale_df['scale'] = scale_df['es_close'] / scale_df['spy_close']
    
    # Merge EM data with scaling
    df = pd.merge(spy_master, scale_df, left_on='date_str', right_on='date', how='inner')
    
    print(f"\nLoaded {len(df)} days with matching ES/SPY data")
    
    # ==========================================
    # Calculate ES-scaled EM levels
    # ==========================================
    
    print("\n[1] Calculating ES-scaled EM levels...")
    
    # Close-Anchored EMs (using prev day's ES close as anchor)
    df['es_prev_close'] = df['es_close'].shift(1)
    df['es_prev_open'] = df['es_open'].shift(1)
    
    # Scale the SPY EM values to ES
    df['em_straddle_085_es'] = df['em_close_straddle_085'] * df['scale']
    df['em_straddle_100_es'] = df['em_close_straddle_100'] * df['scale']
    df['em_synth_085_es'] = df['em_open_vix_synth_085'] * df['scale']
    df['em_synth_100_es'] = df['em_open_vix_synth_100'] * df['scale']
    
    # Previous day's EM levels (anchored to prev close)
    df['prev_close_upper_50'] = df['es_prev_close'] + df['em_straddle_085_es'].shift(1) * 0.5
    df['prev_close_lower_50'] = df['es_prev_close'] - df['em_straddle_085_es'].shift(1) * 0.5
    df['prev_close_upper_100'] = df['es_prev_close'] + df['em_straddle_085_es'].shift(1) * 1.0
    df['prev_close_lower_100'] = df['es_prev_close'] - df['em_straddle_085_es'].shift(1) * 1.0
    
    # Previous day's Open-anchored levels
    df['prev_open_upper_50'] = df['es_prev_open'] + df['em_straddle_085_es'].shift(1) * 0.5
    df['prev_open_lower_50'] = df['es_prev_open'] - df['em_straddle_085_es'].shift(1) * 0.5
    df['prev_open_upper_100'] = df['es_prev_open'] + df['em_straddle_085_es'].shift(1) * 1.0
    df['prev_open_lower_100'] = df['es_prev_open'] - df['em_straddle_085_es'].shift(1) * 1.0
    
    # ==========================================
    # Analyze Overnight Session
    # ==========================================
    
    print("\n[2] Analyzing overnight session (16:00 - 09:30)...")
    
    from datetime import time as dt_time
    
    overnight_results = []
    
    for idx, row in df.iterrows():
        if pd.isna(row['es_prev_close']): continue
        
        current_date = row['date']
        prev_date = df.iloc[idx-1]['date'] if idx > 0 else None
        if not prev_date: continue
        
        # Get overnight bars (after 16:00 on prev day OR before 09:30 on current day)
        overnight_bars = es_5m[
            ((es_5m['date'] == prev_date) & (es_5m['time'] >= dt_time(16, 0))) |
            ((es_5m['date'] == current_date) & (es_5m['time'] < dt_time(9, 30)))
        ]
        
        if overnight_bars.empty: continue
        
        overnight_high = overnight_bars['high'].max()
        overnight_low = overnight_bars['low'].min()
        overnight_open = overnight_bars.iloc[0]['open']
        overnight_close = overnight_bars.iloc[-1]['close']
        
        # Check level interactions
        for anchor_name, anchor_val in [('prev_close', row['es_prev_close']), ('prev_open', row['es_prev_open'])]:
            for mult in [0.5, 1.0]:
                em_val = row['em_straddle_085_es']
                if pd.isna(em_val): continue
                
                level_upper = anchor_val + em_val * mult
                level_lower = anchor_val - em_val * mult
                
                touched_upper = overnight_high >= level_upper
                touched_lower = overnight_low <= level_lower
                contained = (overnight_high < level_upper) and (overnight_low > level_lower)
                
                # MFE/MAE from overnight open
                mfe_overnight = (overnight_high - overnight_open) / em_val if em_val > 0 else 0
                mae_overnight = (overnight_open - overnight_low) / em_val if em_val > 0 else 0
                
                overnight_results.append({
                    'date': current_date,
                    'anchor': anchor_name,
                    'multiple': mult,
                    'anchor_price': anchor_val,
                    'em_value': em_val,
                    'level_upper': level_upper,
                    'level_lower': level_lower,
                    'overnight_high': overnight_high,
                    'overnight_low': overnight_low,
                    'overnight_open': overnight_open,
                    'overnight_close': overnight_close,
                    'touched_upper': touched_upper,
                    'touched_lower': touched_lower,
                    'contained': contained,
                    'mfe_overnight': round(mfe_overnight, 4),
                    'mae_overnight': round(mae_overnight, 4)
                })
    
    overnight_df = pd.DataFrame(overnight_results)
    
    # ==========================================
    # Save Overnight Analysis CSV
    # ==========================================
    
    print("\n[3] Saving overnight analysis CSV...")
    overnight_df.to_csv('docs/expected_moves/analysis_data/em_overnight_es.csv', index=False)
    print(f"  Saved {len(overnight_df)} rows to em_overnight_es.csv")
    
    # ==========================================
    # Summary Statistics
    # ==========================================
    
    print("\n[4] Overnight Session Summary...")
    print("\n" + "="*60)
    
    for anchor in ['prev_close', 'prev_open']:
        print(f"\n[Anchor: {anchor.upper()}]")
        for mult in [0.5, 1.0]:
            sub = overnight_df[(overnight_df['anchor'] == anchor) & (overnight_df['multiple'] == mult)]
            if sub.empty: continue
            
            containment = sub['contained'].mean() * 100
            touch_upper = sub['touched_upper'].mean() * 100
            touch_lower = sub['touched_lower'].mean() * 100
            med_mfe = sub['mfe_overnight'].median()
            med_mae = sub['mae_overnight'].median()
            
            print(f"\n  {mult*100:.0f}% EM:")
            print(f"    Containment: {containment:.1f}%")
            print(f"    Touch Upper: {touch_upper:.1f}%")
            print(f"    Touch Lower: {touch_lower:.1f}%")
            print(f"    Median MFE:  {med_mfe:.3f}")
            print(f"    Median MAE:  {med_mae:.3f}")
    
    # ==========================================
    # Create Overnight Summary CSV
    # ==========================================
    
    summary_rows = []
    for anchor in ['prev_close', 'prev_open']:
        for mult in [0.5, 1.0, 1.5]:
            sub = overnight_df[(overnight_df['anchor'] == anchor) & (overnight_df['multiple'] == mult)]
            if sub.empty: continue
            
            summary_rows.append({
                'session': 'overnight',
                'anchor': anchor,
                'multiple': mult,
                'containment_pct': round(sub['contained'].mean() * 100, 2),
                'touch_upper_pct': round(sub['touched_upper'].mean() * 100, 2),
                'touch_lower_pct': round(sub['touched_lower'].mean() * 100, 2),
                'median_mfe': round(sub['mfe_overnight'].median(), 4),
                'median_mae': round(sub['mae_overnight'].median(), 4),
                'sample_size': len(sub)
            })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv('docs/expected_moves/analysis_data/em_overnight_summary.csv', index=False)
    print(f"\n  Saved summary to em_overnight_summary.csv")
    
    print("\n" + "="*80)
    print("=== OVERNIGHT ANALYSIS COMPLETE ===")
    print("="*80)

if __name__ == "__main__":
    analyze_overnight_em()
