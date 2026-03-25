"""
Final Strategy Variant Comparison
=================================
Test all promising variants and compile results for final summary.
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import time
import sys
sys.path.insert(0, 'scripts/backtest/framework')

from simulate_trades import TradeSimulator, ORB_V7_Strategy, BaseStrategy, TradeState, DayContext

# ============================================================
# VARIANT 1: PULLBACK ENTRY (Wait for pullback to Range after confirmation)
# ============================================================

class ORB_PullbackEntry_Strategy(ORB_V7_Strategy):
    """Wait for pullback to Range High/Low after confirmation before entering"""
    
    def __init__(self):
        super().__init__({
            'name': 'ORB_PullbackEntry',
            'confirm_pct': 0.10,
            'tp1_pct': 0.05,
            'tp1_qty': 0.50,
        })
        
    def should_enter(self, bar, state, context):
        if state.position != 0:
            return False, 0, 0.0
        
        bar_time = bar.name.time()
        if bar_time >= self.config['entry_cutoff_time']:
            return False, 0, 0.0
        
        # Check if we've already seen a confirmed breakout
        if 'breakout_seen' not in state.custom:
            state.custom['breakout_seen'] = False
            state.custom['breakout_dir'] = 0
        
        confirm_long = context.range_high * 1.001
        confirm_short = context.range_low * 0.999
        
        # Detect breakout
        if not state.custom['breakout_seen']:
            if bar['close'] > confirm_long:
                state.custom['breakout_seen'] = True
                state.custom['breakout_dir'] = 1
            elif bar['close'] < confirm_short:
                state.custom['breakout_seen'] = True
                state.custom['breakout_dir'] = -1
        
        # Wait for pullback to range
        if state.custom['breakout_seen']:
            if state.custom['breakout_dir'] == 1:
                # Long: wait for pullback to Range High
                if bar['low'] <= context.range_high and bar['close'] > context.range_high:
                    return True, 1, bar['close']
            else:
                # Short: wait for pullback to Range Low
                if bar['high'] >= context.range_low and bar['close'] < context.range_low:
                    return True, -1, bar['close']
        
        return False, 0, 0.0

# ============================================================
# VARIANT 2: ENGULFING EXIT (Exit on engulfing candle)
# ============================================================

class ORB_EngulfingExit_Strategy(ORB_V7_Strategy):
    """Exit immediately if next bar engulfs the breakout bar"""
    
    def __init__(self):
        super().__init__({
            'name': 'ORB_EngulfingExit',
            'confirm_pct': 0.10,
            'tp1_pct': 0.05,
            'use_engulfing_exit': True,
        })

# ============================================================
# VARIANT 3: AGGRESSIVE TP (Lower TP1 to 0.03%)
# ============================================================

class ORB_AggressiveTP_Strategy(ORB_V7_Strategy):
    """Lower TP1 to 0.03% for faster profit capture"""
    
    def __init__(self):
        super().__init__({
            'name': 'ORB_AggressiveTP',
            'confirm_pct': 0.10,
            'tp1_pct': 0.03,  # Lower TP1
            'tp1_qty': 0.50,
        })

# ============================================================
# VARIANT 4: NO CTQ (Let entire position ride to time exit)
# ============================================================

class ORB_NoCTQ_Strategy(ORB_V7_Strategy):
    """No partial exit - let full position ride to SL or time exit"""
    
    def __init__(self):
        super().__init__({
            'name': 'ORB_NoCTQ',
            'confirm_pct': 0.10,
            'tp1_pct': 100.0,  # Effectively disables TP1
            'tp1_qty': 0.0,
        })

# ============================================================
# VARIANT 5: HIGHER CONFIRMATION (0.15% confirmation)
# ============================================================

class ORB_HighConfirm_Strategy(ORB_V7_Strategy):
    """Require 0.15% confirmation for stronger breakouts"""
    
    def __init__(self):
        super().__init__({
            'name': 'ORB_HighConfirm',
            'confirm_pct': 0.15,
            'tp1_pct': 0.05,
        })

# ============================================================
# RUN ALL VARIANTS
# ============================================================

def run_all_variants():
    variants = [
        ORB_V7_Strategy(),        # Baseline
        ORB_PullbackEntry_Strategy(),
        ORB_EngulfingExit_Strategy(),
        ORB_AggressiveTP_Strategy(),
        ORB_NoCTQ_Strategy(),
        ORB_HighConfirm_Strategy(),
    ]
    
    results = []
    
    for strategy in variants:
        print(f"Running {strategy.name}...")
        sim = TradeSimulator(strategy)
        sim.load_data('NQ1', years=10)
        trades_df = sim.run()
        summary = sim.summary()
        
        # Add exit reason breakdown
        if not trades_df.empty:
            sl_pnl = trades_df[trades_df['exit_reason'] == 'SL']['pnl_pct'].sum()
            time_pnl = trades_df[trades_df['exit_reason'] == 'TIME']['pnl_pct'].sum()
            tp1_pnl = trades_df[trades_df['exit_reason'] == 'TP1']['pnl_pct'].sum()
        else:
            sl_pnl = time_pnl = tp1_pnl = 0
        
        results.append({
            'Strategy': strategy.name,
            'Trades': summary['trades'],
            'WinRate': summary['win_rate'],
            'GrossPnL': summary['gross_pnl'],
            'AvgPnL': summary['avg_pnl'],
            'PF': summary['profit_factor'],
            'AvgMAE': summary['avg_mae'],
            'SL_PnL': sl_pnl,
            'TIME_PnL': time_pnl,
            'TP1_PnL': tp1_pnl,
        })
    
    df = pd.DataFrame(results)
    return df

if __name__ == '__main__':
    print("=== FINAL VARIANT COMPARISON ===\n")
    
    results = run_all_variants()
    
    print("\n" + "="*100)
    print("VARIANT COMPARISON RESULTS")
    print("="*100)
    
    # Format for display
    display = results.copy()
    display['WinRate'] = display['WinRate'].apply(lambda x: f"{x:.1%}")
    display['GrossPnL'] = display['GrossPnL'].apply(lambda x: f"{x:+.2f}%")
    display['AvgPnL'] = display['AvgPnL'].apply(lambda x: f"{x:.4f}%")
    display['PF'] = display['PF'].apply(lambda x: f"{x:.2f}")
    display['AvgMAE'] = display['AvgMAE'].apply(lambda x: f"{x:.4f}%")
    
    print(display[['Strategy', 'Trades', 'WinRate', 'GrossPnL', 'PF', 'AvgMAE']].to_string(index=False))
    
    print("\n" + "="*100)
    print("PNL BREAKDOWN BY EXIT TYPE")
    print("="*100)
    for _, row in results.iterrows():
        print(f"{row['Strategy']:25s} SL: {row['SL_PnL']:+7.1f}%  TIME: {row['TIME_PnL']:+7.1f}%  TP1: {row['TP1_PnL']:+7.1f}%")
    
    # Save results
    results.to_csv('scripts/backtest/9_30_breakout/results/variant_comparison_final.csv', index=False)
    print("\nSaved: variant_comparison_final.csv")
    
    # Best strategy
    best = results.loc[results['GrossPnL'].idxmax()]
    print(f"\n=== BEST STRATEGY: {best['Strategy']} ===")
    print(f"Gross PnL: {best['GrossPnL']:.2f}%")
    print(f"Profit Factor: {best['PF']:.2f}")
