
import pandas as pd
import sys

def main():
    try:
        df = pd.read_csv('backtest_comparison.csv')
    except FileNotFoundError:
        print("Error: backtest_comparison.csv not found.")
        return

    print("--- Analysis Report ---")
    
    total_trades = len(df)
    print(f"Total Trades Analyzed: {total_trades}")

    # 1. Overall Performance
    base_pnl = df['Base_PnL'].sum()
    new_pnl = df['New_PnL'].sum()
    print(f"\nTotal PnL:")
    print(f"  Base: {base_pnl:.2f}")
    print(f"  New:  {new_pnl:.2f}")
    print(f"  Diff: {new_pnl - base_pnl:.2f}")

    # 2. Win Rate
    base_wins = df[df['Base_Result'] == 'WIN'].shape[0]
    new_wins = df[df['New_Result'] == 'WIN'].shape[0]
    print(f"\nWin Rate:")
    print(f"  Base: {base_wins}/{total_trades} ({base_wins/total_trades*100:.1f}%)")
    print(f"  New:  {new_wins}/{total_trades} ({new_wins/total_trades*100:.1f}%)")

    # 3. Affected Trades
    # Trades where PnL Diff is not 0
    affected = df[df['PnL_Diff'] != 0]
    print(f"\nAffected Trades (where outcome changed): {len(affected)}")
    
    if len(affected) > 0:
        affected_diff = affected['PnL_Diff'].sum()
        print(f"  Net PnL Change on Affected Trades: {affected_diff:.2f}")
        print(f"  Avg PnL Change per Affected Trade: {affected_diff/len(affected):.2f}")

        # Did it save losses or cut wins?
        # Check trades where Base was LOSS and New was WIN (Saved Loss)
        saved_losses = affected[(affected['Base_Result'] == 'LOSS') & (affected['New_Result'] == 'WIN')]
        print(f"  Saved Losses (Loss -> Win): {len(saved_losses)}")
        
        # Check trades where Base was WIN and New was LOSS (Cut Win)
        cut_wins = affected[(affected['Base_Result'] == 'WIN') & (affected['New_Result'] == 'LOSS')]
        print(f"  Cut Wins (Win -> Loss): {len(cut_wins)}")

        # Check trades where Base was LOSS and New was "Less Loss" (Improved Loss)
        # i.e. Base PnL < New PnL < 0
        improved_losses = affected[(affected['Base_PnL'] < affected['New_PnL']) & (affected['New_PnL'] < 0)]
        print(f"  Reduced Losses (Loss -> Smaller Loss): {len(improved_losses)}")

        # Check trades where Base was WIN and New was "Less Win" (Reduced Win)
        reduced_wins = affected[(affected['Base_PnL'] > affected['New_PnL']) & (affected['New_PnL'] > 0)]
        print(f"  Reduced Wins (Win -> Smaller Win): {len(reduced_wins)}")

if __name__ == "__main__":
    main()
