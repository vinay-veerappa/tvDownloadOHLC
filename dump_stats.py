import pandas as pd
import numpy as np

def p_nearest(series, p):
    if len(series) == 0: return np.nan
    return np.percentile(series, p, method='nearest')

import runpy
glbls = runpy.run_path('scripts/indicators-pine/daily-ny-levels/verify_classification.py')
bulls = glbls['bulls']
bears = glbls['bears']
bull_wins = glbls['bull_wins']
bear_wins = glbls['bear_wins']
bull_fakes = bulls[bulls['fakeout'] == True]

def check(name, val, target_pct=None):
    print(f"{name:<30}: {val:.4f}%")
    if target_pct is not None and abs(val - target_pct) < 0.005:
        print(f"*** MATCH *** {name} == {target_pct}")

print("--- MAE (Breakout Px) ---")
check("Bulls Win P80", p_nearest(bull_wins['mae'], 80), 0.095)
check("Bulls Loss P80", p_nearest(bulls[~bulls['win']]['mae'], 80))
check("Bulls All P80", p_nearest(bulls['mae'], 80), 0.095)
check("Bears Win P80", p_nearest(bear_wins['mae'], 80))

print("--- MAE P50 ---")
check("Bulls All P50 (BO)", p_nearest(bulls['mae'], 50), 0.123)
check("Bears All P50 (BO)", p_nearest(bears['mae'], 50), 0.183)
check("Bulls Win P50 (BO)", p_nearest(bull_wins['mae'], 50), 0.123)
check("Bears Win P50 (BO)", p_nearest(bear_wins['mae'], 50), 0.183)
check("Bulls Loss P50 (BO)", p_nearest(bulls[~bulls['win']]['mae'], 50), 0.123)

print("--- Pullback (P25) ---")
check("Bulls All P25 (BO)", p_nearest(bulls['mae'], 25))
check("Bulls Win P25 (BO)", p_nearest(bull_wins['mae'], 25))

print("--- Fakeout (P25-P50) ---")
check("Bulls Fake P25 (OR)", p_nearest(bull_fakes['session_mae'], 25))
check("Bulls Fake P50 (OR)", p_nearest(bull_fakes['session_mae'], 50))
check("Bulls Fake P25 (BO)", p_nearest(bull_fakes['mae'], 25))
check("Bulls Fake P50 (BO)", p_nearest(bull_fakes['mae'], 50))

print("--- MFE P20 (Cashflow) ---")
check("Bulls All P20 (BO)", p_nearest(bulls['mfe'], 20))
check("Bulls Win P20 (BO)", p_nearest(bull_wins['mfe'], 20))

print("--- MFE P50 (Fakeouts - Pivot) ---")
check("Bulls Fake P50 (BO)", p_nearest(bull_fakes['mfe'], 50))
check("Bulls Fake P75 (BO)", p_nearest(bull_fakes['mfe'], 75), 0.111)
check("Bulls Fake P50 (OR)", p_nearest(bull_fakes['session_mfe'], 50))
