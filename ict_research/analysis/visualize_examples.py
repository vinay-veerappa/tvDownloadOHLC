import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import sys
from datetime import datetime, timedelta

# Add parent dir to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_loader import load_data, slice_trading_days
from config import SESSION_TIMES

def create_example_charts(ticker='NQ', num_examples=10):
    days_file = f'ict_research/data/trading_days_{ticker}.csv'
    arrays_file = f'ict_research/data/pd_arrays_{ticker}.csv'
    
    if not os.path.exists(days_file) or not os.path.exists(arrays_file):
        print("Required data files not found. Run pipeline first.")
        return

    print("Loading data for visualization...")
    df_days = pd.read_csv(days_file)
    df_arrays = pd.read_csv(arrays_file)
    
    # Select diverse successful examples
    # 5 Bullish Reversals, 5 Bearish Reversals
    bull_revs = df_days[(df_days['manipulation'] == 'BULLISH_MANIPULATION') & (df_days['manipulation_reversed'] == True)].tail(20)
    bear_revs = df_days[(df_days['manipulation'] == 'BEARISH_MANIPULATION') & (df_days['manipulation_reversed'] == True)].tail(20)
    
    examples = pd.concat([bull_revs.sample(min(5, len(bull_revs))), 
                         bear_revs.sample(min(5, len(bear_revs)))]).sort_values('date')
    
    print(f"Generating {len(examples)} visualization charts...")
    
    # Load 1m data for the chart background
    df_1m = load_data(ticker, '1m')
    df_1m = slice_trading_days(df_1m)
    df_1m['date_str'] = df_1m['trading_date'].astype(str)
    day_groups = df_1m.groupby('date_str')

    os.makedirs('ict_research/visual_guides', exist_ok=True)

    for i, (_, day_row) in enumerate(examples.iterrows()):
        d_str = str(day_row['date'])
        if d_str not in day_groups.groups:
            continue
            
        day_df = day_groups.get_group(d_str).copy()
        day_arrays = df_arrays[(df_arrays['date'] == d_str) & (df_arrays['in_manipulation_zone'] == True) & (df_arrays['respected'] == True)]
        
        if day_arrays.empty:
            continue
            
        # Select the best PDA for display (highest win probability in backtest: Swing or OB)
        best_pda = day_arrays.sort_values('type', ascending=False).iloc[0]
        
        # Setup Figure
        fig, ax = plt.subplots(figsize=(15, 8), dpi=100)
        ax.set_facecolor('#131722') # TradingView Dark Theme
        fig.patch.set_facecolor('#131722')
        
        # Plot Price Action
        # Using a simple line chart for the 1m data but with thicker line for visibility
        ax.plot(day_df.index, day_df['close'], color='#d1d4dc', linewidth=1, alpha=0.8, label='Price')
        
        # Highlight Sessions
        asia_start = SESSION_TIMES['ASIA'][0]
        asia_end = SESSION_TIMES['ASIA'][1]
        london_start = SESSION_TIMES['LONDON'][0]
        london_end = SESSION_TIMES['LONDON'][1]
        ny_start = SESSION_TIMES['NY_AM'][0]
        ny_end = SESSION_TIMES['NY_PM'][1]
        
        # Add Session Background Translucency
        ax.axvspan(day_df.between_time(asia_start, asia_end).index.min(), 
                   day_df.between_time(asia_start, asia_end).index.max(), 
                   color='#2962ff', alpha=0.05, label='Asia')
        
        ax.axvspan(day_df.between_time(london_start, london_end).index.min(), 
                   day_df.between_time(london_start, london_end).index.max(), 
                   color='#ff9800', alpha=0.05, label='London')
        
        ax.axvspan(day_df.between_time(ny_start, ny_end).index.min(), 
                   day_df.between_time(ny_start, ny_end).index.max(), 
                   color='#4caf50', alpha=0.05, label='NY')

        # Draw Asia High/Low (The Liquidity Zones)
        asia_h = day_row['asia_high']
        asia_l = day_row['asia_low']
        ax.axhline(asia_h, color='#f23645', linestyle='--', linewidth=1, alpha=0.5)
        ax.axhline(asia_l, color='#089981', linestyle='--', linewidth=1, alpha=0.5)
        ax.text(day_df.index[10], asia_h, ' Asia High', color='#f23645', verticalalignment='bottom', fontweight='bold')
        ax.text(day_df.index[10], asia_l, ' Asia Low', color='#089981', verticalalignment='top', fontweight='bold')

        # Draw the Entry PDA Zone
        pda_color = '#089981' if 'BULL' in best_pda['type'] or 'L' in best_pda['type'] else '#f23645'
        rect = patches.Rectangle((day_df.index[0], best_pda['low']), 
                                  timedelta(hours=24), best_pda['high'] - best_pda['low'], 
                                  linewidth=0, facecolor=pda_color, alpha=0.25, label=f"PDA: {best_pda['type']}")
        ax.add_patch(rect)
        
        # Annotate Entry, SL, TP
        entry_price = best_pda['high'] if day_row['manipulation'] == 'BULLISH_MANIPULATION' else best_pda['low']
        
        # Hypothetical SL/TP based on structural logic (0.3% SL, London High/Low as TP)
        sl_dist = entry_price * 0.003
        if day_row['manipulation'] == 'BULLISH_MANIPULATION': # Long
            sl_price = entry_price - sl_dist
            tp_price = day_row['london_high']
            direction_label = "BULLISH REVERSAL"
            entry_marker = '^'
            entry_color = '#089981'
        else: # Bearish Reversal
            sl_price = entry_price + sl_dist
            tp_price = day_row['london_low']
            direction_label = "BEARISH REVERSAL"
            entry_marker = 'v'
            entry_color = '#f23645'

        # Find the specific entry point (first touch in NY)
        ny_df = day_df.between_time(ny_start, ny_end)
        if day_row['manipulation'] == 'BULLISH_MANIPULATION':
            touch_idx = ny_df[ny_df['low'] <= entry_price].index
        else:
            touch_idx = ny_df[ny_df['high'] >= entry_price].index
            
        if len(touch_idx) > 0:
            actual_entry_time = touch_idx[0]
            ax.plot(actual_entry_time, entry_price, entry_marker, markersize=12, color=entry_color, label='Entry Trigger')
            ax.annotate('ENTRY', xy=(actual_entry_time, entry_price), xytext=(20, 20),
                        textcoords='offset points', color='white', fontweight='bold',
                        arrowprops=dict(arrowstyle='->', color='white'))

        # Final Formatting
        ax.set_title(f"ICT Strategy Study: {d_str} | {direction_label} | {best_pda['type']}", color='white', fontsize=16, pad=20)
        ax.tick_params(colors='#d1d4dc', which='both')
        ax.grid(color='#2a2e39', alpha=0.5)
        
        # Limit X-axis to the trading day
        ax.set_xlim(day_df.index.min(), day_df.index.max())
        
        # Legend
        leg = ax.legend(facecolor='#1e222d', edgecolor='#d1d4dc', labelcolor='white')
        
        file_name = f'ict_research/visual_guides/example_{i+1}_{d_str}.png'
        plt.savefig(file_name, bbox_inches='tight')
        plt.close()
        
    print(f"Check ict_research/visual_guides/ for the generated charts.")

if __name__ == "__main__":
    create_example_charts(ticker='NQ')
