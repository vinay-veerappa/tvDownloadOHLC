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
    return df_1m.resample('15min').apply(logic).dropna()

def plot_candlesticks_15m(ax, df):
    """Visualizes 15m candlesticks."""
    colors = ['#089981' if c >= o else '#f23645' for o, c in zip(df['open'], df['close'])]
    width_td = timedelta(minutes=12) 
    
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

def run_ict_definitive_backtest(ticker='NQ', num_charts=10):
    days_file = f'ict_research/data/trading_days_{ticker}.csv'
    arrays_file = f'ict_research/data/pd_arrays_{ticker}.csv'
    
    if not os.path.exists(days_file) or not os.path.exists(arrays_file):
        print("Required data files not found. Run pipeline first.")
        return

    print(f"Loading data for Definitive ICT Strategy Backtest ({ticker})...")
    df_days = pd.read_csv(days_file)
    df_arrays = pd.read_csv(arrays_file)
    
    # LOAD 1M DATA
    df_1m = load_data(ticker, '1m')
    df_1m = slice_trading_days(df_1m)
    df_1m['date_str'] = df_1m['trading_date'].astype(str)
    day_groups = df_1m.groupby('date_str')

    # Constants
    SL_BPS = 20
    SL_PCT = SL_BPS / 10000.0  
    MIN_RR = 2.0 # Spec says "minimum 2:1 R:R"
    
    ny_start_time = "09:30"
    ny_end_time = "16:00"

    results = []
    charts_count = 0
    viz_dir = 'ict_research/visual_guides_definitive'
    os.makedirs(viz_dir, exist_ok=True)

    # Filter for manipulation days
    manip_days = df_days[df_days['manipulation'] != "NO_MANIPULATION"]
    
    print(f"Simulating trades on {len(manip_days)} potential days...")
    
    for _, day in tqdm(manip_days.iterrows(), total=len(manip_days)):
        d_str = str(day['date'])
        if d_str not in day_groups.groups: continue
        
        day_1m = day_groups.get_group(d_str)
        # 09:30 to 16:00
        ny_1m = day_1m.between_time(ny_start_time, ny_end_time)
        if ny_1m.empty: continue
        
        # --- Institutional Bias Check ---
        manip = day['manipulation']
        if manip == 'BULLISH_MANIPULATION': # Swept Low -> Expect up
            direction = 'LONG'
            # Target Selection
            target_price = day['london_high']
        else: # BEARISH_MANIPULATION -> Expect down
            direction = 'SHORT'
            target_price = day['london_low']
            
        if pd.isna(target_price): continue
            
        # --- NY Position Filter ---
        # "when NY opens on the reversal side of London Mid"
        ny_pos = day['ny_position']
        if direction == 'LONG': # Expecting upward expansion
             if ny_pos != 'ABOVE_LONDON_MID': continue
        else: # Expecting downward expansion
             if ny_pos != 'BELOW_LONDON_MID': continue

        # "Pick the earliest displacement PDA formed during London in the manipulation zone"
        candidate_arrays = df_arrays[
            (df_arrays['date'] == d_str) & 
            (df_arrays['in_manipulation_zone'] == True) &
            (~df_arrays['type'].isin(['SWING_H', 'SWING_L']))
        ]
        if candidate_arrays.empty: continue
        
        # Pick the FIRST PDA (Origin of Displacement)
        best_arr = candidate_arrays.sort_values('time', ascending=True).iloc[0]
        
        # Entry Price is PDA Midpoint
        entry_price = best_arr['midpoint']
        
        if direction == 'LONG':
            stop_price = entry_price * (1 - SL_PCT)
        else:
            stop_price = entry_price * (1 + SL_PCT)

        # RR Check & Target Refinement
        risk = abs(entry_price - stop_price)
        reward = abs(target_price - entry_price)
        rr = reward / risk if risk > 0 else 0
        
        # Fallback to PDH/PDL if London Extreme doesn't give enough RR
        if rr < MIN_RR:
            if direction == 'LONG':
                if not pd.isna(day['prev_day_high']) and day['prev_day_high'] > entry_price:
                    target_price = day['prev_day_high']
            else:
                if not pd.isna(day['prev_day_low']) and day['prev_day_low'] < entry_price:
                    target_price = day['prev_day_low']
            
            reward = abs(target_price - entry_price)
            rr = reward / risk if risk > 0 else 0

        if rr < MIN_RR: continue

        # --- Causality Execution (1m) ---
        outcome = None
        fill_time = None
        exit_time = None
        exit_price = None
        
        for t, row in ny_1m.iterrows():
            if outcome is None:
                # 1. Void if Target hit before Fill
                if direction == 'LONG' and row['high'] >= target_price:
                    outcome = 'VOID_TARGET_HIT_FIRST'
                    break
                if direction == 'SHORT' and row['low'] <= target_price:
                    outcome = 'VOID_TARGET_HIT_FIRST'
                    break
                    
                # 2. Check Fill
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
                'rr': rr,
                'dir': direction,
                'pda_type': best_arr['type']
            })
            
            if charts_count < num_charts and outcome != 'VOID_TARGET_HIT_FIRST':
                charts_count += 1
                
                day_15m = resample_to_15m(day_1m).between_time("07:00", "16:00")
                
                fig, ax = plt.subplots(figsize=(15, 8), dpi=110)
                ax.set_facecolor('#131722')
                fig.patch.set_facecolor('#131722')
                
                plot_candlesticks_15m(ax, day_15m)
                
                # Highlight PDA
                arr_color = '#00ff88' if direction == 'LONG' else '#ff4444'
                pda_patch = patches.Rectangle((day_15m.index[0], best_arr['low']), 
                                             timedelta(hours=24), best_arr['high'] - best_arr['low'], 
                                             facecolor=arr_color, alpha=0.15, label=f"15m {best_arr['type']}")
                ax.add_patch(pda_patch)
                
                # Markers
                ax.axhline(entry_price, color='white', linestyle='-', linewidth=1, alpha=0.9, label='Midpoint Entry')
                ax.axhline(target_price, color='#089981', linestyle='--', linewidth=1.5, alpha=0.9, label='Target')
                ax.axhline(stop_price, color='#f23645', linestyle='--', linewidth=1.5, alpha=0.9, label='Stop (20bps)')
                
                ax.scatter(fill_time, entry_price, marker='*', s=300, color='gold', zorder=10, label='Filled')
                if exit_time:
                    ecol = '#089981' if outcome == 'TARGET' else '#f23645'
                    ax.scatter(exit_time, exit_price, marker='X', s=250, color=ecol, zorder=10)
                
                # X-axis
                import matplotlib.dates as mdates
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
                ax.tick_params(colors='#d1d4dc', labelsize=10)
                ax.yaxis.get_major_formatter().set_useOffset(False)
                ax.yaxis.get_major_formatter().set_scientific(False)
                
                ax.set_title(f"ICT Definitive Strategy | {d_str} | {direction} | {outcome} | RR: {rr:.2f}", color='white', fontsize=16)
                ax.grid(color='#2a2e39', alpha=0.3)
                
                # Zoom
                buff = (day_15m['high'].max() - day_15m['low'].min()) * 0.1
                ax.set_ylim(min(day_15m['low'].min(), stop_price, target_price) - buff, 
                           max(day_15m['high'].max(), entry_price, target_price) + buff)
                
                ax.legend(facecolor='#1e222d', edgecolor='#d1d4dc', labelcolor='white', loc='upper left')
                
                plt.savefig(f'{viz_dir}/trade_{charts_count}_{d_str}_{outcome}.png', bbox_inches='tight')
                plt.close()

    # Final Report
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        total = len(df_res)
        tp = len(df_res[df_res['outcome'] == 'TARGET'])
        sl = len(df_res[df_res['outcome'] == 'STOP'])
        eod = len(df_res[df_res['outcome'] == 'EOD'])
        
        print(f"\n==========================================")
        print(f"📊 DEFINITIVE ICT STRATEGY REPORT: {ticker}")
        print(f"==========================================")
        print(f"Total Trades Filled:   {total}")
        print(f"Win Rate (Target):     {tp/total*100:.2f}%")
        print(f"Loss Rate (Stop):       {sl/total*100:.2f}%")
        print(f"EOD/Other:             {eod/total*100:.2f}%")
        print(f"Average RR (Wins):     {df_res[df_res['outcome']=='TARGET']['rr'].mean():.2f}:1")
        
        if sl > 0:
            profit_factor = (tp * df_res[df_res['outcome']=='TARGET']['rr'].mean()) / sl
            print(f"Profit Factor:         {profit_factor:.2f}")
        
        print(f"\nBy PDA Type:")
        print(df_res.groupby(['pda_type', 'outcome']).size().unstack(fill_value=0))
        print(f"==========================================\n")

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else 'NQ'
    run_ict_definitive_backtest(ticker=ticker)
