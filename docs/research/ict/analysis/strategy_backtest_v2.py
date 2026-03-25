import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
from tqdm import tqdm

# Add parent dir to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_loader import load_data, slice_trading_days
from config import SESSION_TIMES

def run_structural_backtest(ticker='NQ'):
    days_file = f'ict_research/data/trading_days_{ticker}.csv'
    arrays_file = f'ict_research/data/pd_arrays_{ticker}.csv'
    
    if not os.path.exists(days_file) or not os.path.exists(arrays_file):
        print("Required data files not found. Run pipeline first.")
        return

    print("Loading datasets...")
    df_days = pd.read_csv(days_file)
    df_arrays = pd.read_csv(arrays_file)
    
    # 1. FILTER SETUPS
    # Valid setup: Respected PDA in Manipulation Zone
    # Manipulation must be BULLISH or BEARISH
    df_setups = df_arrays[
        (df_arrays['in_manipulation_zone'] == True) & 
        (df_arrays['respected'] == True)
    ].copy()
    
    # Merge with day context to get manipulation direction and reversal outcome
    df_setups = df_setups.merge(df_days[['date', 'manipulation', 'manipulation_reversed', 'london_range']], on='date')
    
    if df_setups.empty:
        print("No valid structural setups found.")
        return
        
    print(f"Total Structural Setups (PDA Level Touches): {len(df_setups)}")

    # 2. LOAD 1M DATA
    print("Loading detailed 1m data...")
    df_1m = load_data(ticker, '1m')
    df_1m = slice_trading_days(df_1m)
    df_1m['date_str'] = df_1m['trading_date'].astype(str)
    day_groups = df_1m.groupby('date_str')

    ny_start = SESSION_TIMES['NY_AM'][0] # 09:30
    ny_end = SESSION_TIMES['NY_PM'][1]   # 16:00

    results = []

    print("Executing Structural Backtest...")
    # We iterate through each PDA that was respected.
    # We check if NY session hit the entry price.
    for _, arr in tqdm(df_setups.iterrows(), total=len(df_setups)):
        d_str = str(arr['date'])
        if d_str not in day_groups.groups:
            continue
            
        day_df = day_groups.get_group(d_str)
        ny_df = day_df.between_time(ny_start, ny_end)
        
        if ny_df.empty:
            continue
            
        manip = arr['manipulation']
        
        # Entry Rules:
        # Long if Bearish Manipulation (expecting reversal down?? No.)
        # Wait, the rule is:
        # BEARISH_MANIPULATION = London swept Asia HIGH -> Expect Down move in NY.
        # BULLISH_MANIPULATION = London swept Asia LOW -> Expect Up move in NY.
        
        # Correction of direction notation:
        # Prompt says: "Long if manipulation was Bearish (reversing the move down)".
        # Wait, if manipulation (London) was BEARISH (moved down into Asia Low), then NY reverses it UP (Long).
        # My classification: 
        #   "BEARISH_MANIPULATION" means London swept Asia HIGH (made a bearish fakeout). Expecting DOWN move.
        #   "BULLISH_MANIPULATION" means London swept Asia LOW (made a bullish fakeout). Expecting UP move.
        # Let's check session_extractor logic or prompt.
        # Prompt: "Long if manipulation was Bearish (reversing the move down)"
        # This implies "Bearish Manipulation" = "Move Down". 
        # But my code uses ICT terminology: "Bearish Manipulation" = "Bearish Setup" (Sweep High then Revert).
        
        if manip == "BEARISH_MANIPULATION": # Sweep High -> Expect reversal DOWN (Short)
            direction = "SHORT"
            entry_price = arr['low'] # Enter at bottom of Bearish Zone
        elif manip == "BULLISH_MANIPULATION": # Sweep Low -> Expect reversal UP (Long)
            direction = "LONG"
            entry_price = arr['high'] # Enter at top of Bullish Zone
        else:
            continue

        # Check for Touch during NY
        idx_touch = None
        if direction == "LONG":
            # Price enters zone: low trades into entry_price
            touch_mask = ny_df['low'] <= entry_price
        else:
            # Price enters zone: high trades into entry_price
            touch_mask = ny_df['high'] >= entry_price
            
        if not touch_mask.any():
            # Never touched during NY
            continue
            
        touch_time = ny_df[touch_mask].index[0]
        # Data from touch time onwards
        trade_df = ny_df[ny_df.index >= touch_time]
        
        if trade_df.empty:
            continue
            
        # Metrics Calculation
        highs = trade_df['high'].values
        lows = trade_df['low'].values
        
        max_high = np.max(highs)
        min_low = np.min(lows)
        
        if direction == "LONG":
            mfe_pts = max_high - entry_price
            mae_pts = entry_price - min_low
        else:
            mfe_pts = entry_price - min_low
            mae_pts = max_high - entry_price
            
        # Convert to Percentages
        mfe_pct = (mfe_pts / entry_price) * 100
        mae_pct = (mae_pts / entry_price) * 100
        
        results.append({
            'date': d_str,
            'pda_type': arr['type'],
            'direction': direction,
            'entry_price': entry_price,
            'win': arr['manipulation_reversed'],
            'mfe_pct': mfe_pct,
            'mae_pct': mae_pct,
            'mfe_pts': mfe_pts,
            'mae_pts': mae_pts
        })

    df_results = pd.DataFrame(results)
    
    if df_results.empty:
        print("No trades executed based on touch criteria.")
        return

    # 3. REPORTING
    print("\n" + "="*60)
    print("ICT STRUCTURAL REVERSION BACKTEST REPORT".center(60))
    print("="*60)
    
    print(f"Total Trades Executed:   {len(df_results)}")
    print(f"Overall Win Rate:        {df_results['win'].mean() * 100:.2f}%")
    print(f"Average MAE (%):         {df_results['mae_pct'].mean():.4f}%")
    print(f"Average MFE (%):         {df_results['mfe_pct'].mean():.4f}%")
    print(f"Median MAE (%):          {df_results['mae_pct'].median():.4f}%")
    print(f"Median MFE (%):          {df_results['mfe_pct'].median():.4f}%")

    # Breakdown by PDA Type
    print("\n--- Performance by PD Array Type ---")
    type_stats = df_results.groupby('pda_type').agg({
        'win': ['count', 'mean'],
        'mae_pct': 'mean',
        'mfe_pct': 'mean'
    })
    type_stats.columns = ['Count', 'Win Rate (%)', 'Avg MAE (%)', 'Avg MFE (%)']
    type_stats['Win Rate (%)'] *= 100
    print(type_stats.to_string())

    # OB vs Swing Analysis
    def classify_class(t):
        if 'OB' in t: return 'Order Block'
        if 'SWING' in t: return 'Swing'
        return 'Other (FVG)'
        
    df_results['pda_class'] = df_results['pda_type'].apply(classify_class)
    class_stats = df_results.groupby('pda_class').agg({
        'win': ['count', 'mean'],
        'mae_pct': 'mean',
        'mfe_pct': 'mean'
    })
    class_stats.columns = ['Count', 'Win Rate (%)', 'Avg MAE (%)', 'Avg MFE (%)']
    class_stats['Win Rate (%)'] *= 100
    print("\n--- OB vs Swing Performance ---")
    print(class_stats.to_string())

    # Visual: MAE/MFE Distribution (Percentage Based)
    os.makedirs('ict_research/reports', exist_ok=True)
    plt.figure(figsize=(10, 6))
    
    wins = df_results[df_results['win'] == True]
    losses = df_results[df_results['win'] == False]
    
    plt.scatter(wins['mae_pct'], wins['mfe_pct'], color='green', label='Reversed', alpha=0.5)
    plt.scatter(losses['mae_pct'], losses['mfe_pct'], color='red', label='Failed', alpha=0.5)
    
    plt.axvline(df_results['mae_pct'].median(), color='gray', linestyle='--', label=f"Med MAE {df_results['mae_pct'].median():.3f}%")
    
    plt.xlabel('MAE (%)')
    plt.ylabel('MFE (%)')
    plt.title(f'Structural Backtest: MAE vs MFE (%) - {ticker}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    report_plot = f'ict_research/reports/structural_mae_mfe_{ticker}.png'
    plt.savefig(report_plot)
    print(f"\nReport plot saved to {report_plot}")

    # Generate Detailed Text Report
    report_file = f'ict_research/reports/structural_report_{ticker}.txt'
    with open(report_file, 'w') as f:
        f.write("="*60 + "\n")
        f.write("ICT STRUCTURAL BACKTEST REPORT\n")
        f.write(f"Instrument: {ticker} | NY Session Reversals\n")
        f.write("="*60 + "\n\n")
        f.write(f"Total Array Touches during NY: {len(df_results)}\n")
        f.write(f"Aggregate Win Rate (Reversal): {df_results['win'].mean() * 100:.2f}%\n\n")
        f.write("Aggregated Metrics:\n")
        f.write(f"  - Avg MAE: {df_results['mae_pct'].mean():.4f}%\n")
        f.write(f"  - Avg MFE: {df_results['mfe_pct'].mean():.4f}%\n")
        f.write(f"  - Median MAE: {df_results['mae_pct'].median():.4f}%\n\n")
        f.write("Breakdown by Structural Category:\n")
        f.write(class_stats.to_string() + "\n\n")
        f.write("Top Performance by Array Type:\n")
        f.write(type_stats.sort_values('Win Rate (%)', ascending=False).to_string() + "\n")
    
    print(f"Detailed report written to {report_file}")

if __name__ == "__main__":
    run_structural_backtest(ticker='NQ')
