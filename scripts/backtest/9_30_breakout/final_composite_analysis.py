
import pandas as pd
import numpy as np
import os

def final_composite_analysis():
    trades_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    vvix_path = r"c:\Users\vinay\tvDownloadOHLC\data\VVIX_1d.parquet"
    nq_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    
    if not all(os.path.exists(p) for p in [trades_path, vvix_path, nq_path]):
        print("Missing data files")
        return

    # 1. Load Trades
    trades = pd.read_csv(trades_path)
    trades['Date'] = pd.to_datetime(trades['Date'])
    
    # 2. Add Day of Week Filter
    trades['DOW'] = trades['Date'].dt.day_name()
    
    # 3. Load VVIX
    vvix = pd.read_parquet(vvix_path)
    vvix.index = pd.to_datetime(vvix.index).tz_localize(None).normalize()
    vvix = vvix.rename(columns={'open': 'VVIX_Open'})
    
    # 4. Calculate Regime (NQ vs SMA20)
    # Load 1m data and downsample to daily for SMA
    nq = pd.read_parquet(nq_path)
    if nq.index.tz is not None: nq = nq.tz_convert('US/Eastern').tz_localize(None)
    nq_daily = nq['close'].resample('D').last().dropna().to_frame()
    nq_daily['SMA20'] = nq_daily['close'].rolling(20).mean()
    nq_daily['Regime'] = np.where(nq_daily['close'] > nq_daily['SMA20'], 'BULL', 'BEAR')
    nq_daily.index = nq_daily.index.normalize()

    # 5. Merge everything
    df = pd.merge(trades, vvix[['VVIX_Open']], left_on='Date', right_index=True, how='inner')
    df = pd.merge(df, nq_daily[['Regime']], left_on='Date', right_index=True, how='inner')
    
    # 6. Apply Filter Combination
    # Recommendation: Bull Regime + Skip Tuesday + VVIX < 115
    mask = (df['Regime'] == 'BULL') & (df['DOW'] != 'Tuesday') & (df['VVIX_Open'] < 115)
    
    variants = ['Base_1Att', 'Base_NoEarlyExit']
    print("\nCOMBINED EFFECTIVE WIN RATES (Bull Regime + No Tue + VVIX < 115):")
    
    targets = [0.10, 0.35, 0.50, 0.90]
    
    summary_results = []
    for var in variants:
        v_df = df[mask & (df['Variant'] == var)].copy()
        if v_df.empty: continue
        
        row = {'Variant': var, 'Trades': len(v_df)}
        for tp in targets:
            wr = len(v_df[v_df['MFE_Pct'] >= tp]) / len(v_df)
            row[f'WR_{int(tp*100)}bps'] = f"{wr:.1%}"
        summary_results.append(row)
        
    print(pd.DataFrame(summary_results).to_string(index=False))

if __name__ == "__main__":
    final_composite_analysis()
