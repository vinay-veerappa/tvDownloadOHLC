
import pandas as pd
import numpy as np

def analyze(csv_file, name):
    try:
        df = pd.read_csv(csv_file)
    except:
        print(f"[{name}] File not found.")
        return None
        
    # Group by TradeNum or Entry Time to reconstruct "Whole Trades" from splits
    # Since we have splits (TP1, TP2, SL), we need agg P&L per trade.
    # Note: 'Gross P&L %' is per split.
    # To get Trade P&L, we need weights.
    # My python script didn't save weight in CSV explicitly, but we know the structure.
    # Actually, simpler: just sum all P&L % rows. This gives "Total Portfolio Return" unweighted?
    # No, that's wrong because splits are partials.
    # 
    # Correct Way:
    # A "Trade" consists of multiple rows (splits).
    # We sum the Gross P&L % * Weight for the trade.
    # BUT, the script output 'Gross P&L %' is (Exit-Entry)/Entry.
    # It didn't account for weight in the CSV output column value.
    # However, if we average the P&L of all rows, it's roughly the trade P&L?
    # No.
    # Let's effectively assume 1 unit traded.
    # Each split handles a fraction.
    
    # Let's simplify:
    # Win Rate: Any trade that ended > 0?
    # Or just "Sum of P&L %" for the dataset.
    
    # Let's assume equal weights for simplicity of "Directional Quality" check.
    # Or better: Group by 'Entry Time'.
    # For each group:
    #   Calculate weighted average exit?
    #   The script didn't save the weight.
    #   But we know splits are [0.5, 0.25, 0.25].
    #   This makes exact P&L hard to reconstruct purely from CSV without mapping types.
    
    # Fallback: Count "SL Hit" vs "Target Hit".
    # Losses usually end in SL Hit for remaining portion.
    # If ANY part hits SL, is it a loser? Not necessarily (Breakeven).
    
    # Metric 1: Total Raw P&L Sum (Sum of % moves captured).
    # This is a proxy for "Total Points Captured". 
    # Winners contribute, Losers subtract.
    
    total_raw_pnl = df['Gross P&L %'].sum()
    
    # Metric 2: Win Rate (Rows).
    # Count rows > 0.
    wins = len(df[df['Gross P&L %'] > 0])
    losses = len(df[df['Gross P&L %'] <= 0])
    total = len(df)
    win_rate = (wins / total) * 100 if total > 0 else 0
    
    # Metric 3: Profit Factor (Gross Win / Gross Loss)
    gross_win = df[df['Gross P&L %'] > 0]['Gross P&L %'].sum()
    gross_loss = abs(df[df['Gross P&L %'] < 0]['Gross P&L %'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else 0
    
    # Metric 4: Trade Count (Unique Entries)
    unique_trades = df['Entry Time'].nunique()
    
    print(f"--- {name} ---")
    print(f"Unique Trades: {unique_trades}")
    print(f"Total Raw P&L Sum: {total_raw_pnl:.4f}")
    print(f"Row Win Rate: {win_rate:.2f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Avg P&L per Row: {total_raw_pnl/total:.6f}\n")
    
    return {'pf': pf, 'pnl': total_raw_pnl}

print("COMPARISON: BASELINE vs VWAP FILTER\n")
base = analyze("local_backtest_results.csv", "BASELINE (No Filter)")
scen = analyze("scenario_vwap_results.csv", "VWAP FILTER")

if base and scen:
    diff_pnl = ((scen['pnl'] - base['pnl']) / abs(base['pnl'])) * 100
    print(f"Impact on Total P&L: {diff_pnl:+.2f}%")
