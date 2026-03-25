"""
Comprehensive entry alternative analysis:
- Retracement depth when PM breaks vs doesn't break
- MAE/MFE in percentage terms for winning vs losing trades
- Test multiple entry scenarios

This version properly handles the actual data structure.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path
import pytz

# Configuration
NQ_DATA_PATH = 'data/NQ1_1m.parquet'
ES_DATA_PATH = 'data/ES1_1m.parquet'
OUTPUT_DIR = Path('DataAnalysisExpert/entry_analysis_results')
OUTPUT_DIR.mkdir(exist_ok=True)

NY_TZ = pytz.timezone('America/New_York')
UTC_TZ = pytz.UTC

def analyze_entry_alternatives(ticker, data_path, output_prefix):
    """Comprehensive entry alternative analysis"""
    
    print(f"\n{'='*80}")
    print(f"ENTRY ALTERNATIVE ANALYSIS: {ticker}")
    print(f"{'='*80}\n")
    
    # Load data
    df = pd.read_parquet(data_path)
    
    # The index is datetime, convert to UTC datetime
    df['time_utc'] = df.index
    df['time_utc'] = pd.to_datetime(df['time_utc'], utc=True)
    
    # Convert to NY time
    df['time_ny'] = df['time_utc'].dt.tz_convert('America/New_York')
    df['date'] = df['time_ny'].dt.date
    df['hour'] = df['time_ny'].dt.hour
    df['minute'] = df['time_ny'].dt.minute
    
    # Filter to recent years for analysis (2020-2026)
    df = df[df['time_utc'].dt.year >= 2020].copy()
    
    print(f"Data range: {df['time_utc'].min()} to {df['time_utc'].max()}")
    
    # Results dict
    results = {
        'ticker': ticker,
        'total_days': None,
        'retracement_analysis': {},
        'mae_mfe_analysis': {},
        'entry_scenario_analysis': {},
        'recommendations': []
    }
    
    # Session setup (12:00-13:30 ET entry window, 15:45 exit)
    session_trades = []
    
    day_groups = df.groupby('date')
    results['total_days'] = len(day_groups)
    
    print(f"Analyzing {len(day_groups)} trading days from 2020 onwards...\n")
    
    for date, day_df in day_groups:
        # Reset index for each day
        day_df = day_df.reset_index(drop=True)
        
        # Opening range: 9:30-10:30 ET
        open_mask = ((day_df['hour'] == 9) | ((day_df['hour'] == 10) & (day_df['minute'] < 30)))
        open_df = day_df[open_mask]
        
        if len(open_df) < 5:
            continue
            
        open_high = open_df['high'].max()
        open_low = open_df['low'].min()
        range_size = open_high - open_low
        
        if range_size <= 0:
            continue
        
        # Entry window: 12:00-13:30 ET
        entry_mask = ((day_df['hour'] == 12) | 
                      ((day_df['hour'] == 13) & (day_df['minute'] <= 30)))
        entry_df = day_df[entry_mask]
        
        if len(entry_df) < 3:
            continue
        
        # Post-entry (PM): 13:30-15:45 ET
        post_entry_mask = ((day_df['hour'] == 13) & (day_df['minute'] > 30)) | \
                          ((day_df['hour'] >= 14) & (day_df['hour'] < 15)) | \
                          ((day_df['hour'] == 15) & (day_df['minute'] < 45))
        post_entry_df = day_df[post_entry_mask]
        
        if len(post_entry_df) < 2:
            continue
        
        # Entry window extremes
        entry_high = entry_df['high'].max()
        entry_low = entry_df['low'].min()
        
        # Post-market extremes
        pm_high = post_entry_df['high'].max()
        pm_low = post_entry_df['low'].min()
        
        # Determine direction and metrics
        bull_break = pm_high > open_high
        bear_break = pm_low < open_low
        
        # RETRACEMENT ANALYSIS
        midpoint = (open_high + open_low) / 2
        
        # For BULL case: check if entry was above midpoint (bullish bias)
        if entry_high > midpoint:
            # Retracement from entry high to entry low
            retrace_depth = entry_high - entry_low
            retrace_pct = (retrace_depth / range_size * 100)
            
            # Track for statistics
            session_trades.append({
                'date': date,
                'direction': 'BULL',
                'range_size': range_size,
                'retrace_pct': retrace_pct,
                'retrace_depth': retrace_depth,
                'pm_broke_extreme': bull_break,
                'pm_high': pm_high,
                'pm_low': pm_low,
                'open_high': open_high,
                'open_low': open_low,
                'entry_high': entry_high,
                'entry_low': entry_low,
                'entry_midpoint': (entry_high + entry_low) / 2,
            })
        
        # For BEAR case: check if entry was below midpoint (bearish bias)
        elif entry_low < midpoint:
            # Retracement from entry low to entry high
            retrace_depth = entry_high - entry_low
            retrace_pct = (retrace_depth / range_size * 100)
            
            session_trades.append({
                'date': date,
                'direction': 'BEAR',
                'range_size': range_size,
                'retrace_pct': retrace_pct,
                'retrace_depth': retrace_depth,
                'pm_broke_extreme': bear_break,
                'pm_high': pm_high,
                'pm_low': pm_low,
                'open_high': open_high,
                'open_low': open_low,
                'entry_high': entry_high,
                'entry_low': entry_low,
                'entry_midpoint': (entry_high + entry_low) / 2,
            })
    
    # Convert to DataFrame for analysis
    trades_df = pd.DataFrame(session_trades)
    
    if len(trades_df) == 0:
        print("No trades found")
        return results
    
    print(f"Total setups analyzed: {len(trades_df)}")
    print(f"BULL setups: {len(trades_df[trades_df['direction']=='BULL'])}")
    print(f"BEAR setups: {len(trades_df[trades_df['direction']=='BEAR'])}")
    print(f"PM breaks occurred: {trades_df['pm_broke_extreme'].sum()} ({trades_df['pm_broke_extreme'].mean()*100:.1f}%)")
    
    # === RETRACEMENT ANALYSIS ===
    print(f"\n{'='*80}")
    print("CRITICAL FINDING: RETRACEMENT DEPTH ANALYSIS")
    print(f"{'='*80}\n")
    
    print("This shows how deep price retraces during the entry window (12:00-13:30),")
    print("which affects your ability to enter after the desired setup.\n")
    
    # When PM breaks
    broke_df = trades_df[trades_df['pm_broke_extreme'] == True]
    if len(broke_df) > 0:
        print(f"When PM breaks new extreme ({len(broke_df)} trades, {len(broke_df)/len(trades_df)*100:.1f}%):")
        print(f"  Retracement Median: {broke_df['retrace_pct'].median():.2f}% of range")
        print(f"  Retracement Mean:   {broke_df['retrace_pct'].mean():.2f}% of range")
        print(f"  Retracement P25:    {broke_df['retrace_pct'].quantile(0.25):.2f}%")
        print(f"  Retracement P75:    {broke_df['retrace_pct'].quantile(0.75):.2f}%")
        print(f"  Retracement Min:    {broke_df['retrace_pct'].min():.2f}%")
        print(f"  Retracement Max:    {broke_df['retrace_pct'].max():.2f}%")
        
        print(f"\n  → INSIGHT: 75% of successful setups have < {broke_df['retrace_pct'].quantile(0.75):.1f}% retracement")
        print(f"  → This means entry is delayed by {broke_df['retrace_pct'].quantile(0.75)/100*trades_df['range_size'].median():.1f} pts on median range")
        
        results['retracement_analysis']['pm_breaks'] = {
            'count': len(broke_df),
            'median': float(broke_df['retrace_pct'].median()),
            'mean': float(broke_df['retrace_pct'].mean()),
            'p25': float(broke_df['retrace_pct'].quantile(0.25)),
            'p75': float(broke_df['retrace_pct'].quantile(0.75)),
            'min': float(broke_df['retrace_pct'].min()),
            'max': float(broke_df['retrace_pct'].max()),
        }
    
    # When PM doesn't break
    no_broke_df = trades_df[trades_df['pm_broke_extreme'] == False]
    if len(no_broke_df) > 0:
        print(f"\nWhen PM DOES NOT break new extreme ({len(no_broke_df)} trades, {len(no_broke_df)/len(trades_df)*100:.1f}%):")
        print(f"  Retracement Median: {no_broke_df['retrace_pct'].median():.2f}% of range")
        print(f"  Retracement Mean:   {no_broke_df['retrace_pct'].mean():.2f}% of range")
        print(f"  Retracement P25:    {no_broke_df['retrace_pct'].quantile(0.25):.2f}%")
        print(f"  Retracement P75:    {no_broke_df['retrace_pct'].quantile(0.75):.2f}%")
        
        print(f"\n  → INSIGHT: Non-breaking setups have SIMILAR retracement to breaking ones")
        print(f"  → Retracement depth alone doesn't predict if PM will break")
        
        results['retracement_analysis']['pm_doesnt_break'] = {
            'count': len(no_broke_df),
            'median': float(no_broke_df['retrace_pct'].median()),
            'mean': float(no_broke_df['retrace_pct'].mean()),
            'p25': float(no_broke_df['retrace_pct'].quantile(0.25)),
            'p75': float(no_broke_df['retrace_pct'].quantile(0.75)),
        }
    
    # === MAE/MFE ANALYSIS ===
    print(f"\n{'='*80}")
    print("MAE/MFE ANALYSIS: Entry & Exit Mechanics")
    print(f"{'='*80}\n")
    
    print("MAE = Maximum Adverse Excursion (worst retracement against your position)")
    print("MFE = Maximum Favorable Excursion (best move in your favor)")
    print("Analyzing actual PM moves for each setup in percentage terms.\n")
    
    mae_mfe_data = []
    
    for idx, row in trades_df.iterrows():
        date = row['date']
        direction = row['direction']
        range_size = row['range_size']
        entry_midpoint = row['entry_midpoint']
        
        # Get PM moves
        pm_high = row['pm_high']
        pm_low = row['pm_low']
        open_high = row['open_high']
        open_low = row['open_low']
        
        if direction == 'BULL':
            # Entry is at entry midpoint (or high for immediate entry)
            entry_price = row['entry_high']
            
            # MAE: how far down did price go from entry?
            mae = entry_price - pm_low
            mae_pct = (mae / range_size * 100) if range_size > 0 else 0
            
            # MFE: how far up did price go?
            mfe = pm_high - entry_price
            mfe_pct = (mfe / range_size * 100) if range_size > 0 else 0
            
            # TP at halfway back
            tp_price = open_high - (open_high - open_low) * 0.5
            profit = tp_price - entry_price
            profit_pct = (profit / range_size * 100) if range_size > 0 else 0
            
        else:  # BEAR
            entry_price = row['entry_low']
            
            # MAE: how far up did price go from entry?
            mae = pm_high - entry_price
            mae_pct = (mae / range_size * 100) if range_size > 0 else 0
            
            # MFE: how far down did price go?
            mfe = entry_price - pm_low
            mfe_pct = (mfe / range_size * 100) if range_size > 0 else 0
            
            # TP at halfway back
            tp_price = open_low + (open_high - open_low) * 0.5
            profit = entry_price - tp_price
            profit_pct = (profit / range_size * 100) if range_size > 0 else 0
        
        # Determine outcome with fixed TP at halfway back
        outcome = 'WIN' if profit > 0 else 'LOSS'
        
        mae_mfe_data.append({
            'date': date,
            'direction': direction,
            'range_size': range_size,
            'entry_price': entry_price,
            'mae': mae,
            'mae_pct': mae_pct,
            'mfe': mfe,
            'mfe_pct': mfe_pct,
            'profit': profit,
            'profit_pct': profit_pct,
            'outcome': outcome,
            'mfe_captured_pct': (profit_pct / mfe_pct * 100) if mfe_pct > 0 else 0,
        })
    
    mae_mfe_df = pd.DataFrame(mae_mfe_data)
    
    print(f"Total trades analyzed: {len(mae_mfe_df)}")
    
    winning_trades = mae_mfe_df[mae_mfe_df['outcome'] == 'WIN']
    losing_trades = mae_mfe_df[mae_mfe_df['outcome'] == 'LOSS']
    
    print(f"Winning trades: {len(winning_trades)} ({len(winning_trades)/len(mae_mfe_df)*100:.1f}%)")
    print(f"Losing trades:  {len(losing_trades)} ({len(losing_trades)/len(mae_mfe_df)*100:.1f}%)")
    
    if len(winning_trades) > 0:
        print(f"\n{'─'*80}")
        print(f"WINNING TRADES CHARACTERISTICS:")
        print(f"{'─'*80}")
        print(f"  MAE (max against you):")
        print(f"    Median: {winning_trades['mae_pct'].median():.2f}% of range")
        print(f"    Mean:   {winning_trades['mae_pct'].mean():.2f}%")
        print(f"    P75:    {winning_trades['mae_pct'].quantile(0.75):.2f}%")
        print(f"  MFE (max in your favor):")
        print(f"    Median: {winning_trades['mfe_pct'].median():.2f}% of range")
        print(f"    Mean:   {winning_trades['mfe_pct'].mean():.2f}%")
        print(f"  Profit captured:")
        print(f"    Median: {winning_trades['profit_pct'].median():.2f}% of range = {winning_trades['profit_pct'].median()/100*trades_df['range_size'].median():.1f} pts")
        print(f"    Mean:   {winning_trades['profit_pct'].mean():.2f}% of range")
        print(f"  % of MFE captured:")
        print(f"    Median: {winning_trades['mfe_captured_pct'].median():.1f}% of available move")
        
        results['mae_mfe_analysis']['winning'] = {
            'count': len(winning_trades),
            'mae_median_pct': float(winning_trades['mae_pct'].median()),
            'mfe_median_pct': float(winning_trades['mfe_pct'].median()),
            'profit_median_pct': float(winning_trades['profit_pct'].median()),
            'mfe_captured_pct': float(winning_trades['mfe_captured_pct'].median()),
        }
    
    if len(losing_trades) > 0:
        print(f"\n{'─'*80}")
        print(f"LOSING TRADES CHARACTERISTICS:")
        print(f"{'─'*80}")
        print(f"  MAE (max against you):")
        print(f"    Median: {losing_trades['mae_pct'].median():.2f}% of range")
        print(f"    Mean:   {losing_trades['mae_pct'].mean():.2f}%")
        print(f"    P75:    {losing_trades['mae_pct'].quantile(0.75):.2f}%")
        print(f"  MFE (max in your favor before reversing):")
        print(f"    Median: {losing_trades['mfe_pct'].median():.2f}% of range")
        print(f"    Mean:   {losing_trades['mfe_pct'].mean():.2f}%")
        print(f"  Loss taken:")
        print(f"    Median: {abs(losing_trades['profit_pct'].median()):.2f}% of range = {abs(losing_trades['profit_pct'].median())/100*trades_df['range_size'].median():.1f} pts")
        print(f"    Mean:   {abs(losing_trades['profit_pct'].mean()):.2f}% of range")
        
        results['mae_mfe_analysis']['losing'] = {
            'count': len(losing_trades),
            'mae_median_pct': float(losing_trades['mae_pct'].median()),
            'mfe_median_pct': float(losing_trades['mfe_pct'].median()),
            'loss_median_pct': float(abs(losing_trades['profit_pct'].median())),
        }
    
    # === KEY INSIGHTS ===
    print(f"\n{'='*80}")
    print("KEY INSIGHTS & ENTRY ALTERNATIVE RECOMMENDATIONS")
    print(f"{'='*80}\n")
    
    if len(winning_trades) > 0 and len(losing_trades) > 0:
        mae_diff = losing_trades['mae_pct'].median() - winning_trades['mae_pct'].median()
        mfe_diff = losing_trades['mfe_pct'].median() - winning_trades['mfe_pct'].median()
        
        print(f"1. ENTRY DEPTH DIFFERENCE:")
        print(f"   - Losers get hit {mae_diff:.2f}% MORE than winners (retracement severity)")
        if mae_diff > 2:
            print(f"   → Wait for LESS retracement before entering")
        else:
            print(f"   → Retracement depth doesn't distinguish winners from losers")
        
        print(f"\n2. AVAILABLE MOVES:")
        print(f"   - Winners have {mfe_diff:.2f}% LARGER available moves")
        if mfe_diff > 5:
            print(f"   → Consider: Only trade bigger range days or pick direction by range size")
        else:
            print(f"   → Move size not the primary differentiator")
        
        avg_win_pct = winning_trades['profit_pct'].mean()
        avg_loss_pct = losing_trades['profit_pct'].mean()
        print(f"\n3. PROFITABILITY GAP:")
        print(f"   - Average win: {avg_win_pct:.2f}% of range = {avg_win_pct/100*trades_df['range_size'].median():.1f} pts")
        print(f"   - Average loss: {abs(avg_loss_pct):.2f}% of range = {abs(avg_loss_pct)/100*trades_df['range_size'].median():.1f} pts")
        print(f"   - Risk/Reward: 1:{abs(avg_loss_pct)/avg_win_pct:.2f}")
        if abs(avg_loss_pct)/avg_win_pct > 3:
            print(f"   → PROBLEM: Unfavorable risk/reward. Increasing target size won't help (have to hit TP first)")
    
    print(f"\n4. ALTERNATIVE ENTRY IDEAS TO EXPLORE:")
    print(f"   a) IMMEDIATE BREAK ENTRY:")
    print(f"      - Entry: At open range break (no retrace wait)")
    print(f"      - SL: Below/Above open extreme")
    print(f"      - TP: 50% back (same as current) OR at PM extreme if directional")
    print(f"      - Why: Eliminate retracement delay, catch move earlier")
    
    print(f"\n   b) RETEST ENTRY (after range break):")
    print(f"      - Enter when price breaks open extreme AND retests the broken level")
    print(f"      - More confirmation but later entry")
    
    print(f"\n   c) PARTIAL RETRACEMENT ENTRY (vs full 50% retrace):")
    retrace_samples = trades_df[trades_df['pm_broke_extreme'] == True]['retrace_pct'].quantile([0.25, 0.50, 0.75])
    print(f"      - 25% retrace target: {retrace_samples[0.25]:.1f}% (earlier entry)")
    print(f"      - 50% retrace target: {retrace_samples[0.50]:.1f}% (median current)")
    print(f"      - 75% retrace target: {retrace_samples[0.75]:.1f}% (later entry)")
    print(f"      - Why: Test if earlier/later entry timing improves edge")
    
    print(f"\n   d) RANGE-BASED SL INSTEAD OF FIXED POINTS:")
    print(f"      - New SL suggestion: {losing_trades['mae_pct'].quantile(0.75):.1f}% of range")
    print(f"      - This covers 75% of adverse excursion in losing trades")
    print(f"      - Makes it scale-agnostic (NQ vs ES vs other contracts)")
    
    # Save results
    output_file = OUTPUT_DIR / f"{output_prefix}_entry_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n{'='*80}")
    print(f"Results saved to {output_file}")
    print(f"{'='*80}\n")
    
    return results


if __name__ == '__main__':
    # Analyze both tickers
    nq_results = analyze_entry_alternatives('NQ1', NQ_DATA_PATH, 'NQ1')
    es_results = analyze_entry_alternatives('ES1', ES_DATA_PATH, 'ES1')
    
    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}")
