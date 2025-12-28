
import pandas as pd
import numpy as np
import os

def analyze_pullback_conditions():
    trades_path = r"c:\Users\vinay\tvDownloadOHLC\scripts\backtest\9_30_breakout\results\pullback_test_results.csv"
    vvix_path = r"c:\Users\vinay\tvDownloadOHLC\data\VVIX_1d.parquet"
    nq_path = r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
    
    if not os.path.exists(trades_path):
        print("Run test_pullback_efficiency.py first")
        return

    # 1. Load Data
    trades = pd.read_csv(trades_path)
    trades['Date'] = pd.to_datetime(trades['Date'])
    
    vvix = pd.read_parquet(vvix_path)
    vvix.index = pd.to_datetime(vvix.index).tz_localize(None).normalize()
    
    nq = pd.read_parquet(nq_path)
    if nq.index.tz is not None: nq = nq.tz_convert('US/Eastern').tz_localize(None)
    nq_daily = nq['close'].resample('D').last().dropna().to_frame()
    nq_daily['SMA20'] = nq_daily['close'].rolling(20).mean()
    nq_daily['Regime'] = np.where(nq_daily['close'] > nq_daily['SMA20'], 'BULL', 'BEAR')
    nq_daily.index = nq_daily.index.normalize()

    # 2. Merge
    df = pd.merge(trades, vvix[['open']], left_on='Date', right_index=True, how='inner')
    df = df.rename(columns={'open': 'VVIX'})
    df = pd.merge(df, nq_daily[['Regime']], left_on='Date', right_index=True, how='inner')
    
    # 3. Add Range Pct (Approximation using any row's Range_High)
    df['Range_Pct'] = (df['Range_Size'] / df['Range_High']) * 100
    
    print("\n--- Pullback Analysis by Market Condition ---")
    
    # Analysis A: Regime Impact on PB_Shallow_25
    df['VVIX_Group'] = np.where(df['VVIX'] > 115, 'High (>115)', 'Normal (<115)')
    df['Range_Size_Group'] = pd.qcut(df['Range_Pct'], 3, labels=['Small', 'Medium', 'Large'])
    
    # Analysis B: Granular VVIX Impact
    bins = [0, 85, 98, 115, 999]
    labels = ['Low (<85)', 'Mid (85-98)', 'Elevated (98-115)', 'Extreme (>115)']
    df['VVIX_Granular'] = pd.cut(df['VVIX'], bins=bins, labels=labels)

    pb_var = 'PB_Shallow_25'
    pb_df = df[df['Variant'] == pb_var].copy()
    base_df = df[df['Variant'] == 'Base_Breakout'].copy()
    
    # Calculate Fill Rate and Win Rate by Regime
    for reg in ['BULL', 'BEAR']:
        reg_pb = pb_df[pb_df['Regime'] == reg]
        reg_base = base_df[base_df['Regime'] == reg]
        fill_rate = len(reg_pb) / len(reg_base) if len(reg_base) > 0 else 0
        win_rate = reg_pb['Win'].mean()
        pts_per = reg_pb['PnL_Pts'].mean()
        
        print(f"\nRegime: {reg}")
        print(f"  Fill Rate: {fill_rate:.1%}")
        print(f"  Win Rate (Filled): {win_rate:.1%}")
        print(f"  Pts Per Trade: {pts_per:.2f}")

    print("\nImpact of Granular VVIX (Shallow 25%):")
    for group in labels:
        v_pb = pb_df[pb_df['VVIX_Granular'] == group]
        v_base = base_df[base_df['VVIX_Granular'] == group]
        
        fill_rate = len(v_pb) / len(v_base) if len(v_base) > 0 else 0
        win_rate = v_pb['Win'].mean()
        pts_per = v_pb['PnL_Pts'].mean()
        
        print(f"VVIX {group}: Fill={fill_rate:.1%}, Win={win_rate:.1%}, Pts/Trade={pts_per:.2f}")

    # Analysis D: When to WAIT vs SKIP (Prudence)
    # We update the full_merged to include granular bins
    full_merged = pd.merge(base_df, pb_df, on='Date', suffixes=('_Base', '_PB'), how='left')
    
    print("\n--- PRUDENCE ANALYSIS BY VVIX RANGE ---")
    for group in labels:
        group_loss = full_merged[(full_merged['VVIX_Granular_Base'] == group) & (full_merged['Result_Base'] == 'LOSS')]
        group_avoided = group_loss[group_loss['Variant_PB'].isna()]
        avoid_rate = len(group_avoided) / len(group_loss) if len(group_loss) > 0 else 0
        print(f"VVIX {group}: Base Losses={len(group_loss)}, Avoided={len(group_avoided)} ({avoid_rate:.1%})")

if __name__ == "__main__":
    analyze_pullback_conditions()
