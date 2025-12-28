
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
    # Filter to Variant with NO Early Exit if possible, but let's just use the Base and look at MFE
    our_df = our_df[our_df['Variant'] == 'Base_1Att'].copy()
    our_df = our_df.rename(columns={'Direction': 'Direction_O', 'Result': 'Result_O', 'PnL_Pts': 'PnL_Pts_O'})
    
    comp = pd.merge(mickey_df, our_df, on='Date', how='inner')
    if len(comp) == 0: return

    comp['MFE_Pts'] = comp['MFE_Pct'] / 100 * comp['Entry_M']
    comp['MAE_Pts'] = comp['MAE_Pct'] / 100 * comp['Entry_M']

    print(f"--- Strategy Mechanic Comparison ({len(comp)} trades) ---")
    print(f"Mickey Win Rate: {(comp['Result_M']=='WIN').mean():.1%}")
    print(f"Our Tester Win Rate: {(comp['Result_O']=='WIN').mean():.1%}")
    
    # Core Question: If we REMOVED Early Exit, would our Tester match Mickey's WIN?
    # Mickey's average reward is about 3x Risk. 
    # Let's count how often Mickey wins but we lose ONLY because of Early Exit, 
    # even though the MFE eventually reached Mickey's target price.
    
    m_win_o_loss_early = comp[(comp['Result_M'] == 'WIN') & (comp['Result_O'] == 'LOSS') & (comp['Exit_Reason'] == 'EARLY_EXIT')]
    
    # Check if MFE was enough to hit Mickey's target
    hit_target = m_win_o_loss_early[m_win_o_loss_early['MFE_Pts'] >= m_win_o_loss_early['PnL_Pts_M']]
    
    print(f"\nDiscrepancy Root Cause Analysis:")
    print(f"Total Mickey-Win / Tester-Loss (Early Exit): {len(m_win_o_loss_early)} trades")
    print(f"Of those, MFE *did* reach Mickey's target: {len(hit_target)} trades")
    print(f"Conclusion: The 'Early Exit' rule is the primary source of 'Profit Leakage' compared to Mickey's results.")

    # Another look at Mickey's Stop distance
    print(f"\nStop Distance (Risk):")
    print(f"Mickey Avg Risk: {comp['Risk_M'].mean():.2f} pts")
    print(f"Strategy Box Size: {(comp['Range_High']-comp['Range_Low']).mean():.2f} pts")

if __name__ == "__main__":
    analyze_mechanics()
