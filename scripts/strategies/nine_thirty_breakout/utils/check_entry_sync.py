
import pandas as pd
import numpy as np
import os

def load_data():
    mickey_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\Mickey 0930CPT Backtest - dont touch 0930 PNL.txt.csv"
    m_df = pd.read_csv(mickey_path, header=None, low_memory=False, skiprows=4)
    m_df = m_df.rename(columns={1: 'Date', 3: 'Entry_M', 4: 'Stop_M', 5: 'Exit_M', 6: 'Dir_M'})
    
    our_trades_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    o_df = pd.read_csv(our_trades_path)
    o_df['Date'] = pd.to_datetime(o_df['Date'])
    
    return m_df, o_df

def check_sync():
    m_df, o_df = load_data()
    m_data = []
    for idx, row in m_df.iterrows():
        try:
            d = pd.to_datetime(str(row['Date'])).date()
            m_data.append({'Date': d, 'Entry_M': float(str(row['Entry_M']).replace(',','')), 'Dir_M': str(row['Dir_M']).upper()})
        except: continue
    m_df = pd.DataFrame(m_data)
    
    o_df_base = o_df[o_df['Variant'] == 'Base_1Att'].copy()
    o_df_base['Date'] = o_df_base['Date'].dt.date
    
    comp = pd.merge(m_df, o_df_base, on='Date')
    
    # Check Entry Price proximity to Range High/Low
    comp['Dist_to_High'] = abs(comp['Entry_M'] - comp['Range_High'])
    comp['Dist_to_Low'] = abs(comp['Entry_M'] - comp['Range_Low'])
    
    print("Entry Price Proximity to 9:30 Range (Abs Pts):")
    print(comp[['Dist_to_High', 'Dist_to_Low']].describe())
    
    # If Entry_M is very different from Range High/Low, Mickey is not trading the 9:30 breakout.
    far_from_range = comp[(comp['Dist_to_High'] > 5) & (comp['Dist_to_Low'] > 5)]
    print(f"\nTrades with Entry > 5 pts from 9:30 Range boundaries: {len(far_from_range)/len(comp):.1%}")
    
    print("\nSample of 'Far' entries:")
    print(far_from_range[['Date', 'Entry_M', 'Range_High', 'Range_Low', 'Dir_M', 'Direction']].head(10).to_string(index=False))

if __name__ == "__main__":
    check_sync()
