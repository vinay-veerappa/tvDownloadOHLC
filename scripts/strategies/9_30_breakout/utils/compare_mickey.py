
import pandas as pd
import numpy as np
import os

def load_mickey():
    path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\Mickey 0930CPT Backtest - dont touch 0930 PNL.txt.csv"
    df = pd.read_csv(path, header=None, low_memory=False)
    
    mickey_data = []
    for idx, row in df.iterrows():
        date_str = str(row[1])
        try:
            date = pd.to_datetime(date_str)
            if date.year < 2000 or date.year > 2026: continue
            
            direction = str(row[6]).lower()
            if direction not in ['long', 'short']: continue
            
            entry = float(str(row[3]).replace('"', '').replace(',', ''))
            exit_p = float(str(row[5]).replace('"', '').replace(',', ''))
            
            if direction == 'long':
                pts = exit_p - entry
            else:
                pts = entry - exit_p
                
            mickey_data.append({
                'Date': date.date(),
                'Direction_M': direction.upper(),
                'Entry_M': entry,
                'Exit_M': exit_p,
                'PnL_Pts_M': pts,
                'Result_M': 'WIN' if pts > 0 else 'LOSS'
            })
        except:
            continue
            
    return pd.DataFrame(mickey_data)

def compare():
    mickey_df = load_mickey()
    print(f"Loaded {len(mickey_df)} Mickey trades.")
    
    our_trades_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    our_df = pd.read_csv(our_trades_path)
    our_df['Date'] = pd.to_datetime(our_df['Date']).dt.date
    our_df = our_df[our_df['Variant'] == 'Base_1Att'].copy()
    
    # Prefix our columns to avoid any issues
    our_df = our_df.rename(columns={'Direction': 'Direction_O', 'Result': 'Result_O', 'PnL_Pts': 'PnL_Pts_O'})

    comparison = pd.merge(mickey_df, our_df, on='Date', how='inner')
    print(f"Common dates: {len(comparison)}")
    
    if len(comparison) == 0:
        print("No overlapping trades found.")
        return
        
    same_dir = comparison[comparison['Direction_M'] == comparison['Direction_O']]
    win_m = (comparison['Result_M'] == 'WIN').mean()
    win_o = (comparison['Result_O'] == 'WIN').mean()
    
    print(f"\n--- Comparative Performance ---")
    print(f"Mickey Win Rate: {win_m:.1%}")
    print(f"Strategy Win Rate: {win_o:.1%}")
    print(f"Directional Alignment: {len(same_dir)/len(comparison):.1%}")
    
    matched_outcome = comparison[comparison['Result_M'] == comparison['Result_O']]
    print(f"Outcome Correlation (Matched W/L): {len(matched_outcome)/len(comparison):.1%}")
    
    diffs = comparison[comparison['Result_M'] != comparison['Result_O']]
    print(f"\nSample Discrepancies (First 5):")
    print(diffs[['Date', 'Direction_M', 'Direction_O', 'Result_M', 'Result_O', 'PnL_Pts_M', 'PnL_Pts_O']].head(5))

if __name__ == "__main__":
    compare()
