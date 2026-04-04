
import pandas as pd
import numpy as np
import glob
import os

# Configuration
ITERATIONS = 2500
CONFIDENCE_LEVEL = 95
# Target specific file patterns based on User Request
TARGETS = {
    "Fixed Mode": "*24edf.xlsx",
    "Trailing Mode": "*467b7.xlsx"
}

def load_trades(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    # If multiple, take the newest
    files.sort(key=os.path.getmtime, reverse=True)
    f = files[0]
    
    try:
        xl = pd.ExcelFile(f)
        sheet = next((s for s in xl.sheet_names if s.lower() == "list of trades"), "List of trades")
        df = pd.read_excel(f, sheet_name=sheet)
        # We only need Net P&L USD
        if 'Net P&L USD' in df.columns:
            return df['Net P&L USD'].values
        else:
            print(f"Error: 'Net P&L USD' not found in {f}")
            return None
    except Exception as e:
        print(f"Error loading {f}: {e}")
        return None

def calc_drawdown(equity_curve):
    peak = np.maximum.accumulate(equity_curve)
    drawdown = equity_curve - peak
    return drawdown.min()

def run_monte_carlo(pnl_array, name):
    print(f"\n--- Running Monte Carlo ({ITERATIONS} runs) for {name} ---")
    
    all_final_equity = []
    all_max_dd = []
    
    # Original Stats
    orig_equity = np.cumsum(pnl_array)
    orig_total = orig_equity[-1]
    orig_dd = calc_drawdown(orig_equity)
    
    print(f"Original >> Total P&L: ${orig_total:,.0f} | Max DD: ${orig_dd:,.0f}")
    
    for i in range(ITERATIONS):
        # Shuffle trades
        shuffled = np.random.permutation(pnl_array)
        eq = np.cumsum(shuffled)
        
        all_final_equity.append(eq[-1]) # Should be same as original sum, but good sanity check? 
        # Actually sum is invariant to order, so Final Equity is constant!
        # Wait, Monte Carlo for *equity curve* usually implies assessing Drawdown risk.
        # Net Profit is constant in simple shuffling. 
        # To simulate *market conditions*, we would resample with replacement.
        # But for "Sequence Risk" (which is what we care about for Drawdown), shuffling is correct.
        # Let's do Shuffling (Sequence Risk) for Drawdown analysis.
        
        all_max_dd.append(calc_drawdown(eq))

    # Drawdown Stats
    dd_p95 = np.percentile(all_max_dd, 5) # 5th percentile (worst case essentially, since DD is negative)
    dd_median = np.median(all_max_dd)
    dd_p05 = np.percentile(all_max_dd, 95) # 95th percentile (best case)
    
    return {
        "name": name,
        "orig_dd": orig_dd,
        "dd_median": dd_median,
        "dd_p95": dd_p95, # Logic: -2000 is "smaller" than -1000, so 5th percentile is the "deep" tail.
        "prob_dd_2k": np.sum(np.array(all_max_dd) < -2000) / ITERATIONS * 100,
        "prob_dd_3k": np.sum(np.array(all_max_dd) < -3000) / ITERATIONS * 100
    }

results = []

for label, pattern in TARGETS.items():
    pnl = load_trades(pattern)
    if pnl is not None:
        stats = run_monte_carlo(pnl, label)
        results.append(stats)
    else:
        print(f"Could not load data for {label}")

print("\n\n=== MONTE CARLO RESULTS (SEQUENCE RISK) ===")
print(f"Iterations: {ITERATIONS}")
print("-" * 60)
print(f"{'Strategy':<15} | {'Orig DD':<10} | {'Median DD':<10} | {'95% Worst DD':<12} | {'Prob > $2k':<10}")
print("-" * 60)

for r in results:
    print(f"{r['name']:<15} | ${r['orig_dd']:<9,.0f} | ${r['dd_median']:<9,.0f} | ${r['dd_p95']:<11,.0f} | {r['prob_dd_2k']:.1f}%")

print("-" * 60)
