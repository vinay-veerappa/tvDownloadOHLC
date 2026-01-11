"""
Tanja Model: Full Chain Analysis
================================
Tests the complete causal chain of the strategy:
1. Signal: 9:28/9:32 Candle Pattern (Gap, On Top, etc.)
2. Trigger: 9:30 Candle Direction (Green/Red)
3. Outcome: Session MFE > MAE (09:30 - 10:30 Window)

Hypothesis:
If we only take 9:30 breakouts that are *aligned* with the 9:28/9:32 pattern,
is the win rate and risk/reward significantly better?
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import time, date

DATA_DIR = Path("data")
DOCS_DIR = Path("docs/strategies/9_30_breakout/tanja_model/output")
TICKER = "NQ1"

def load_data():
    file_path = DATA_DIR / f"{TICKER}_1m.parquet"
    print(f"Loading {file_path}...")
    df = pd.read_parquet(file_path)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
        df = df.set_index('datetime')
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    return df

def main():
    print("="*70)
    print(f"TANJA FULL CHAIN ANALYSIS ({TICKER})")
    print("="*70)
    
    # Ensure output dir exists
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    
    df = load_data()
    print(f"Loaded {len(df)} rows. Range: {df.index.min()} to {df.index.max()}")
    
    # ---------------------------------------------------------
    # 1. Identify 9:28, 9:30, 9:32 Candles
    # ---------------------------------------------------------
    print("Extracting Key Candles...")
    
    # Extract times
    times = [time(9, 28), time(9, 30), time(9, 32)]
    cols = ['open', 'high', 'low', 'close']
    
    daily_data = pd.DataFrame(index=df['date'].unique())
    
    for t in times:
        t_str = t.strftime("%H%M")
        subset = df[df['time_only'] == t].copy()
        subset = subset.set_index('date')
        subset = subset[cols].rename(columns={c: f"{c}{t_str}" for c in cols})
        daily_data = daily_data.join(subset)
    
    # Drop rows with missing data
    daily_data = daily_data.dropna()
    print(f"Valid Trading Days with all candles: {len(daily_data)}")
    
    # ---------------------------------------------------------
    # 2. Pattern Classification (9:28 vs 9:32)
    # ---------------------------------------------------------
    d = daily_data # shortcut
    
    # 9:28 Direction
    d['dir_928'] = np.where(d['close0928'] > d['open0928'], 'BULLISH',
                   np.where(d['close0928'] < d['open0928'], 'BEARISH', 'DOJI'))
                   
    # Relationship Logic
    cond_gap_up = d['low0932'] >= d['high0928']
    cond_gap_down = d['high0932'] <= d['low0928']
    cond_on_top = (d['high0932'] > d['high0928']) & (d['low0932'] > d['low0928'])
    cond_below = (d['low0932'] < d['low0928']) & (d['high0932'] < d['high0928'])
    cond_engulf = (d['high0932'] >= d['high0928']) & (d['low0932'] <= d['low0928'])
    cond_inside = (d['high0932'] <= d['high0928']) & (d['low0932'] >= d['low0928'])
    
    d['pattern'] = np.select(
        [cond_gap_up, cond_gap_down, cond_on_top, cond_below, cond_engulf, cond_inside],
        ['GAP_UP', 'GAP_DOWN', 'ON_TOP', 'BELOW', 'ENGULF', 'INSIDE'],
        default='KISS'
    )
    
    # ---------------------------------------------------------
    # 3. 9:30 Range & Direction
    # ---------------------------------------------------------
    d['dir_930'] = np.where(d['close0930'] > d['open0930'], 'BULLISH',
                   np.where(d['close0930'] < d['open0930'], 'BEARISH', 'DOJI'))
    
    # ---------------------------------------------------------
    # 4. Session Outcome (09:30 - 10:30)
    # Using 1 hour window as the "Golden" window from previous analysis
    # ---------------------------------------------------------
    start_t = time(9, 30)
    end_t = time(10, 30)
    
    # Get Max High / Min Low for this window
    df_win = df[(df['time_only'] >= start_t) & (df['time_only'] <= end_t)]
    win_stats = df_win.groupby('date').agg(
        win_high=('high', 'max'),
        win_low=('low', 'min')
    )
    
    d = d.join(win_stats).dropna()
    
    # Calculate MFE/MAE based on 9:30 Direction
    # If 9:30 Bullish: MFE = Up Ext, MAE = Down Ext
    # If 9:30 Bearish: MFE = Down Ext, MAE = Up Ext
    
    # Base Extensions (from 9:30 Range)
    ext_up = (d['win_high'] - d['high0930']) / d['high0930'] * 100
    ext_down = (d['low0930'] - d['win_low']) / d['low0930'] * 100
    
    d['mfe'] = np.where(d['dir_930'] == 'BULLISH', ext_up, 
               np.where(d['dir_930'] == 'BEARISH', ext_down, 0))
               
    d['mae'] = np.where(d['dir_930'] == 'BULLISH', ext_down,
               np.where(d['dir_930'] == 'BEARISH', ext_up, 0))
               
    d['mfe'] = d['mfe'].clip(lower=0)
    d['mae'] = d['mae'].clip(lower=0)
    
    d['outcome_win'] = d['mfe'] > d['mae']
    
    # ---------------------------------------------------------
    # 5. Full Chain Analysis
    # ---------------------------------------------------------
    
    # Defined Signals (Bullish Bias vs Bearish Bias)
    # Bullish Signal: Gap Up, On Top, or (Engulf/Kiss if 9:28 Green)
    # For simplicity, we stick to the strong ones
    
    print("\n" + "="*80)
    print("FULL CHAIN RESULTS (Pattern -> 9:30 Dir -> Outcome)")
    print("Window: 09:30 - 10:30")
    print("="*80)
    
    combinations = [
        ('STRONG BULL', ['GAP_UP', 'ON_TOP'], 'BULLISH'),
        ('STRONG BEAR', ['GAP_DOWN', 'BELOW'], 'BEARISH'),
        # Contrarian check: Gap Up but 9:30 turns Red?
        ('FAILED BULL', ['GAP_UP', 'ON_TOP'], 'BEARISH'), 
        ('FAILED BEAR', ['GAP_DOWN', 'BELOW'], 'BULLISH'),
        # The "Judas" check
        ('ENGULF BULL 9:28', ['ENGULF'], 'BULLISH'),
    ]
    
    final_report = []
    
    print(f"{'Setup':<20} | {'Count':>6} | {'Win Rate':>8} | {'Med MFE':>8} | {'Med MAE':>8} | {'R/R':>5}")
    print("-" * 75)
    
    for label, patterns, trigger_dir in combinations:
        # Filter for pattern
        subset = d[d['pattern'].isin(patterns)]
        
        # Filter for 9:30 Trigger
        if trigger_dir:
            subset = subset[subset['dir_930'] == trigger_dir]
            
        count = len(subset)
        if count == 0: continue
        
        win_rate = subset['outcome_win'].mean() * 100
        med_mfe = subset['mfe'].median()
        med_mae = subset['mae'].median()
        rr = med_mfe / med_mae if med_mae > 0 else 0
        
        print(f"{label:<20} | {count:>6} | {win_rate:>7.1f}% | {med_mfe:>7.3f}% | {med_mae:>7.3f}% | {rr:>5.1f}")
        
        final_report.append({
            'Setup': label,
            'Count': count,
            'Win Rate': f"{win_rate:.1f}%",
            'Median MFE': f"{med_mfe:.3f}%",
            'Median MAE': f"{med_mae:.3f}%",
            'Edge': f"{rr:.1f}"
        })

    # Save
    pd.DataFrame(final_report).to_csv(DOCS_DIR / "full_chain_results.csv", index=False)
    print(f"\nResults saved to {DOCS_DIR / 'full_chain_results.csv'}")

if __name__ == "__main__":
    main()
