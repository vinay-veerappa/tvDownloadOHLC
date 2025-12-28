
import pandas as pd
import numpy as np
import os

def load_mickey():
    path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\Mickey 0930CPT Backtest - dont touch 0930 PNL.txt.csv"
    # Data starts after header rows. Based on inspection, row 4 is the header start.
    df = pd.read_csv(path, header=None, low_memory=False, skiprows=4)
    
    # We need to map columns carefully based on the header we saw:
    # 1: Date, 3: Entry, 4: Stop, 5: TP/Exit, 6: Long/short, 7: MAE, 8: MFE
    
    mickey_data = []
    for idx, row in df.iterrows():
        try:
            date_str = str(row[1])
            if '/' not in date_str: continue
            date = pd.to_datetime(date_str)
            if date.year < 2008 or date.year > 2026: continue
            
            direction = str(row[6]).lower()
            if 'long' not in direction and 'short' not in direction: continue
            dir_str = 'LONG' if 'long' in direction else 'SHORT'
            
            entry = float(str(row[3]).replace('"', '').replace(',', ''))
            exit_p = float(str(row[5]).replace('"', '').replace(',', ''))
            
            # Mickey's MAE/MFE are in pts
            mae_m = float(str(row[7]).replace('"', '').replace(',', '')) if not pd.isna(row[7]) else 0
            mfe_m = float(str(row[8]).replace('"', '').replace(',', '')) if not pd.isna(row[8]) else 0
            
            pts = (exit_p - entry) if dir_str == 'LONG' else (entry - exit_p)
            
            mickey_data.append({
                'Date': date.date(),
                'Direction_M': dir_str,
                'Entry_M': entry,
                'Exit_M': exit_p,
                'MAE_M': mae_m,
                'MFE_M': mfe_m,
                'PnL_Pts_M': pts,
                'Result_M': 'WIN' if pts > 0 else 'LOSS'
            })
        except: continue
        
    return pd.DataFrame(mickey_data)

def compare_deep():
    mickey_df = load_mickey()
    our_trades_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    our_df = pd.read_csv(our_trades_path)
    our_df['Date'] = pd.to_datetime(our_df['Date']).dt.date
    # Use Base_1Att for core logic comparison
    our_df = our_df[our_df['Variant'] == 'Base_1Att'].copy()
    our_df = our_df.rename(columns={'Direction': 'Direction_O', 'Result': 'Result_O', 'PnL_Pts': 'PnL_Pts_O'})
    
    # Prefix our metrics
    our_df['MAE_Pts_O'] = our_df['MAE_Pct'] / 100 * our_df['Range_High'] # Approximation
    our_df['MFE_Pts_O'] = our_df['MFE_Pct'] / 100 * our_df['Range_High']
    
    comp = pd.merge(mickey_df, our_df, on='Date', how='inner')
    
    if len(comp) == 0:
        print("No match.")
        return

    print(f"--- Deep Comparison ({len(comp)} trades) ---")
    
    # 1. Entry Efficiency (MAE comparison)
    # Since prices are adjusted/unadjusted, let's look at MAE/Risk or MAE/Range
    comp['MAE_Ratio_M'] = comp['MAE_M'] / (comp['Range_High'] - comp['Range_Low'])
    comp['MAE_Ratio_O'] = comp['MAE_Pts_O'] / (comp['Range_High'] - comp['Range_Low'])
    
    print(f"Avg MAE Ratio (MAE/BoxSize): Mickey={comp['MAE_Ratio_M'].mean():.2f}, Strategy Tester={comp['MAE_Ratio_O'].mean():.2f}")
    
    # 2. Excursion Comparison
    # Is Mickey capturing more MFE?
    print(f"Avg MFE Captured: Mickey={comp['MFE_M'].mean():.2f} pts, Strategy Tester={comp['MFE_Pts_O'].mean():.2f} pts")
    
    # 3. Discrepancy Breakdown by Direction
    dir_match = (comp['Direction_M'] == comp['Direction_O']).mean()
    print(f"Directional Alignment: {dir_match:.1%}")
    
    # 4. Filter for same direction, look at why Mickey wins
    same_dir = comp[comp['Direction_M'] == comp['Direction_O']]
    print(f"\nTrade Performance (Same Direction trades: {len(same_dir)}):")
    print(f"Mickey Win Rate: {(same_dir['Result_M'] == 'WIN').mean():.1%}")
    print(f"Strategy Tester Win Rate: {(same_dir['Result_O'] == 'WIN').mean():.1%}")
    
    # 5. Analysis of Strategy Tester Losers that were Mickey Winners
    m_win_o_loss = same_dir[(same_dir['Result_M'] == 'WIN') & (same_dir['Result_O'] == 'LOSS')]
    print(f"\nMickey Wins / Strategy Tester Loses (Same Direction): {len(m_win_o_loss)}")
    print(f"Exit Reasons for Strategy Tester Loses: \n{m_win_o_loss['Exit_Reason'].value_counts()}")
    
    # 6. Check if Mickey's MAE is lower than our 0.12% heat filter
    # (0.12% of NQ ~ 20-25 pts)
    print(f"\nMickey trades hitting > 15 pts MAE: {(comp['MAE_M'] > 15).mean():.1%}")

if __name__ == "__main__":
    compare_deep()
