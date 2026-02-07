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

def resample_to_15m(df_1m):
    """Resamples 1m OHLCV to 15m."""
    if df_1m.empty: return df_1m
    logic = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    # Standard 15m bars (00, 15, 30, 45)
    return df_1m.resample('15min').apply(logic).dropna()

def plot_candlesticks_15m(ax, df):
    """Visualizes 15m candlesticks."""
    colors = ['#089981' if c >= o else '#f23645' for o, c in zip(df['open'], df['close'])]
    width_td = timedelta(minutes=12) # 15m bar width
    wick_td = timedelta(minutes=1)
    
    for i in range(len(df)):
        t = df.index[i]
        o, h, l, c = df.iloc[i][['open', 'high', 'low', 'close']]
        top, bot = max(o, c), min(o, c)
        if top == bot: top += 0.05
        
        # Body
        ax.add_patch(patches.Rectangle((t - width_td/2, bot), width_td, top - bot, 
                                      facecolor=colors[i], edgecolor=colors[i], linewidth=0.5, alpha=0.9))
        # Wick
        ax.vlines(t, l, h, color=colors[i], linewidth=1.2, alpha=0.8)

def run_ict_pro_backtest(ticker='NQ', num_charts=10):
    days_file = f'ict_research/data/trading_days_{ticker}.csv'
    arrays_file = f'ict_research/data/pd_arrays_{ticker}.csv'
    
    if not os.path.exists(days_file) or not os.path.exists(arrays_file):
        print("Required data files not found. Run pipeline first.")
        return

    print("Loading data for 15m ICT Professional Backtest...")
    df_days = pd.read_csv(days_file)
    df_arrays = pd.read_csv(arrays_file)
    
    # 1. LOAD 1M DATA FOR Granular Execution, then resample for Viz
    df_1m = load_data(ticker, '1m')
    df_1m = slice_trading_days(df_1m)
    df_1m['date_str'] = df_1m['trading_date'].astype(str)
    day_groups = df_1m.groupby('date_str')

    # Constants
    SL_BPS = 20
    SL_PCT = SL_BPS / 10000.0  # 0.002
    MIN_RR = 1.5
    
    ny_start_time = "09:30"
    ny_end_time = "16:00"

    results = []
    charts_count = 0
    os.makedirs('ict_research/visual_guides_15m', exist_ok=True)

    # Filter for manipulation days
    manip_days = df_days[df_days['manipulation'] != "NO_MANIPULATION"]
    
    print(f"Simulating trades on {len(manip_days)} potential days...")
    
    for _, day in tqdm(manip_days.iterrows(), total=len(manip_days)):
        d_str = str(day['date'])
        if d_str not in day_groups.groups: continue
        
        day_1m = day_groups.get_group(d_str)
        # Use 1m for fill/sl accuracy, but viz will use 15m
        ny_1m = day_1m.between_time(ny_start_time, ny_end_time)
        if ny_1m.empty: continue
        
        # --- Institutional Bias Check ---
        manip = day['manipulation']
        if manip == 'BULLISH_MANIPULATION': # Swept Low -> Target London High
            direction = 'LONG'
            target_price = day['london_high']
        else: # BEARISH_MANIPULATION -> Target London Low
            direction = 'SHORT'
            target_price = day['london_low']
            
        if pd.isna(target_price): continue
            
        # --- Array Selection ---
        # Only use 15m PDAs that were created during manipulation leg
        # And haven't been 'run over' yet.
        candidate_arrays = df_arrays[
            (df_arrays['date'] == d_str) & 
            (df_arrays['in_manipulation_zone'] == True)
        ]
        if candidate_arrays.empty: continue
        
        # Pick the FIRST PDA created (Origin of Displacement)
        best_arr = candidate_arrays.sort_values('time', ascending=True).iloc[0]
        
        if direction == 'LONG':
            entry_price = best_arr['high'] # Enter at ceiling
            stop_price = entry_price * (1 - SL_PCT)
        else:
            entry_price = best_arr['low'] # Enter at floor
            stop_price = entry_price * (1 + SL_PCT)

        # R:R Check
        risk = abs(entry_price - stop_price)
        reward = abs(target_price - entry_price)
        if risk == 0 or (reward / risk) < MIN_RR: continue

        # --- Causality Execution ---
        outcome = None
        fill_time = None
        exit_time = None
        exit_price = None
        
        # Walk through 1m bars starting at 09:30
        for t, row in ny_1m.iterrows():
            if outcome is None:
                # 1. Did we hit Target before Fill?
                if direction == 'LONG' and row['high'] >= target_price:
                    outcome = 'VOID_TARGET_HIT_FIRST'
                    break
                if direction == 'SHORT' and row['low'] <= target_price:
                    outcome = 'VOID_TARGET_HIT_FIRST'
                    break
                    
                # 2. Check for Fill at Limit
                is_fill = False
                if direction == 'LONG' and row['low'] <= entry_price: is_fill = True
                elif direction == 'SHORT' and row['high'] >= entry_price: is_fill = True
                
                if is_fill:
                    outcome = 'IN_TRADE'
                    fill_time = t
                    continue
            
            if outcome == 'IN_TRADE':
                if direction == 'LONG':
                    if row['low'] <= stop_price:
                        outcome = 'STOP'
                        exit_time, exit_price = t, stop_price
                        break
                    elif row['high'] >= target_price:
                        outcome = 'TARGET'
                        exit_time, exit_price = t, target_price
                        break
                else: # SHORT
                    if row['high'] >= stop_price:
                        outcome = 'STOP'
                        exit_time, exit_price = t, stop_price
                        break
                    elif row['low'] <= target_price:
                        outcome = 'TARGET'
                        exit_time, exit_price = t, target_price
                        break
        
        if outcome == 'IN_TRADE':
            outcome = 'EOD'
            exit_time = ny_1m.index[-1]
            exit_price = ny_1m['close'].iloc[-1]

        # --- Record & Chart ---
        if fill_time:
            results.append({
                'date': d_str,
                'outcome': outcome,
                'rr': reward/risk,
                'dir': direction
            })
            
            if charts_count < num_charts and outcome != 'VOID_TARGET_HIT_FIRST':
                charts_count += 1
                
                # 15m Resampling for Visualization
                day_15m = resample_to_15m(day_1m).between_time("07:00", "16:00")
                
                fig, ax = plt.subplots(figsize=(15, 8), dpi=110)
                ax.set_facecolor('#131722') # TradingView Grey
                fig.patch.set_facecolor('#131722')
                
                plot_candlesticks_15m(ax, day_15m)
                
                # Highlight PDA
                arr_color = '#00ff88' if direction == 'LONG' else '#ff4444'
                pda_patch = patches.Rectangle((day_15m.index[0], best_arr['low']), 
                                             timedelta(hours=24), best_arr['high'] - best_arr['low'], 
                                             facecolor=arr_color, alpha=0.12, label=f"15m {best_arr['type']}")
                ax.add_patch(pda_patch)
                
                # Lines
                ax.axhline(entry_price, color='white', linestyle='-', linewidth=1, alpha=0.7, label='Entry Limit')
                ax.axhline(target_price, color='#089981', linestyle='--', linewidth=1.5, alpha=0.8, label='Target (Liq)')
                ax.axhline(stop_price, color='#f23645', linestyle='--', linewidth=1.5, alpha=0.8, label='Stop (20bps)')
                
                # Entry/Exit Markers
                ax.scatter(fill_time, entry_price, marker='*', s=250, color='gold', zorder=10, label='Filled')
                if exit_time:
                    ecol = '#089981' if outcome == 'TARGET' else '#f23645'
                    ax.scatter(exit_time, exit_price, marker='X', s=200, color=ecol, zorder=10)
                
                # Formatting X-axis
                import matplotlib.dates as mdates
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
                ax.tick_params(colors='#d1d4dc', labelsize=10)
                # Ensure Y axis doesn't use scientific notation
                ax.yaxis.get_major_formatter().set_useOffset(False)
                ax.yaxis.get_major_formatter().set_scientific(False)
                
                # Styling
                ax.set_title(f"ICT 15m Chart | {d_str} | {direction} | {outcome} | RR: {reward/risk:.2f}", color='white', fontsize=16)
                ax.tick_params(colors='#d1d4dc')
                ax.grid(color='#2a2e39', alpha=0.3)
                
                # Zoom axis
                buff = (day_15m['high'].max() - day_15m['low'].min()) * 0.1
                ax.set_ylim(min(day_15m['low'].min(), stop_price, target_price) - buff, 
                           max(day_15m['high'].max(), entry_price, target_price) + buff)
                
                ax.legend(facecolor='#1e222d', edgecolor='#d1d4dc', labelcolor='white', loc='upper left')
                
                plt.savefig(f'ict_research/visual_guides_15m/study_{charts_count}_{d_str}_{outcome}.png', bbox_inches='tight')
                plt.close()

    # Reporting
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        tp = len(df_res[df_res['outcome'] == 'TARGET'])
        sl = len(df_res[df_res['outcome'] == 'STOP'])
        print(f"\n✅ ICT 15M BACKTEST COMPLETE")
        print(f"Total Trades Filled: {len(df_res)}")
        print(f"Win Rate (TP):      {tp/len(df_res)*100:.2f}%")
        print(f"Loss Rate (SL):     {sl/len(df_res)*100:.2f}%")
        print(f"Average RR:         {df_res[df_res['outcome']=='TARGET']['rr'].mean():.2f}:1")
        print(f"Profit Factor:      {(tp * df_res[df_res['outcome']=='TARGET']['rr'].mean()) / sl:.2f}")

if __name__ == "__main__":
    run_ict_pro_backtest(ticker='NQ')
