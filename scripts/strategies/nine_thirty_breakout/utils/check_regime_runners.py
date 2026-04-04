
import pandas as pd
import numpy as np
import os

def check_regime_runners():
    trades_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\930_backtest_all_trades.csv"
    nq_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    
    trades = pd.read_csv(trades_path)
    trades['Date'] = pd.to_datetime(trades['Date'])
    base_trades = trades[trades['Variant'] == 'Base_1Att'].copy()

    nq = pd.read_parquet(nq_path)
    if nq.index.tz is not None: nq = nq.tz_convert('US/Eastern').tz_localize(None)
    nq_daily = nq['close'].resample('D').last().dropna().to_frame()
    nq_daily['SMA20'] = nq_daily['close'].rolling(20).mean()
    nq_daily['Regime'] = np.where(nq_daily['close'] > nq_daily['SMA20'], 'BULL', 'BEAR')
    nq_daily.index = nq_daily.index.normalize()

    df = pd.merge(base_trades, nq_daily[['Regime']], left_on='Date', right_index=True, how='inner')
    
    print("MFE Distribution by Regime:")
    print(df.groupby('Regime')['MFE_Pct'].describe())
    
    print("\nWin Rate for 0.35% Target by Regime:")
    df['Hit_035'] = df['MFE_Pct'] >= 0.35
    print(df.groupby('Regime')['Hit_035'].mean())

    print("\nWin Rate for 0.90% Target by Regime:")
    df['Hit_090'] = df['MFE_Pct'] >= 0.90
    print(df.groupby('Regime')['Hit_090'].mean())

if __name__ == "__main__":
    check_regime_runners()
