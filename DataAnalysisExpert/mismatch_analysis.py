"""
CRITICAL DISCOVERY: Mismatch between Directional Prediction and Trade Execution

Python Analysis = "Did PM break a new extreme?" (YES/NO directional)
Pine Strategy = "Did price hit my TP before hitting my SL?" (WIN/LOSS trade)

These are NOT the same thing!
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import time

def load_data(ticker):
    """Load the analysis data"""
    csv_path = Path(f'scripts/nqstats/results/deep_analysis_{ticker}_2020_2025.csv')
    df = pd.read_csv(csv_path)
    df['Date'] = pd.to_datetime(df['Date'])
    df['Prediction_Correct'] = df['Prediction_Correct'].astype(str).str.lower().isin(['true', '1', 'yes'])
    return df

def analyze_mismatch(df, ticker):
    """
    Check what Python measures vs what Pine trades:
    
    Python: Expected_Dir == Actual_PM_Dir (macro direction)
    Pine: Entry on retrace + TP at range_extreme*0.5 + SL at range_extreme - buffer
    """
    
    print(f"\n{'='*100}")
    print(f"{ticker}: DIRECTIONAL ACCURACY vs TRADE PROFITABILITY")
    print(f"{'='*100}\n")
    
    # Group by directional prediction correctness
    correct = df[df['Prediction_Correct'] == True]
    wrong = df[df['Prediction_Correct'] == False]
    
    print(f"Directional Accuracy (PM broke new extreme as expected):")
    print(f"  Correct: {len(correct)} days ({len(correct)/len(df)*100:.1f}%)")
    print(f"  Wrong:   {len(wrong)} days ({len(wrong)/len(df)*100:.1f}%)")
    
    # Now analyze what that means for actual trades
    print(f"\nBut what does 'directionally correct' actually tell you?\n")
    
    print(f"The Python analysis ONLY answers: 'Did PM break a new extreme?'")
    print(f"It does NOT answer: 'Did your trade TP before hitting SL?'\n")
    
    # Show examples
    print(f"SCENARIO ANALYSIS:")
    print(f"─" * 100)
    print(f"\n1. DIRECTIONALLY CORRECT (Prediction_Correct = TRUE)")
    print(f"   But did you actually profit?")
    
    if len(correct) > 0:
        sample = correct.iloc[0]
        print(f"\n   Example Day: {sample['Date'].date()}")
        print(f"   AM High:  {sample['AM_Range']:.1f} range")
        print(f"   Expected: {sample['Expected_Dir']}")
        print(f"   Actual PM: {sample['Actual_PM_Dir']} ✓ (direction correct)")
        print(f"\n   Question: But at what PRICE did the move happen?")
        print(f"   - If move happened at 15:30 (end of day), your TP hit early")
        print(f"   - If move was gradual, you might have hit SL first")
        print(f"   - Entry level determines if you even get filled on retrace")
    
    print(f"\n2. DIRECTIONALLY WRONG (Prediction_Correct = FALSE)")
    print(f"   {len(wrong)} cases where PM didn't move as expected")
    print(f"   -> 100% of these are losses (no alternative exit)")
    
    # Key insight
    print(f"\n{'='*100}")
    print(f"KEY INSIGHT: The 60% win stat is MISLEADING")
    print(f"{'='*100}\n")
    
    print(f"What Python measures: 'Market moves my way' = 60% of the time")
    print(f"What Pine needs: 'TP hits before SL' = ? % of the time")
    print(f"\nThese are DIFFERENT because:")
    print(f"  1. Your TP is at 50% of range (Halfway Back)")
    print(f"  2. You enter at retracement, not immediately")
    print(f"  3. SL is 30 points (usually 12-15% of range)")
    print(f"  4. If PM move is slow, you hit SL first")
    print(f"  5. If entry never happens (no retrace), you never trade")
    
    # Data quality check
    print(f"\nDATA QUALITY CHECK:")
    print(f"─" * 100)
    
    # Check range statistics
    print(f"\nAvg AM Range: {df['AM_Range'].mean():.1f} pts")
    print(f"Avg Time Gap: {df['Time_Gap_Minutes'].mean():.1f} min")
    
    # Group by whether time-gap was in optimal window
    optimal_tg = df[(df['Time_Gap_Minutes'] >= 120) & (df['Time_Gap_Minutes'] <= 240)]
    print(f"\nTrades with 120-240 min time-gap:")
    print(f"  Count: {len(optimal_tg)} / {len(df)}")
    print(f"  Accuracy: {optimal_tg['Prediction_Correct'].mean()*100:.1f}%")
    
    # Check entry window state
    print(f"\nEntry Window Analysis:")
    above = df[df['Entry_vs_Midpoint'] == 'ABOVE']
    below = df[df['Entry_vs_Midpoint'] == 'BELOW']
    
    print(f"  Entry close ABOVE midpoint: {above['Prediction_Correct'].mean()*100:.1f}% acc ({len(above)} days)")
    print(f"  Entry close BELOW midpoint: {below['Prediction_Correct'].mean()*100:.1f}% acc ({len(below)} days)")
    
    # The real question
    print(f"\n{'='*100}")
    print(f"WHAT YOU SHOULD CHECK:")
    print(f"{'='*100}\n")
    print(f"1. In your Pine backtest, what % of entries are triggering?")
    print(f"   (If only 50% trigger due to no retrace, you cut your edge in half)")
    print(f"\n2. For entries that trigger, what % hit TP vs SL?")
    print(f"   (This is what matters, NOT the 60% directional accuracy)")
    print(f"\n3. Are you comparing:")
    print(f"   ✗ Python macro analysis (does market go right way?)")
    print(f"   ✗ Pine micro execution (do you hit TP first?)")
    print(f"\n4. The TP level is critical:")
    print(f"   ✓ Halfway Back = ~20-25pts on NQ = 50% of your SL")
    print(f"   ✓ This is TOO TIGHT - need bigger TP for 60% to work")

def main():
    for ticker in ['NQ1', 'ES1']:
        df = load_data(ticker)
        analyze_mismatch(df, ticker)

if __name__ == "__main__":
    main()
