
"""
Prop Firm Passage Simulator
===========================
Estimates time to reach Profit Target ($3000) vs Drawdown Limit ($2000).
Based on historical trade data from the 'Superstar' configuration.

Methodology:
1. Load trades from the best backtest.
2. Run Monte Carlo simulations (bootstrapping daily P&L).
3. Determine success rate and average days to pass for 1, 2, 3, 4 contracts.
"""

import pandas as pd
import numpy as np
import glob
import os

# Target File: The "Superstar" Config
FILE_PATTERN = r"ORB_V3_Doji*8f5bf.xlsx"
TARGET = 3000
DRAWDOWN_LIMIT = 2000

def run_simulation():
    files = glob.glob(FILE_PATTERN)
    if not files:
        print("Error: Could not find the specific backtest file.")
        return

    path = files[0]
    print(f"Loading Trade Data: {os.path.basename(path)}")
    
    try:
        df = pd.read_excel(path, sheet_name="List of trades")
        df.columns = df.columns.str.strip()
        
        # Calculate Daily P&L (1 Contract)
        df['dt'] = pd.to_datetime(df['Date and time'])
        df['date'] = df['dt'].dt.date
        daily_pnl = df.groupby('date')['Net P&L USD'].sum().values
        
        print(f"loaded {len(daily_pnl)} trading days.")
        
        # Simulation Settings
        SIMULATIONS = 10000
        SCALES = [1, 2, 3, 4, 5]
        
        print(f"\n--- SIMULATION RESULTS (Target: ${TARGET}, MaxDD: ${DRAWDOWN_LIMIT}) ---")
        print(f"{'Contracts':<10} | {'Pass Rate':<10} | {'Avg Days':<10} | {'Median Days':<12} | {'Risk of Ruin':<12}")
        print("-" * 65)
        
        for scale in SCALES:
            scaled_pnl = daily_pnl * scale
            
            pass_count = 0
            ruin_count = 0
            days_to_pass = []
            
            for _ in range(SIMULATIONS):
                # Bootstrap Resample (Random sequence of days)
                # We simulate up to 250 days (1 year)
                sim_days = np.random.choice(scaled_pnl, size=250, replace=True)
                
                # Calculate Equity Curve
                equity = np.cumsum(sim_days)
                
                # Check for Target
                pass_idx = np.where(equity >= TARGET)[0]
                first_pass = pass_idx[0] if len(pass_idx) > 0 else 999
                
                # Check for Drawdown (Trailing)
                # Trailing DD logic: Max Equity - Current Equity
                running_max = np.maximum.accumulate(np.insert(equity, 0, 0))[:-1] # shift alignment
                # Actually standard way:
                # equity_curve = [0, d1, d1+d2, ...]
                eq_curve = np.concatenate(([0], equity))
                running_pk = np.maximum.accumulate(eq_curve)
                dd = eq_curve - running_pk
                
                # Where did we breach?
                ruin_idx = np.where(dd <= -DRAWDOWN_LIMIT)[0]
                first_ruin = ruin_idx[0] if len(ruin_idx) > 0 else 999
                
                # The Outcome
                if first_pass < first_ruin and first_pass < 250:
                    pass_count += 1
                    days_to_pass.append(first_pass + 1) # 0-indexed
                elif first_ruin < first_pass and first_ruin < 250:
                    ruin_count += 1
                else:
                    # Timeout (neither reached in 250 days)
                    pass 
            
            pass_rate = (pass_count / SIMULATIONS) * 100
            ruin_rate = (ruin_count / SIMULATIONS) * 100
            avg_days = np.mean(days_to_pass) if days_to_pass else 0
            med_days = np.median(days_to_pass) if days_to_pass else 0
            
            print(f"{scale:<10} | {pass_rate:6.1f}% | {avg_days:8.1f} | {med_days:10.1f} | {ruin_rate:10.1f}%")

    except Exception as e:
        print(f"Simulation Error: {e}")

if __name__ == "__main__":
    run_simulation()
