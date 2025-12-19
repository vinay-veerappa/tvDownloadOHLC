"""
Comprehensive Intraday Trading Analysis

This script reads the generated EM datasets and produces a complete trading analysis
from multiple perspectives: S/R levels, targets, options strategies, and direct trading.
"""

import pandas as pd
import numpy as np
import os

def analyze_for_trading():
    print("\n" + "="*80)
    print("=== COMPREHENSIVE INTRADAY TRADING ANALYSIS ===")
    print("="*80)
    
    # Load datasets
    summary_df = pd.read_csv('data/analysis/em_method_summary.csv')
    perf_df = pd.read_csv('data/analysis/em_daily_performance.csv')
    levels_df = pd.read_csv('data/analysis/em_daily_levels.csv')
    touches_df = pd.read_csv('data/analysis/em_level_touches.csv')
    
    print(f"\nLoaded: {len(summary_df)} method summaries, {len(perf_df)} daily performance records")
    
    # ==========================================
    # SECTION 1: Best Method for Each Use Case
    # ==========================================
    
    print("\n" + "="*80)
    print("SECTION 1: BEST EM METHOD FOR EACH USE CASE")
    print("="*80)
    
    # 1A. Best for Containment (Options Selling)
    print("\n[1A] BEST FOR OPTIONS SELLING (Highest Containment at 100%)")
    contain_100 = summary_df[summary_df['multiple'] == 1.0].sort_values('containment_pct', ascending=False)
    print(contain_100[['method', 'containment_pct', 'median_mfe', 'median_mae']].head(5).to_string(index=False))
    
    # 1B. Best for S/R (Highest Touch + Reversal)
    print("\n[1B] BEST FOR S/R IDENTIFICATION (Most Touches at 50%)")
    sr_50 = summary_df[summary_df['multiple'] == 0.5].copy()
    sr_50['total_touch_pct'] = sr_50['touch_upper_pct'] + sr_50['touch_lower_pct']
    sr_50 = sr_50.sort_values('total_touch_pct', ascending=False)
    print(sr_50[['method', 'touch_upper_pct', 'touch_lower_pct', 'containment_pct']].head(5).to_string(index=False))
    
    # 1C. Best for Targets (Low MFE = Tight Range)
    print("\n[1C] BEST FOR TARGET SETTING (Tightest MFE at 100%)")
    target_100 = summary_df[summary_df['multiple'] == 1.0].sort_values('median_mfe', ascending=True)
    print(target_100[['method', 'median_mfe', 'median_mae', 'containment_pct']].head(5).to_string(index=False))
    
    # ==========================================
    # SECTION 2: S/R Friction Analysis
    # ==========================================
    
    print("\n" + "="*80)
    print("SECTION 2: INTRADAY S/R FRICTION ANALYSIS")
    print("="*80)
    
    # Reversal Rates at 50% and 100% levels
    for mult in [0.5, 1.0, 1.5]:
        mult_touches = touches_df[touches_df['multiple'] == mult]
        print(f"\n[Level {mult*100:.0f}%]")
        
        for method in mult_touches['method'].unique():
            m_data = mult_touches[mult_touches['method'] == method]
            total_u = m_data['touched_upper'].sum()
            rev_u = m_data['reversed_upper'].sum()
            total_l = m_data['touched_lower'].sum()
            rev_l = m_data['reversed_lower'].sum()
            
            if total_u + total_l > 0:
                rev_rate = (rev_u + rev_l) / (total_u + total_l) * 100
                print(f"  {method:<25} | Touch: {total_u+total_l:>3} | Rev Rate: {rev_rate:>5.1f}%")
    
    # ==========================================
    # SECTION 3: OPTIONS STRATEGY RECOMMENDATIONS
    # ==========================================
    
    print("\n" + "="*80)
    print("SECTION 3: OPTIONS STRATEGY RECOMMENDATIONS")
    print("="*80)
    
    # Iron Condor Wings
    print("\n[IRON CONDOR WING PLACEMENT]")
    print("Use these levels as short strike targets for high-probability selling:")
    
    for method in ['synth_vix_100_open', 'straddle_100_close', 'vix_scaled_close']:
        m_data = summary_df[summary_df['method'] == method]
        
        contain_100 = m_data[m_data['multiple'] == 1.0]['containment_pct'].values
        contain_127 = m_data[m_data['multiple'] == 1.272]['containment_pct'].values
        contain_150 = m_data[m_data['multiple'] == 1.5]['containment_pct'].values
        
        if len(contain_100) > 0 and len(contain_150) > 0:
            print(f"\n  {method}:")
            print(f"    Short Strike @ 100% EM: {contain_100[0]:.1f}% Prob of Profit")
            if len(contain_127) > 0:
                print(f"    Short Strike @ 127% EM: {contain_127[0]:.1f}% Prob of Profit")
            print(f"    Short Strike @ 150% EM: {contain_150[0]:.1f}% Prob of Profit")
    
    # Straddle/Strangle Analysis
    print("\n[STRADDLE PRICING ANALYSIS]")
    print("Theoretical edge for ATM straddle sellers:")
    
    for method in ['synth_vix_100_open', 'straddle_100_close']:
        m_perf = perf_df[(perf_df['method'] == method) & (perf_df['multiple'] == 1.0)]
        contained = m_perf['contained'].mean() * 100
        avg_mfe = m_perf['mfe_mult'].mean()
        avg_mae = m_perf['mae_mult'].mean()
        
        print(f"\n  {method}:")
        print(f"    Win Rate (Contained): {contained:.1f}%")
        print(f"    Avg MFE Multiple: {avg_mfe:.3f}")
        print(f"    Avg MAE Multiple: {avg_mae:.3f}")
        print(f"    Implied Edge: Price typically uses {(avg_mfe + avg_mae)/2 * 100:.1f}% of the EM")
    
    # ==========================================
    # SECTION 4: DIRECT TRADING RECOMMENDATIONS
    # ==========================================
    
    print("\n" + "="*80)
    print("SECTION 4: DIRECT TRADING (SPY/ES) RECOMMENDATIONS")
    print("="*80)
    
    # Best method for intraday
    best_method = 'synth_vix_100_open'
    
    print(f"\n[RECOMMENDED METHOD: {best_method}]")
    print("This method uses VIX at the 9:30 AM open, anchored to the Open price.")
    
    # Get statistics
    best_summary = summary_df[summary_df['method'] == best_method]
    
    print("\n[LEVEL USAGE TABLE]")
    print(f"{'Level':<10} | {'Containment':<12} | {'Med MFE':<10} | {'Med MAE':<10} | {'Use Case'}")
    print("-" * 70)
    
    use_cases = {
        0.5: "Initial Target / Speed Bump",
        0.618: "Fib Retracement Target",
        1.0: "Hard Boundary / Stop Zone",
        1.272: "Extension Target (Trend)",
        1.5: "Extreme Move / Fade Zone",
        1.618: "Golden Ratio Exhaustion",
        2.0: "Black Swan / Never Fade"
    }
    
    for _, row in best_summary.iterrows():
        mult = row['multiple']
        use = use_cases.get(mult, "")
        print(f"{mult*100:>5.1f}%    | {row['containment_pct']:>10.1f}% | {row['median_mfe']:>9.4f} | {row['median_mae']:>9.4f} | {use}")
    
    # ==========================================
    # SECTION 5: TRADING PLAYBOOK
    # ==========================================
    
    print("\n" + "="*80)
    print("SECTION 5: INTRADAY TRADING PLAYBOOK")
    print("="*80)
    
    print("""
[SETUP: Calculate EM at 9:30 AM]
  1. Get VIX value at 9:30 AM (first 5m bar)
  2. Calculate: EM = Open * (VIX/100) * sqrt(1/252) * 2.0

[LEVEL MARKERS]
  50% EM Upper/Lower:   First "speed bump" targets
  100% EM Upper/Lower:  Primary boundary (97.8% containment)
  150% EM Upper/Lower:  Extreme fade zone (99.6% containment)

[ENTRY STRATEGIES]
  MEAN REVERSION:
    - Enter LONG when price touches 50% EM Lower and shows reversal
    - Stop: Below 100% EM Lower
    - Target: Open Price

  BREAKOUT:
    - If 50% EM breaks with momentum, target 100% EM
    - If 100% EM breaks, fade at 127% or 150% EM

  FADE EXTREME:
    - If price reaches 150% EM, fade aggressively
    - Only 0.4% of days exceed this level

[OPTIONS OVERLAY]
  IRON CONDOR: Short 100% EM, Long 150% EM -> 97%+ POP
  IRON FLY: Short ATM Straddle -> Price uses ~35% of EM on average
  JADE LIZARD: Sell Put @ 100% EM, Call Spread @ 127%-150% EM
""")
    
    print("\n" + "="*80)
    print("=== ANALYSIS COMPLETE ===")
    print("="*80)

if __name__ == "__main__":
    analyze_for_trading()
