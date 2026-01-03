import pandas as pd
import numpy as np

# Simulate the Logic Flaw
# Scenario:
# Trade 1: Enters. 
# TP1 (50% qty) hits +0.05% profit. -> "Last Trade Profit > 0" -> hasWonToday = True.
# Runner (50% qty) hits SL (e.g., -0.25% loss). -> Net Loss for Trade 1.
# Trade 2: New signal appears. 
# Logic Check: "not hasWonToday". 
# Result: BLOCKED because hasWonToday is True from the tiny TP1.

def analyze_logic_flaw():
    print("=== STOP AFTER WIN LOGIC FLAW ANALYSIS ===")
    
    # Simulation Parameters
    tp1_level = 0.0005 # 0.05%
    sl_level = 0.0025  # 0.25% (Range size)
    
    # Trade Outcome
    pos_size = 2 # 2 contracts
    tp1_qty = 1
    runner_qty = 1
    
    tp1_pnl = tp1_qty * tp1_level
    runner_pnl = runner_qty * -sl_level
    
    net_pnl = tp1_pnl + runner_pnl
    
    print(f"TP1 Gain: +{tp1_pnl:.4f} (Triggered 'Win')")
    print(f"Runner Loss: -{sl_level:.4f}")
    print(f"Net Trade PnL: {net_pnl:.4f}")
    
    if tp1_pnl > 0:
        print("ALERT: 'StopAfterWin' flag triggered by TP1.")
        print("RESULT: Subsequent profitable re-entries are BLOCKED.")
        print("VERDICT: This logic guarantees locking in small losses and missing recovery trades.")

if __name__ == "__main__":
    analyze_logic_flaw()
