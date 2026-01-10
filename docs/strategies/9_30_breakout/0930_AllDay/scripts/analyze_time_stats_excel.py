
"""
Granular Time Statistics (EXCEL)
================================
Complete statistical breakdown of Entry/Exit times and Duration for Winners vs Losers.

Source: ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx
"""

import pandas as pd
import numpy as np
import scipy.stats as stats
import os

EXCEL_PATH = r"c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_CME_MINI_MNQ1!_2026-01-07_6f55a.xlsx"

def get_minute_of_day(dt_series):
    """Convert datetime series to minutes from midnight."""
    return dt_series.dt.hour * 60 + dt_series.dt.minute

def format_min_as_time(minutes):
    """Convert minutes from midnight to HH:MM string."""
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"

def analyze():
    print(f"Loading Excel: {os.path.basename(EXCEL_PATH)}...")
    
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name="List of trades")
        df.columns = df.columns.str.strip()
        
        trades = []
        for t_id, t_group in df.groupby('Trade #'):
            t_group = t_group.sort_values('Date and time')
            if len(t_group) < 2: continue
            
            entry_row = t_group.iloc[0]
            exit_row = t_group.iloc[-1]
            
            direction = "Long" if "Long" in entry_row['Type'] else "Short"
            entry_time = entry_row['Date and time']
            exit_time = exit_row['Date and time']
            profit = t_group['Net P&L USD'].sum()
            
            trades.append({
                'TradeNum': t_id,
                'Direction': direction,
                'Entry Time': entry_time,
                'Exit Time': exit_time,
                'P&L': profit
            })
            
        t_df = pd.DataFrame(trades)
        
        # Datetime Handling
        t_df['entry_dt'] = pd.to_datetime(t_df['Entry Time']).dt.tz_localize(None).dt.tz_localize('America/New_York')
        t_df['exit_dt'] = pd.to_datetime(t_df['Exit Time']).dt.tz_localize(None).dt.tz_localize('America/New_York')
        
        # Calculate Duration (minutes)
        t_df['duration_min'] = (t_df['exit_dt'] - t_df['entry_dt']).dt.total_seconds() / 60.0
        
        # Calculate Minute of Day (for aggregation)
        t_df['entry_mod'] = get_minute_of_day(t_df['entry_dt'])
        t_df['exit_mod'] = get_minute_of_day(t_df['exit_dt'])
        
        # Split Winners/Losers
        winners = t_df[t_df['P&L'] > 0].copy()
        losers = t_df[t_df['P&L'] < 0].copy()
        
        print(f"\nStats for {len(t_df)} Trades ({len(winners)} Wins, {len(losers)} Losses)")
        
        # DATASETS TO ANALYZE
        datasets = {
            "ALL TRADES": t_df,
            "WINNERS": winners,
            "LOSERS": losers
        }
        
        metrics = ['entry_mod', 'exit_mod', 'duration_min']
        metric_names = ['Entry Time', 'Exit Time', 'Duration (min)']
        
        for m_idx, metric in enumerate(metrics):
            m_name = metric_names[m_idx]
            print(f"\n=== {m_name.upper()} ANALYSIS ===")
            print(f"{'Category':<12} | {'Mean':<8} | {'Median':<8} | {'Mode':<8} | {'StdDev':<8} | {'Min':<8} | {'Max':<8}")
            print("-" * 80)
            
            for cat, data in datasets.items():
                if data.empty: continue
                vals = data[metric]
                
                mean_v = vals.mean()
                median_v = vals.median()
                mode_v = vals.mode()[0] if not vals.mode().empty else 0
                std_v = vals.std()
                min_v = vals.min()
                max_v = vals.max()
                
                # Format output
                if metric == 'duration_min':
                    # Float formatting
                    print(f"{cat:<12} | {mean_v:<8.1f} | {median_v:<8.1f} | {mode_v:<8.1f} | {std_v:<8.1f} | {min_v:<8.1f} | {max_v:<8.1f}")
                else:
                    # Time formatting
                    print(f"{cat:<12} | {format_min_as_time(mean_v):<8} | {format_min_as_time(median_v):<8} | {format_min_as_time(mode_v):<8} | {std_v:<8.1f} | {format_min_as_time(min_v):<8} | {format_min_as_time(max_v):<8}")

        # BINNING ANALYSIS (Histogram)
        # Focus on Entry Times (09:30 - 11:00)
        print("\n=== ENTRY TIME DISTRIBUTION (5-min Bins) ===")
        print(f"{'Time':<10} | {'Wins':<6} | {'Losses':<6} | {'Win Rate':<8}")
        
        # Create bins from 09:30 (570 min) to 16:00 (960 min)
        start_min = 9*60 + 30
        end_min = 16*60
        step = 5
        
        for b_start in range(start_min, end_min, step):
            b_end = b_start + step
            
            # Filter
            w_count = len(winners[(winners['entry_mod'] >= b_start) & (winners['entry_mod'] < b_end)])
            l_count = len(losers[(losers['entry_mod'] >= b_start) & (losers['entry_mod'] < b_end)])
            total = w_count + l_count
            
            if total > 0:
                wr = (w_count / total) * 100
                print(f"{format_min_as_time(b_start):<10} | {w_count:<6} | {l_count:<6} | {wr:<8.1f}%")
            else:
                # print(f"{format_min_as_time(b_start):<10} | 0      | 0      | -")
                pass

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze()
