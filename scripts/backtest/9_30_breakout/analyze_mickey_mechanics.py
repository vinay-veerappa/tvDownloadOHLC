
import pandas as pd
import numpy as np
import os

def load_mickey():
    path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\Mickey 0930CPT Backtest - dont touch 0930 PNL.txt.csv"
    df = pd.read_csv(path, header=None, low_memory=False)
    mickey_data = []
    for idx, row in df.iterrows():
        try:
            date = pd.to_datetime(str(row[1]))
            if date.year < 2000 or date.year > 2026: continue
            direction = str(row[6]).lower()
            if direction not in ['long', 'short']: continue
            entry = float(str(row[3]).replace('"', '').replace(',', ''))
            stop = float(str(row[4]).replace('"', '').replace(',', ''))
            exit_p = float(str(row[5]).replace('"', '').replace(',', ''))
            risk = abs(entry - stop)
            reward = abs(exit_p - entry)
            rr = reward / risk if risk != 0 else 0
            pts = (exit_p - entry) if direction == 'long' else (entry - exit_p)
            mickey_data.append({
                'Date': date.date(),
                'Direction_M': direction.upper(),
                'Entry_M': entry, 'Stop_M': stop, 'Exit_M': exit_p,
                'Risk_M': risk, 'RR_M': rr, 'PnL_Pts_M': pts,
                'Result_M': 'WIN' if pts > 0 else 'LOSS'
            })
        except: continue
    return pd.DataFrame(mickey_data)

def analyze_mechanics():
    mickey_df = load_mickey()
    our_trades_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    our_df = pd.read_csv(our_trades_path)
    our_df['Date'] = pd.to_datetime(our_df['Date']).dt.date
    our_df = our_df[our_df['Variant'] == 'Base_1Att'].copy()
    our_df = our_df.rename(columns={'Direction': 'Direction_O', 'Result': 'Result_O', 'PnL_Pts': 'PnL_Pts_O'})
    
    comp = pd.merge(mickey_df, our_df, on='Date', how='inner')
    if len(comp) == 0:
        print("No overlap.")
        return

    comp['Range_Size_O'] = comp['Range_High'] - comp['Range_Low']
    print(f"--- Strategy Mechanic Comparison ({len(comp)} trades) ---")
    print(f"Avg Stop Distance: Mickey={comp['Risk_M'].mean():.2f}, Strategy Tester (Range)={comp['Range_Size_O'].mean():.2f}")
    print(f"Avg Mickey RR on Winners: {comp[comp['Result_M'] == 'WIN']['RR_M'].mean():.2f}")
    print(f"Win Rate: Mickey={(comp['Result_M']=='WIN').mean():.1%}, Strategy Tester={(comp['Result_O']=='WIN').mean():.1%}")
    print(f"Directional Alignment: {(comp['Direction_M']==comp['Direction_O']).mean():.1%}")

    m_win_o_loss = comp[(comp['Result_M'] == 'WIN') & (comp['Result_O'] == 'LOSS')]
    print(f"\nMickey Wins / Strategy Loses: {len(m_win_o_loss)} trades")
    if len(m_win_o_loss) > 0:
        print("Sample of M-Win / O-Loss Discrepancies:")
        cols = ['Date', 'Direction_M', 'Direction_O', 'Exit_Reason', 'PnL_Pts_M', 'PnL_Pts_O']
        print(m_win_o_loss[cols].head(10).to_string(index=False))

    # Check for same direction but opposite outcome
    same_dir_diff_res = comp[(comp['Direction_M'] == comp['Direction_O']) & (comp['Result_M'] != comp['Result_O'])]
    print(f"\nSame Direction but Different Result: {len(same_dir_diff_res)} trades")
    if len(same_dir_diff_res) > 0:
        print("Sample (First 5):")
        print(same_dir_diff_res[['Date', 'Direction_M', 'Result_M', 'Result_O', 'Exit_Reason', 'PnL_Pts_M', 'PnL_Pts_O']].head(5).to_string(index=False))

if __name__ == "__main__":
    analyze_mechanics()
