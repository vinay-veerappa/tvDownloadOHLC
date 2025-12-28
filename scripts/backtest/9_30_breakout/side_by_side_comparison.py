
import pandas as pd
import numpy as np

def generate_side_by_side():
    mickey_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\Mickey 0930CPT Backtest - dont touch 0930 PNL.txt.csv"
    our_trades_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    
    # Load Mickey
    m_raw = pd.read_csv(mickey_path, header=None, skiprows=4)
    m_data = []
    for idx, row in m_raw.iterrows():
        try:
            date = pd.to_datetime(str(row[1])).date()
            pnl = float(str(row[42])) if len(row) > 42 else 0 # Result index from deep check
            # Simpler: just get WIN/LOSS from the "Result" column if we can find it
            # From compare_mickey_deep: Result_M was pts > 0
            entry = float(str(row[3]).replace(',','').replace('"',''))
            exit_p = float(str(row[5]).replace(',','').replace('"',''))
            direction = str(row[6]).lower()
            pts = (exit_p - entry) if 'long' in direction else (entry - exit_p)
            m_data.append({'Date': date, 'Result_M': 'WIN' if pts > 0 else 'LOSS'})
        except: continue
    m_df = pd.DataFrame(m_data)
    
    # Load Our Trades
    o_df = pd.read_csv(our_trades_path)
    o_df['Date'] = pd.to_datetime(o_df['Date']).dt.date
    
    # Merge on shared dates to be fair
    comp = pd.merge(m_df, o_df, on='Date')
    
    # Calculate win rates across different variants
    summary = []
    
    # Mickey's baseline
    summary.append({
        'Strategy Configuration': "Mickey's Strategy (As logged)",
        'Win Rate': f"{(comp['Result_M'] == 'WIN').mean():.1%}",
        'Trades': len(m_df) # Mickey Total
    })
    
    # Our Base (Strict Exit)
    base_1att = comp[comp['Variant'] == 'Base_1Att']
    summary.append({
        'Strategy Configuration': "Our Base (1 Attempt, Strict Range Exit)",
        'Win Rate': f"{(base_1att['Result'] == 'WIN').mean():.1%}",
        'Trades': len(base_1att)
    })
    
    # Our No Early Exit
    no_exit = comp[comp['Variant'] == 'Base_NoEarlyExit']
    summary.append({
        'Strategy Configuration': "Our Strategy (No Early Exit)",
        'Win Rate': f"{(no_exit['Result'] == 'WIN').mean():.1%}",
        'Trades': len(no_exit)
    })
    
    # Enhanced with 3 attempts
    enhanced = comp[comp['Variant'] == 'Enhanced_3Att_CTQ']
    summary.append({
        'Strategy Configuration': "Our Enhanced (3 Attempts, Scale-outs)",
        'Win Rate': f"{(enhanced['Result'] == 'WIN').mean():.1%}",
        'Trades': len(enhanced)
    })
    
    print("\nSIDE-BY-SIDE WIN RATE COMPARISON (Shared Dates)")
    print("="*60)
    print(pd.DataFrame(summary).to_string(index=False))
    print("="*60)
    print("Note: Shared dates only (n=580 days). Our 'Win' depends on the target (0.1%-0.9%).")

if __name__ == "__main__":
    generate_side_by_side()
