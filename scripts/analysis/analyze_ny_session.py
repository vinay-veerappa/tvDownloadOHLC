
import pandas as pd
import numpy as np
from pathlib import Path

DATA_PATH = Path("data/derived/NQ1_herman_stats.parquet")

def load_data():
    if not DATA_PATH.exists():
        print(f"Error: {DATA_PATH} not found.")
        return None
    return pd.read_parquet(DATA_PATH)

def calc_prob(df, condition_mask, target_mask, name=""):
    # Fix: Use combined mask on original DF to avoid index alignment warnings
    subset_mask = np.array(condition_mask)
    n = subset_mask.sum()
    
    if n == 0:
        return 0.0, 0
        
    # Target is instances where BOTH condition AND target are true
    # (Assuming target_mask is the Event occurring, given the Condition)
    success_mask = condition_mask & target_mask
    k = success_mask.sum()
    
    prob = (k / n) * 100
    return prob, n

def analyze_ny_am(df):
    print("\n" + "="*50)
    print("ANALYSIS: NY AM SESSION (07:00 - 10:00 ET)")
    print("="*50)
    
    # 1. Sweep Probabilities
    # Does NY AM Sweep London?
    sw_h, n = calc_prob(df, [True]*len(df), df['ny_am_sweeps_lon_h'], "Sweep Lon High")
    sw_l, _ = calc_prob(df, [True]*len(df), df['ny_am_sweeps_lon_l'], "Sweep Lon Low")
    
    print(f"1. NY AM Sweeps London Liquidity:")
    print(f"   • Sweeps London High: {sw_h:.1f}%")
    print(f"   • Sweeps London Low:  {sw_l:.1f}%")
    
    # 2. State Machine: If Sweep -> Then What?
    # Scenario A: Bullish Setup (London Low Swept)
    # If NY AM Sweeps London LOW...
    # -> Continuation (Bearish): Closes < Open (Red Candle)
    # -> Reversal (Bullish): Closes > Open (Green Candle) - Classic ICT Turtle Soup
    
    # Define Close Direction for NY AM
    df['ny_am_bullish'] = df['ny_am_close'] > df['ny_am_open']
    df['ny_am_bearish'] = df['ny_am_close'] < df['ny_am_open']
    
    # Setup: Sweep Low
    sl_continuation, n_sl = calc_prob(df, df['ny_am_sweeps_lon_l'], df['ny_am_bearish']) 
    sl_reversal, _      = calc_prob(df, df['ny_am_sweeps_lon_l'], df['ny_am_bullish'])
    
    print(f"\n2. Setup: NY AM Sweeps London LOW (n={n_sl}):")
    print(f"   • Reversal (Bullish Close): {sl_reversal:.1f}% (Buy Signal)")
    print(f"   • Continuation (Bearish):   {sl_continuation:.1f}%")
    
    # Setup: Sweep High
    sh_continuation, n_sh = calc_prob(df, df['ny_am_sweeps_lon_h'], df['ny_am_bullish'])
    sh_reversal, _      = calc_prob(df, df['ny_am_sweeps_lon_h'], df['ny_am_bearish'])
    
    print(f"\n3. Setup: NY AM Sweeps London HIGH (n={n_sh}):")
    print(f"   • Reversal (Bearish Close): {sh_reversal:.1f}% (Sell Signal)")
    print(f"   • Continuation (Bullish):   {sh_continuation:.1f}%")

def analyze_ny_lunch(df):
    print("\n" + "="*50)
    print("ANALYSIS: NY LUNCH REVERSALS (12:00 - 13:00 ET)")
    print("="*50)
    
    # Question: If NY AM was Strong (Trend), does Lunch reverse it?
    
    # Context: NY AM was Bullish (Green)
    am_bull = df[df['ny_am_bullish']]
    
    # Did Lunch Sweep AM High? (Expansion? or Trap?)
    bull_sweep_high, n_bun = calc_prob(df, df['ny_am_bullish'], df['ny_lunch_sweeps_am_h'])
    
    # If Lunch swept High, did it reverse (Close < Open)?
    # Need lunch direction
    df['ny_lunch_bearish'] = df['ny_lunch_close'] < df['ny_lunch_open']
    df['ny_lunch_bullish'] = df['ny_lunch_close'] > df['ny_lunch_open']
    
    # Setup: AM Bullish + Lunch Sweeps AM High
    mask_setup_bull = df['ny_am_bullish'] & df['ny_lunch_sweeps_am_h']
    lunch_rev_bull, n_setup_bull = calc_prob(df, mask_setup_bull, df['ny_lunch_bearish'])
    
    print(f"1. Context: NY AM Bullish (Green)")
    print(f"   • Lunch Sweeps AM High: {bull_sweep_high:.1f}% (Continuation Attempt)")
    print(f"   • IF Lunch Sweeps High -> It Reverses (Red): {lunch_rev_bull:.1f}% (n={n_setup_bull})")
    
    # Context: NY AM Bearish (Red)
    mask_setup_bear = df['ny_am_bearish'] & df['ny_lunch_sweeps_am_l']
    lunch_rev_bear, n_setup_bear = calc_prob(df, mask_setup_bear, df['ny_lunch_bullish'])
    
    print(f"\n2. Context: NY AM Bearish (Red)")
    print(f"   • IF Lunch Sweeps Low -> It Reverses (Green): {lunch_rev_bear:.1f}% (n={n_setup_bear})")

def main():
    df = load_data()
    if df is None: return
    
    analyze_ny_am(df)
    analyze_ny_lunch(df)

if __name__ == "__main__":
    main()
