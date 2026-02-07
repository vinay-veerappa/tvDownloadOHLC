import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import sys
from tqdm import tqdm
from datetime import datetime, timedelta

# Add parent dir to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_loader import load_data, slice_trading_days
from config import SESSION_TIMES

def plot_candlesticks(ax, df):
    """Refined candlestick plotting for ICT Visualization."""
    # body: center at date, width 0.8 min
    colors = ['#089981' if c >= o else '#f23645' for o, c in zip(df['open'], df['close'])]
    for i in range(len(df)):
        t = df.index[i]
        o, h, l, c = df.iloc[i][['open', 'high', 'low', 'close']]
        # Body
        top, bot = max(o, c), min(o, c)
        if top == bot: top += 0.05
        ax.add_patch(patches.Rectangle((t - timedelta(seconds=25), bot), 
                                      timedelta(seconds=50), top - bot, 
                                      facecolor=colors[i], edgecolor=colors[i], linewidth=0.5))
        # Wick
        ax.vlines(t, l, h, color=colors[i], linewidth=0.8)

def run_institutional_backtest(ticker='NQ', num_charts=10):
    days_file = f'ict_research/data/trading_days_{ticker}.csv'
    arrays_file = f'ict_research/data/pd_arrays_{ticker}.csv'
    
    if not os.path.exists(days_file) or not os.path.exists(arrays_file):
        print("Required data files not found. Run pipeline first.")
        return

    print("Loading data for Institutional Backtest...")
    df_days = pd.read_csv(days_file)
    df_arrays = pd.read_csv(arrays_file)
    
    # 1. LOAD 1M DATA FOR Granular Execution
    df_1m = load_data(ticker, '1m')
    df_1m = slice_trading_days(df_1m)
    df_1m['date_str'] = df_1m['trading_date'].astype(str)
    day_groups = df_1m.groupby('date_str')

    # Constants
    SL_BPS = 20
    SL_PCT = SL_BPS / 10000.0  # 0.002
    
    ny_start_time = SESSION_TIMES['NY_AM'][0] # 09:30
    ny_end_time = SESSION_TIMES['NY_PM'][1]   # 16:00

    results = []
    charts_count = 0
    os.makedirs('ict_research/visual_guides_v3_ict', exist_ok=True)

    # Filter for manipulation days
    manip_days = df_days[df_days['manipulation'] != "NO_MANIPULATION"]
    
    print(f"Simulating trades on {len(manip_days)} manipulation days...")
    
    for _, day in tqdm(manip_days.iterrows(), total=len(manip_days)):
        d_str = str(day['date'])
        if d_str not in day_groups.groups: continue
        
        day_df = day_groups.get_group(d_str)
        # Full NY period for check
        ny_df = day_df.between_time(ny_start_time, ny_end_time)
        if ny_df.empty: continue
        
        # --- ICT Logic Setup ---
        # Bias/Direction
        manip = day['manipulation']
        if manip == 'BULLISH_MANIPULATION': # Swept Low -> Look for Long
            direction = 'LONG'
            target_price = day['london_high']
            entry_side = 'high' # Entry at top of PDA
        else: # BEARISH_MANIPULATION -> Look for Short
            direction = 'SHORT'
            target_price = day['london_low']
            entry_side = 'low' # Entry at bottom of PDA
            
        if pd.isna(target_price): continue
            
        # Find all valid 15m PDAs in the manipulation zone for this day
        # Note: We do NOT check if they were "respected" in advance
        candidate_arrays = df_arrays[
            (df_arrays['date'] == d_str) & 
            (df_arrays['in_manipulation_zone'] == True)
        ]
        
        if candidate_arrays.empty: continue
        
        # PICK THE BEST ARRAY (Unbiased)
        # Logic: Pick the array that offers best R:R or most extreme.
        # For Short: Pick Highest PDA. For Long: Pick Lowest PDA.
        if direction == 'SHORT':
            best_arr = candidate_arrays.sort_values('high', ascending=False).iloc[0]
            entry_price = best_arr['low'] # Limit at bottom of bearish block
            stop_price = entry_price * (1 + SL_PCT)
        else:
            best_arr = candidate_arrays.sort_values('low', ascending=True).iloc[0]
            entry_price = best_arr['high'] # Limit at top of bullish block
            stop_price = entry_price * (1 - SL_PCT)

        # --- Simulation ---
        trade_outcome = None
        fill_time = None
        exit_time = None
        exit_price = None
        
        # Iterate bar by bar to respect causality
        for t, row in ny_df.iterrows():
            # 1. Check if Target hit before Fill
            if trade_outcome is None:
                if direction == 'LONG' and row['high'] >= target_price:
                    trade_outcome = 'VOID_TARGET_FIRST'
                    break
                if direction == 'SHORT' and row['low'] <= target_price:
                    trade_outcome = 'VOID_TARGET_FIRST'
                    break
                    
            # 2. Check for Fill
            if trade_outcome is None:
                is_fill = False
                if direction == 'LONG' and row['low'] <= entry_price:
                    is_fill = True
                elif direction == 'SHORT' and row['high'] >= entry_price:
                    is_fill = True
                    
                if is_fill:
                    trade_outcome = 'IN_TRADE'
                    fill_time = t
                    continue
                    
            # 3. If in trade, check for SL or TP
            if trade_outcome == 'IN_TRADE':
                if direction == 'LONG':
                    if row['low'] <= stop_price:
                        trade_outcome = 'STOP'
                        exit_time, exit_price = t, stop_price
                        break
                    elif row['high'] >= target_price:
                        trade_outcome = 'TARGET'
                        exit_time, exit_price = t, target_price
                        break
                else: # SHORT
                    if row['high'] >= stop_price:
                        trade_outcome = 'STOP'
                        exit_time, exit_price = t, stop_price
                        break
                    elif row['low'] <= target_price:
                        trade_outcome = 'TARGET'
                        exit_time, exit_price = t, target_price
                        break
        
        # EOD Handler
        if trade_outcome == 'IN_TRADE':
            trade_outcome = 'EOD'
            exit_time, exit_price = ny_df.index[-1], ny_df['close'].iloc[-1]

        # Log Result
        if fill_time or trade_outcome == 'VOID_TARGET_FIRST':
            results.append({
                'date': d_str,
                'direction': direction,
                'pda_type': best_arr['type'],
                'outcome': trade_outcome,
                'entry': entry_price,
                'tp': target_price,
                'sl': stop_price
            })

            # --- Visual Study ---
            if charts_count < num_charts and fill_time and trade_outcome != 'EOD':
                charts_count += 1
                
                chart_df = day_df.between_time("08:00", "16:00")
                fig, ax = plt.subplots(figsize=(16, 10), dpi=120)
                ax.set_facecolor('#131722')
                fig.patch.set_facecolor('#131722')
                
                plot_candlesticks(ax, chart_df)
                
                # Draw the Chosen 15m PDA
                arr_color = '#089981' if direction == 'LONG' else '#f23645'
                pda_rect = patches.Rectangle((chart_df.index[0], best_arr['low']), 
                                            timedelta(hours=24), best_arr['high'] - best_arr['low'], 
                                            facecolor=arr_color, alpha=0.1, label=f"15m {best_arr['type']}")
                ax.add_patch(pda_rect)
                
                # Lines
                ax.axhline(entry_price, color='white', linestyle='-', linewidth=1.2, alpha=0.8, label=f'ENTRY {entry_price:.1f}')
                ax.axhline(target_price, color='#089981', linestyle='--', linewidth=1.2, alpha=0.8, label=f'TP {target_price:.1f}')
                ax.axhline(stop_price, color='#f23645', linestyle='--', linewidth=1.2, alpha=0.8, label=f'SL {stop_price:.1f}')
                
                # Annotate entry
                ax.scatter(fill_time, entry_price, marker='*', s=300, color='gold', zorder=5, edgecolors='black', label='Limit Filled')
                
                # Styling
                ax.set_title(f"ICT Strategy Study | {d_str} | {direction} | {trade_outcome}", color='white', fontsize=16)
                ax.tick_params(colors='#d1d4dc', labelsize=10)
                ax.grid(color='#2a2e39', alpha=0.3)
                
                # Focus Y axis
                all_important = [entry_price, stop_price, target_price]
                y_min = min(chart_df['low'].min(), min(all_important)) * 0.999
                y_max = max(chart_df['high'].max(), max(all_important)) * 1.001
                ax.set_ylim(y_min, y_max)
                
                plt.legend(facecolor='#1e222d', edgecolor='#d1d4dc', labelcolor='white')
                
                fname = f'ict_research/visual_guides_v3_ict/study_{charts_count}_{d_str}_{trade_outcome}.png'
                plt.savefig(fname, bbox_inches='tight')
                plt.close()

    # Final Report
    df_res = pd.DataFrame(results)
    if df_res.empty: return
    
    filled = df_res[df_res['outcome'].isin(['TARGET', 'STOP', 'EOD'])]
    voided = df_res[df_res['outcome'] == 'VOID_TARGET_FIRST']
    
    print("\n" + "!"*60)
    print("INSTITUTIONAL ICT REVERSION REPORT".center(60))
    print("!"*60)
    print(f"Total Theoretical Setups:    {len(df_res)}")
    print(f"Void (Target hit first):     {len(voided)} ({len(voided)/len(df_res)*100:.1f}%)")
    print(f"Filled (Limit Entry):        {len(filled)}")
    
    if len(filled) > 0:
        win_count = len(filled[filled['outcome']=='TARGET'])
        loss_count = len(filled[filled['outcome']=='STOP'])
        
        # Calculate Average R:R
        win_trades = filled[filled['outcome']=='TARGET'].copy()
        win_trades['r_multiple'] = (abs(win_trades['tp'] - win_trades['entry'])) / (abs(win_trades['sl'] - win_trades['entry']))
        avg_rr = win_trades['r_multiple'].mean()
        
        profit_factor = (win_count * avg_rr) / loss_count if loss_count > 0 else float('inf')
        
        print(f"  - Target Reached:          {win_count} ({win_count/len(filled)*100:.2f}%)")
        print(f"  - Stopped Out (20bps):     {loss_count} ({loss_count/len(filled)*100:.2f}%)")
        print(f"  - EOD Carry:               {len(filled[filled['outcome']=='EOD'])}")
        print(f"  - Avg R:R on Wins:         {avg_rr:.2f}:1")
        print(f"  - Estimated Profit Factor: {profit_factor:.2f}")
        
    print("!"*60)
    print(f"Charts saved to ict_research/visual_guides_v3_ict/")

if __name__ == "__main__":
    run_institutional_backtest(ticker='NQ')
