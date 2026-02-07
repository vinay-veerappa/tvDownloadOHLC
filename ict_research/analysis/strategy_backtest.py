import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_loader import load_data, slice_trading_days, get_trading_day_data
from config import SESSION_TIMES

def calculate_mae_mfe(ticker='NQ'):
    # Files
    days_file = f'ict_research/data/trading_days_{ticker}.csv'
    arrays_file = f'ict_research/data/pd_arrays_{ticker}.csv'
    
    if not os.path.exists(days_file) or not os.path.exists(arrays_file):
        print("Data files not found. Run pipeline first.")
        return

    print("Loading datasets...")
    df_days = pd.read_csv(days_file)
    df_arrays = pd.read_csv(arrays_file)
    
    # 1. IDENTIFY SETUPS
    # A setup is a day with:
    # - manipulation != "NO_MANIPULATION"
    # - At least one PD Array for that date where in_manipulation_zone is True and respected is True.
    
    print("Identifying setups...")
    # Filter arrays for "Respected in Manipulation Zone"
    respected_arrays = df_arrays[(df_arrays['in_manipulation_zone'] == True) & (df_arrays['respected'] == True)]
    setup_dates = respected_arrays['date'].unique()
    
    # Filter days to only those with setups and non-NO_MANIPULATION
    df_setups = df_days[(df_days['date'].isin(setup_dates)) & (df_days['manipulation'] != "NO_MANIPULATION")].copy()
    
    if df_setups.empty:
        print("No setups found matching criteria.")
        return

    print(f"Found {len(df_setups)} valid setups.")

    # 2. LOAD 1M DATA FOR Granular MAE/MFE
    print("Loading 1m data for precise MAE/MFE...")
    df_1m = load_data(ticker, '1m')
    df_1m = slice_trading_days(df_1m)

    # 3. BACKTEST LOGIC
    # BULLISH_MANIPULATION (London swept low) -> Trade is LONG (expecting reversal up to London High)
    # BEARISH_MANIPULATION (London swept high) -> Trade is SHORT (expecting reversal down to London Low)
    
    results = []
    
    print("Preparing 1m data groups...")
    # Ensure date is string for consistent lookup
    df_1m['date_str'] = df_1m['trading_date'].astype(str)
    day_groups = df_1m.groupby('date_str')

    ny_start = SESSION_TIMES['NY_AM'][0]
    ny_end = SESSION_TIMES['NY_PM'][1]

    print("Calculating metrics for setups...")
    for _, row in tqdm(df_setups.iterrows(), total=len(df_setups)):
        d_str = str(row['date'])
        
        if d_str not in day_groups.groups:
            continue
            
        day_df = day_groups.get_group(d_str)
        
        # NY Session (09:30 - 16:00)
        ny_df = day_df.between_time(ny_start, ny_end)
        
        if ny_df.empty:
            continue
            
        entry_price = ny_df['open'].iloc[0] # 09:30 Open
        
        # Peak excursions during NY
        max_high = ny_df['high'].max()
        min_low = ny_df['low'].min()
        
        manip = row['manipulation']
        if manip == "BULLISH_MANIPULATION": # Trade is LONG (expectation: price goes UP)
            mfe_pts = max_high - entry_price
            mae_pts = entry_price - min_low
        else: # BEARISH_MANIPULATION -> Trade is SHORT (expectation: price goes DOWN)
            mfe_pts = entry_price - min_low
            mae_pts = max_high - entry_price
            
        results.append({
            'date': d_str,
            'manipulation': manip,
            'win': row['manipulation_reversed'],
            'mfe_pts': mfe_pts,
            'mae_pts': mae_pts,
            'rth_gap_pct': row['rth_gap_pct'],
            'gap_fill_25': row['gap_fill_25'],
            'gap_fill_50': row['gap_fill_50'],
            'gap_fill_100': row['gap_fill_100']
        })

    df_results = pd.DataFrame(results)
    
    # 4. REQUIRED OUTPUT
    
    # Summary Table
    print("\n" + "="*50)
    print("CONTEXT-DRIVEN REVERSION BACKTEST SUMMARY")
    print("="*50)
    
    summary = {
        'Total Trades': len(df_results),
        'Win Rate (%)': df_results['win'].mean() * 100,
        'Avg MAE (pts)': df_results['mae_pts'].mean(),
        'Avg MFE (pts)': df_results['mfe_pts'].mean(),
        'Median MAE (pts)': df_results['mae_pts'].median(),
        'Median MFE (pts)': df_results['mfe_pts'].median()
    }
    
    for k, v in summary.items():
        print(f"{k:18}: {v:.2f}")

    # Correlation Analysis
    print("\n--- Correlation Analysis ---")
    # Prompt asks: Does hitting a 'respected' PD array during London significantly increase manipulation_reversed probability?
    # We need to compare setup days (respected) vs all manipulation days.
    
    all_manip_days = df_days[df_days['manipulation'] != "NO_MANIPULATION"]
    base_win_rate = all_manip_days['manipulation_reversed'].mean() * 100
    setup_win_rate = df_results['win'].mean() * 100
    
    print(f"Base Reversal Rate (All Manipulation Days): {base_win_rate:.2f}%")
    print(f"Setup Reversal Rate (Respected PDA Days):   {setup_win_rate:.2f}%")
    print(f"Edge from PDA Respect:                     {setup_win_rate - base_win_rate:+.2f}%")

    # Gap Analysis
    print("\n--- Gap Analysis (Win Rate by Fill level) ---")
    gap_stats = df_results.agg({
        'gap_fill_25': ['mean'],
        'gap_fill_50': ['mean'],
        'gap_fill_100': ['mean']
    }) * 100
    print(gap_stats)
    
    # Analysis based on Gap alignment
    def check_align(row):
        if row['manipulation'] == "BEARISH_MANIPULATION": # Expecting Short
            return "Confirming" if row['rth_gap_pct'] > 0 else "Contradicting"
        else: # BULLISH_MANIPULATION (Expecting Long)
            return "Confirming" if row['rth_gap_pct'] < 0 else "Contradicting"
            
    df_results['gap_alignment'] = df_results.apply(check_align, axis=1)
    align_summary = df_results.groupby('gap_alignment')['win'].agg(['count', 'mean'])
    align_summary['mean'] = align_summary['mean'] * 100
    print("\nWin Rate by Gap Alignment:")
    print(align_summary)

    # Visuals: MFE vs MAE
    os.makedirs('ict_research/plots', exist_ok=True)
    plt.figure(figsize=(10, 6))
    
    # Simple matplotlib scatter
    df_win = df_results[df_results['win'] == True]
    df_loss = df_results[df_results['win'] == False]
    
    plt.scatter(df_win['mae_pts'], df_win['mfe_pts'], color='green', label='Win', alpha=0.6)
    plt.scatter(df_loss['mae_pts'], df_loss['mfe_pts'], color='red', label='Loss', alpha=0.6)
    
    # Add median MAE/MFE lines
    med_mae = df_results['mae_pts'].median()
    med_mfe = df_results['mfe_pts'].median()
    plt.axvline(med_mae, color='gray', linestyle='--', label=f'Med MAE ({med_mae:.1f})')
    plt.axhline(med_mfe, color='gray', linestyle=':', label=f'Med MFE ({med_mfe:.1f})')
    
    plt.title(f'MFE vs MAE Distribution - {ticker} Strategy Setups')
    plt.xlabel('MAE (Points)')
    plt.ylabel('MFE (Points)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    plot_path = f'ict_research/plots/mfe_mae_{ticker}.png'
    plt.savefig(plot_path)
    print(f"\nMAE/MFE scatter plot saved to {plot_path}")
    
    # Histograms
    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    plt.hist(df_results['mae_pts'], bins=30, color='salmon', alpha=0.7)
    plt.title('MAE Distribution (How much heat?)')
    plt.xlabel('Points')
    
    plt.subplot(1, 2, 2)
    plt.hist(df_results['mfe_pts'], bins=30, color='skyblue', alpha=0.7)
    plt.title('MFE Distribution (Profit potential)')
    plt.xlabel('Points')
    
    plt.savefig(f'ict_research/plots/histograms_{ticker}.png')
    
    return df_results

if __name__ == "__main__":
    calculate_mae_mfe(ticker='NQ')
