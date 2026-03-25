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
    """Manual candlestick plotting for performance and flexibility."""
    width = 0.0006 # Bar width in days
    width2 = 0.0001 # Wick width
    
    # Prices
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    times = df.index.to_pydatetime()
    
    # Calculate colors
    colors = ['#089981' if c >= o else '#f23645' for o, c in zip(opens, closes)]
    
    for i in range(len(df)):
        # Body
        t = times[i]
        top = max(opens[i], closes[i])
        bot = min(opens[i], closes[i])
        
        # Ensure body has minimum height for visibility
        if top == bot:
            top += 0.1
            
        rect = patches.Rectangle((t - timedelta(minutes=0.4), bot), 
                                 timedelta(minutes=0.8), top - bot, 
                                 facecolor=colors[i], edgecolor=colors[i], linewidth=0.5)
        ax.add_patch(rect)
        
        # Wicks
        ax.vlines(t, lows[i], highs[i], color=colors[i], linewidth=1)

def run_limit_backtest_with_sl(ticker='NQ', num_charts=10):
    days_file = f'ict_research/data/trading_days_{ticker}.csv'
    arrays_file = f'ict_research/data/pd_arrays_{ticker}.csv'
    
    if not os.path.exists(days_file) or not os.path.exists(arrays_file):
        print("Required data files not found. Run pipeline first.")
        return

    print("Loading data...")
    df_days = pd.read_csv(days_file)
    df_arrays = pd.read_csv(arrays_file)
    
    # Load 1m data
    df_1m = load_data(ticker, '1m')
    df_1m = slice_trading_days(df_1m)
    df_1m['date_str'] = df_1m['trading_date'].astype(str)
    day_groups = df_1m.groupby('date_str')

    # Constants
    SL_BPS = 20 # 20 basis points
    SL_PCT = SL_BPS / 10000.0 # 0.002
    
    ny_start = SESSION_TIMES['NY_AM'][0]
    ny_end = SESSION_TIMES['NY_PM'][1]

    # Filter Potential Setups
    df_setups = df_arrays[
        (df_arrays['in_manipulation_zone'] == True) & 
        (df_arrays['respected'] == True)
    ].copy()
    df_setups = df_setups.merge(df_days[['date', 'manipulation', 'london_high', 'london_low']], on='date')
    
    # Target most recent ones for charts
    df_setups = df_setups.sort_values('date', ascending=False)
    
    results = []
    charts_generated = 0
    os.makedirs('ict_research/visual_guides_v2', exist_ok=True)

    print("Executing Structured Limit Backtest...")
    for _, arr in tqdm(df_setups.iterrows(), total=len(df_setups)):
        d_str = str(arr['date'])
        if d_str not in day_groups.groups: continue
        
        day_df = day_groups.get_group(d_str)
        ny_df = day_df.between_time(ny_start, ny_end)
        if ny_df.empty: continue
        
        # 1. DEFINE ENTRY/SL/TP
        manip = arr['manipulation']
        if manip == 'BULLISH_MANIPULATION': # Sweep Low -> Long
            direction = 'LONG'
            entry_price = arr['high'] # Enter at top of zone
            sl_price = entry_price * (1 - SL_PCT)
            tp_price = arr['london_high']
        elif manip == 'BEARISH_MANIPULATION': # Sweep High -> Short
            direction = 'SHORT'
            entry_price = arr['low'] # Enter at bottom of zone
            sl_price = entry_price * (1 + SL_PCT)
            tp_price = arr['london_low']
        else:
            continue
            
        # 2. FIND ENTRY TIME
        if direction == 'LONG':
            entry_mask = ny_df['low'] <= entry_price
        else:
            entry_mask = ny_df['high'] >= entry_price
            
        if not entry_mask.any(): continue
        
        entry_time = ny_df[entry_mask].index[0]
        post_entry_df = ny_df[ny_df.index >= entry_time]
        
        # 3. SIMULATE TRADE OUTCOME
        # We need to see what happens first: SL, TP, or EOD
        outcome = "EOD"
        exit_time = post_entry_df.index[-1]
        exit_price = post_entry_df['close'].iloc[-1]
        
        # Check for SL/TP on 1m bars
        for t, row in post_entry_df.iterrows():
            if direction == 'LONG':
                if row['low'] <= sl_price:
                    outcome = "SL"
                    exit_time = t
                    exit_price = sl_price
                    break
                if row['high'] >= tp_price:
                    outcome = "TP"
                    exit_time = t
                    exit_price = tp_price
                    break
            else: # SHORT
                if row['high'] >= sl_price:
                    outcome = "SL"
                    exit_time = t
                    exit_price = sl_price
                    break
                if row['low'] <= tp_price:
                    outcome = "TP"
                    exit_time = t
                    exit_price = tp_price
                    break
        
        trade_res = {
            'date': d_str,
            'type': arr['type'],
            'direction': direction,
            'entry': entry_price,
            'sl': sl_price,
            'tp': tp_price,
            'outcome': outcome,
            'exit_time': exit_time
        }
        results.append(trade_res)

        # 4. VISUALIZATION (Limit to 10 charts)
        if charts_generated < num_charts and outcome != "EOD":
            charts_generated += 1
            
            # Use smaller window for candlesticks (08:00 to 16:00)
            chart_df = day_df.between_time("07:00", "16:00")
            
            fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
            ax.set_facecolor('#131722')
            fig.patch.set_facecolor('#131722')
            
            plot_candlesticks(ax, chart_df)
            
            # PDA Rectangle
            pda_color = '#089981' if direction == 'LONG' else '#f23645'
            rect = patches.Rectangle((chart_df.index[0], arr['low']), 
                                     timedelta(hours=24), arr['high'] - arr['low'], 
                                     facecolor=pda_color, alpha=0.15, label=f"15m {arr['type']}")
            ax.add_patch(rect)
            
            # Entry/SL/TP Lines
            ax.axhline(entry_price, color='white', linestyle='-', linewidth=1.5, alpha=0.9, label='ENTRY (Limit)')
            ax.axhline(sl_price, color='#f23645', linestyle='--', linewidth=1.5, alpha=0.9, label=f'SL (20bps: {sl_price:.1f})')
            ax.axhline(tp_price, color='#089981', linestyle='--', linewidth=1.5, alpha=0.9, label='TP (Target)')
            
            # Mark Entry Point
            ax.plot(entry_time, entry_price, 'w*', markersize=15, label='Fills')
            
            # Outcome Label
            outcome_color = '#089981' if outcome == "TP" else '#f23645'
            ax.text(exit_time, exit_price, f" EXIT: {outcome}", color=outcome_color, fontweight='bold', fontsize=12)
            
            # Titles & formatting
            ax.set_title(f"ICT Structured Limit Backtest: {d_str} | {direction} | {outcome}", color='white', fontsize=18, pad=20)
            ax.tick_params(colors='#d1d4dc', labelsize=10)
            ax.grid(color='#2a2e39', alpha=0.5)
            
            # Highlight NY Open
            ny_open_raw = chart_df.between_time("09:30", "09:31").index
            if not ny_open_raw.empty:
                ax.axvline(ny_open_raw[0], color='#4caf50', alpha=0.3, label='NY Open')
            
            ax.legend(facecolor='#1e222d', edgecolor='#d1d4dc', labelcolor='white', loc='upper left')
            
            # Zoom Y-axis to relevant area
            prices = chart_df['close']
            y_min = min(prices.min(), sl_price, entry_price, tp_price) * 0.9995
            y_max = max(prices.max(), sl_price, entry_price, tp_price) * 1.0005
            ax.set_ylim(y_min, y_max)
            
            chart_file = f'ict_research/visual_guides_v2/trade_{charts_generated}_{d_str}_{outcome}.png'
            plt.savefig(chart_file, bbox_inches='tight')
            plt.close()

    # Final Stats
    df_res = pd.DataFrame(results)
    print("\n" + "="*50)
    print("STRUCTURED LIMIT BACKTEST (20 BPS SL)")
    print("="*50)
    win_rate = (df_res['outcome'] == 'TP').mean() * 100
    sl_rate = (df_res['outcome'] == 'SL').mean() * 100
    print(f"Total Limit Orders Filled: {len(df_res)}")
    print(f"Target Hit Rate (TP):      {win_rate:.2f}%")
    print(f"Stop Out Rate (SL):       {sl_rate:.2f}%")
    print(f"EOD/Other Exit Rate:      {(100 - win_rate - sl_rate):.2f}%")
    print("="*50)
    print(f"Check ict_research/visual_guides_v2/ for charts.")

if __name__ == "__main__":
    run_limit_backtest_with_sl(ticker='NQ')
