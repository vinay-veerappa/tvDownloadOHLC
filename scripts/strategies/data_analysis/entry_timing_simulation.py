"""
Entry timing simulation - simplified and corrected version

Compares:
- IB Breakout: Trade breaks of 9:30-10:15 opening range, flexible entry after 10:15
- Noon Scenarios: Entry during 12:00-13:30 window with variable retrace requirements
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

NQ_DATA_PATH = 'data/NQ1_1m.parquet'
ES_DATA_PATH = 'data/ES1_1m.parquet'
OUTPUT_DIR = Path('DataAnalysisExpert/entry_timing_simulation')
OUTPUT_DIR.mkdir(exist_ok=True)

def run_simulation(ticker, data_path, output_prefix):
    """Run all entry scenarios"""
    
    print(f"\n{'='*100}")
    print(f"ENTRY TIMING SIMULATION: {ticker}")
    print(f"{'='*100}\n")
    
    # Load data
    df = pd.read_parquet(data_path)
    df.index = pd.to_datetime(df.index, utc=True)
    df['time_utc'] = df.index
    df['time_ny'] = df.index.tz_convert('America/New_York')
    df['date'] = df['time_ny'].dt.date
    df['hour'] = df['time_ny'].dt.hour
    df['minute'] = df['time_ny'].dt.minute
    
    # Filter to 2020+
    df = df[df['time_utc'].dt.year >= 2020].copy()
    
    results = {'ticker': ticker, 'scenarios': {}}
    
    # IB Breakout scenario
    print("\n1. IB BREAKOUT (flexible entry after 10:15)\n" + "─"*100)
    ib_stats = test_ib_breakout(df)
    results['scenarios']['ib_breakout'] = ib_stats
    print_results(ib_stats)
    
    # Noon scenarios  
    noon_scenarios = [
        ('noon_immediate', 'NOON IMMEDIATE BREAK', 0),
        ('noon_25_retrace', 'NOON 25% RETRACE', 25),
        ('noon_50_retrace', 'NOON 50% RETRACE (CURRENT)', 50),
        ('noon_75_retrace', 'NOON 75% RETRACE', 75),
    ]
    
    for scenario_key, scenario_name, retrace in noon_scenarios:
        print(f"\n{len(results['scenarios'])+1}. {scenario_name}\n" + "─"*100)
        noon_stats = test_noon_scenario(df, retrace)
        results['scenarios'][scenario_key] = noon_stats
        print_results(noon_stats)
    
    # Quick comparison
    print(f"\n{'='*100}")
    print("QUICK COMPARISON")
    print(f"{'='*100}\n")
    print(f"{'Scenario':<35} {'Win%':<10} {'Avg Win':<12} {'Avg Loss':<12}  {'R:R':<8}")
    print(f"{'-'*80}")
    
    for key, data in results['scenarios'].items():
        scenario_name = {
            'ib_breakout': 'IB Breakout',
            'noon_immediate': 'Noon Immediate',
            'noon_25_retrace': 'Noon 25% Retrace',
            'noon_50_retrace': 'Noon 50% Retrace (Current)',
            'noon_75_retrace': 'Noon 75% Retrace',
        }.get(key, key)
        
        win_pct = data.get('win_pct', 0)
        avg_win = data.get('avg_win_pts', 0)
        avg_loss = data.get('avg_loss_pts', 0) 
        rr = abs(avg_loss/avg_win) if avg_win != 0 else 0
        
        print(f"{scenario_name:<35} {win_pct:>8.1f}%  {avg_win:>10.1f} pts  {avg_loss:>10.1f} pts  1:{rr:>6.1f}x")
    
    return results


def test_ib_breakout(df):
    """IB breakout scenario"""
    
    trades = []
    dates = df['date'].unique()
    
    for date in dates:
        day_df = df[df['date'] == date]
        
        # IB: 9:30-10:15
        ib_data = day_df[(day_df['hour'] == 9) | ((day_df['hour'] == 10) & (day_df['minute'] < 15))]
        
        if len(ib_data) < 5:
            continue
        
        ib_high = ib_data['high'].max()
        ib_low = ib_data['low'].min()
        ib_range = ib_high - ib_low
        
        # Also track open range (9:30-10:30) for TP/SL
        open_data = day_df[(day_df['hour'] == 9) | ((day_df['hour'] == 10) & (day_df['minute'] < 30))]
        open_high = open_data['high'].max()
        open_low = open_data['low'].min()
        open_range = open_high - open_low
        
        if open_range <= 0:
            continue
        
        # Post-IB entry window: 10:15-15:45
        post_ib = day_df[(day_df['time_ny'].dt.hour >= 10) & ((day_df['time_ny'].dt.hour < 15) | ((day_df['time_ny'].dt.hour == 15) & (day_df['time_ny'].dt.minute < 45)))]
        
        if len(post_ib) < 2:
            continue
        
        # Find break
        direction = None
        entry_price = None
        entry_idx = None
        
        for idx, (i, row) in enumerate(post_ib.iterrows()):
            if row['high'] > ib_high and direction is None:
                direction = 'BULL'
                entry_price = ib_high
                entry_idx = idx
                break
            elif row['low'] < ib_low and direction is None:
                direction = 'BEAR'
                entry_price = ib_low
                entry_idx = idx
                break
        
        if direction is None:
            continue
        
        # Get remaining bars after entry
        remaining_bars = post_ib.iloc[entry_idx:] if entry_idx < len(post_ib) else post_ib.iloc[-1:]
        
        # Execute trade
        if direction == 'BULL':
            tp_level = open_high - open_range * 0.5
            sl_level = open_low - open_range * 0.5
            
            # Find fill
            for i, row in remaining_bars.iterrows():
                if row['high'] >= tp_level:
                    profit = tp_level - entry_price
                    break
                elif row['low'] <= sl_level:
                    profit = -(open_range * 0.5 + entry_price - open_low)
                    break
            else:
                profit = remaining_bars.iloc[-1]['close'] - entry_price
        else:  # BEAR
            tp_level = open_low + open_range * 0.5
            sl_level = open_high + open_range * 0.5
            
            for i, row in remaining_bars.iterrows():
                if row['low'] <= tp_level:
                    profit = entry_price - tp_level
                    break
                elif row['high'] >= sl_level:
                    profit = -(open_high + open_range * 0.5 - entry_price)
                    break
            else:
                profit = entry_price - remaining_bars.iloc[-1]['close']
        
        profit_pct = profit / open_range * 100
        trades.append({
            'profit': profit,
            'profit_pct': profit_pct,
            'outcome': 'WIN' if profit > 0 else 'LOSS'
        })
    
    return compile_stats(trades, pd.DataFrame(df.groupby('date').size()))


def test_noon_scenario(df, retrace_pct):
    """Noon entry scenario"""
    
    trades = []
    dates = df['date'].unique()
    
    for date in dates:
        day_df = df[df['date'] == date]
        
        # Open range: 9:30-10:30
        open_data = day_df[(day_df['hour'] == 9) | ((day_df['hour'] == 10) & (day_df['minute'] < 30))]
        
        if len(open_data) < 5:
            continue
        
        open_high = open_data['high'].max()
        open_low = open_data['low'].min()
        open_range = open_high - open_low
        
        if open_range <= 0:
            continue
        
        # Entry window: 12:00-13:30
        entry_window = day_df[((day_df['hour'] == 12) | ((day_df['hour'] == 13) & (day_df['minute'] <= 30)))]
        
        if len(entry_window) < 3:
            continue
        
        # Rest of day: 13:30-15:45
        rest_of_day = day_df[((day_df['hour'] == 13) & (day_df['minute'] > 30)) | ((day_df['hour'] >= 14) & (day_df['hour'] < 15)) | ((day_df['hour'] == 15) & (day_df['minute'] < 45))]
        
        if len(rest_of_day) == 0:
            rest_of_day = entry_window.iloc[-1:]
        
        # Determine direction
        entry_high = entry_window['high'].max()
        entry_low = entry_window['low'].min()
        midpoint = (open_high + open_low) / 2
        
        direction = None
        entry_price = None
        exit_data = None
        
        if entry_high > midpoint:
            # BULL
            direction = 'BULL'
            if retrace_pct == 0:
                # Immediate: look for break
                for i, row in entry_window.iterrows():
                    if row['high'] > open_high:
                        entry_price = open_high
                        exit_data = entry_window[entry_window.index >= i]
                        break
            else:
                # Retrace: look for specific level
                target_level = entry_high - (entry_high - open_low) * (retrace_pct / 100.0)
                for i, row in entry_window.iterrows():
                    if row['low'] <= target_level:
                        entry_price = target_level
                        exit_data = entry_window[entry_window.index >= i]
                        break
                
                if entry_price is None:
                    for i, row in rest_of_day.iterrows():
                        if row['low'] <= target_level:
                            entry_price = target_level
                            exit_data = rest_of_day[rest_of_day.index >= i]
                            break
        
        elif entry_low < midpoint:
            # BEAR
            direction = 'BEAR'
            if retrace_pct == 0:
                for i, row in entry_window.iterrows():
                    if row['low'] < open_low:
                        entry_price = open_low
                        exit_data = entry_window[entry_window.index >= i]
                        break
            else:
                target_level = entry_low + (open_high - entry_low) * (retrace_pct / 100.0)
                for i, row in entry_window.iterrows():
                    if row['high'] >= target_level:
                        entry_price = target_level
                        exit_data = entry_window[entry_window.index >= i]
                        break
                
                if entry_price is None:
                    for i, row in rest_of_day.iterrows():
                        if row['high'] >= target_level:
                            entry_price = target_level
                            exit_data = rest_of_day[rest_of_day.index >= i]
                            break
        
        if entry_price is None or exit_data is None:
            continue
        
        # Execute trade
        tp_level = None
        sl_level = None
        
        if direction == 'BULL':
            tp_level = open_high - open_range * 0.5
            sl_level = open_low - open_range * 0.5
            
            for i, row in exit_data.iterrows():
                if row['high'] >= tp_level:
                    profit = tp_level - entry_price
                    break
                elif row['low'] <= sl_level:
                    profit = sl_level - entry_price
                    break
            else:
                profit = exit_data.iloc[-1]['close'] - entry_price
        else:  # BEAR
            tp_level = open_low + open_range * 0.5
            sl_level = open_high + open_range * 0.5
            
            for i, row in exit_data.iterrows():
                if row['low'] <= tp_level:
                    profit = entry_price - tp_level
                    break
                elif row['high'] >= sl_level:
                    profit = entry_price - sl_level
                    break
            else:
                profit = entry_price - exit_data.iloc[-1]['close']
        
        profit_pct = profit / open_range * 100
        trades.append({
            'profit': profit,
            'profit_pct': profit_pct,
            'outcome': 'WIN' if profit > 0 else 'LOSS'
        })
    
    return compile_stats(trades, pd.DataFrame(df.groupby('date').size()))


def compile_stats(trades_list, dates_df):
    """Compile statistics"""
    
    if len(trades_list) == 0:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_pct': 0,
            'avg_win_pct': 0,
            'avg_loss_pct': 0,
            'avg_win_pts': 0,
            'avg_loss_pts': 0,
        }
    
    trades_df = pd.DataFrame(trades_list)
    wins = trades_df[trades_df['outcome'] == 'WIN']
    losses = trades_df[trades_df['outcome'] == 'LOSS']
    
    avg_range = 157 if 'NQ' in str(trades_df) else 31  # Approximate for scaling
    
    stats = {
        'total_trades': len(trades_df),
        'wins': len(wins),
        'losses': len(losses),
        'win_pct': len(wins) / len(trades_df) * 100 if len(trades_df) > 0 else 0,
        'avg_win_pct': wins['profit_pct'].mean() if len(wins) > 0 else 0,
        'avg_loss_pct': losses['profit_pct'].mean() if len(losses) > 0 else 0,
        'avg_win_pts': wins['profit'].mean() if len(wins) > 0 else 0,
        'avg_loss_pts': losses['profit'].mean() if len(losses) > 0 else 0,
    }
    
    return stats


def print_results(stats):
    """Print formatted results"""
    
    if stats['total_trades'] == 0:
        print("  No valid trades found\n")
        return
    
    rr = abs(stats['avg_loss_pct'] / stats['avg_win_pct']) if stats['avg_win_pct'] > 0 else 0
    
    print(f"Trades: {stats['total_trades']} | Wins: {stats['wins']} | Losses: {stats['losses']}")
    print(f"Win Rate: {stats['win_pct']:.1f}%")
    print(f"Avg Win:  {stats['avg_win_pct']:>7.2f}% = {stats['avg_win_pts']:>7.1f} pts")
    print(f"Avg Loss: {stats['avg_loss_pct']:>7.2f}% = {stats['avg_loss_pts']:>7.1f} pts")
    print(f"Risk/Reward: 1:{rr:.2f}")
    
    ev_pct = (stats['win_pct']/100 * stats['avg_win_pct']) + ((100-stats['win_pct'])/100 * stats['avg_loss_pct'])
    print(f"EV per trade: {ev_pct:.2f}% of range\n")


if __name__ == '__main__':
    nq = run_simulation('NQ1', NQ_DATA_PATH, 'NQ1')
    es = run_simulation('ES1', ES_DATA_PATH, 'ES1')
