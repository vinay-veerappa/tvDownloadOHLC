"""
Deep Asset Analysis - Diagnose why each asset failed

Analyze:
1. Trade characteristics (MAE/MFE, win/loss patterns)
2. IB statistics (range, break frequency)
3. Asset-specific issues
4. Proposed optimizations
"""

import pandas as pd
import numpy as np
from pathlib import Path

def analyze_asset(asset_name, csv_path):
    """Deep analysis of asset performance"""
    
    print(f"\n{'='*100}")
    print(f"DEEP ANALYSIS: {asset_name}")
    print(f"{'='*100}\n")
    
    # Load data
    df = pd.read_csv(csv_path)
    
    if len(df) == 0:
        print(f"⚠ No trades for {asset_name}")
        return None
    
    # Basic stats
    print(f"Total Trades: {len(df)}")
    print(f"Winners: {(df['result']=='WIN').sum()}")
    print(f"Losers: {(df['result']=='LOSS').sum()}")
    print(f"Win Rate: {(df['result']=='WIN').sum()/len(df)*100:.1f}%")
    
    # P&L Analysis
    print(f"\n--- P&L Analysis ---")
    print(f"Total PnL: {df['pnl_pct'].sum():.2f}%")
    print(f"Avg Win: {df[df['result']=='WIN']['pnl_pct'].mean():.3f}%")
    print(f"Avg Loss: {df[df['result']=='LOSS']['pnl_pct'].mean():.3f}%")
    print(f"Profit Factor: {df[df['result']=='WIN']['pnl_pct'].sum() / abs(df[df['result']=='LOSS']['pnl_pct'].sum()):.2f}")
    
    # MAE/MFE Analysis
    print(f"\n--- MAE/MFE Analysis ---")
    print(f"Avg MAE: {df['mae_pct'].mean():.3f}%")
    print(f"Avg MFE: {df['mfe_pct'].mean():.3f}%")
    print(f"Winners MAE: {df[df['result']=='WIN']['mae_pct'].mean():.3f}%")
    print(f"Losers MAE: {df[df['result']=='LOSS']['mae_pct'].mean():.3f}%")
    print(f"Winners MFE: {df[df['result']=='WIN']['mfe_pct'].mean():.3f}%")
    print(f"Losers MFE: {df[df['result']=='LOSS']['mfe_pct'].mean():.3f}%")
    
    # MFE Reach Analysis
    print(f"\n--- MFE Reach Probability ---")
    for r in [0.25, 0.5, 0.75, 1.0, 1.5]:
        pct = (df['mfe_pct'] >= r).sum() / len(df) * 100
        print(f"{r}R: {pct:.1f}% of trades")
    
    # IB Range Analysis
    print(f"\n--- IB Range Analysis ---")
    print(f"Avg IB Range: {df['ib_range_pct'].mean():.3f}%")
    print(f"Min IB Range: {df['ib_range_pct'].min():.3f}%")
    print(f"Max IB Range: {df['ib_range_pct'].max():.3f}%")
    print(f"Median IB Range: {df['ib_range_pct'].median():.3f}%")
    
    # IB Range vs Win Rate
    print(f"\n--- IB Range vs Performance ---")
    df['ib_range_bucket'] = pd.cut(df['ib_range_pct'], bins=[0, 0.3, 0.5, 0.7, 1.0, 10], 
                                     labels=['<0.3%', '0.3-0.5%', '0.5-0.7%', '0.7-1.0%', '>1.0%'])
    for bucket in df['ib_range_bucket'].unique():
        if pd.isna(bucket):
            continue
        bucket_data = df[df['ib_range_bucket'] == bucket]
        wr = (bucket_data['result']=='WIN').sum() / len(bucket_data) * 100
        avg_pnl = bucket_data['pnl_pct'].mean()
        print(f"{bucket}: {len(bucket_data)} trades, WR={wr:.1f}%, Avg PnL={avg_pnl:.2f}%")
    
    # Directional Bias Analysis
    print(f"\n--- Directional Bias Analysis ---")
    print(f"LONG trades: {(df['direction']=='LONG').sum()}")
    print(f"SHORT trades: {(df['direction']=='SHORT').sum()}")
    long_wr = (df[df['direction']=='LONG']['result']=='WIN').sum() / (df['direction']=='LONG').sum() * 100
    short_wr = (df[df['direction']=='SHORT']['result']=='WIN').sum() / (df['direction']=='SHORT').sum() * 100
    print(f"LONG Win Rate: {long_wr:.1f}%")
    print(f"SHORT Win Rate: {short_wr:.1f}%")
    
    # Matched Expectation Analysis
    print(f"\n--- Expectation Match Analysis ---")
    matched = df[df['matched_expectation']==True]
    unmatched = df[df['matched_expectation']==False]
    if len(matched) > 0:
        matched_wr = (matched['result']=='WIN').sum() / len(matched) * 100
        print(f"Matched Expectation: {len(matched)} trades, WR={matched_wr:.1f}%")
    if len(unmatched) > 0:
        unmatched_wr = (unmatched['result']=='WIN').sum() / len(unmatched) * 100
        print(f"Unmatched Expectation: {len(unmatched)} trades, WR={unmatched_wr:.1f}%")
    
    # Tiers Hit Analysis
    print(f"\n--- Take Profit Tiers Hit ---")
    for tier in [0, 1, 2]:
        tier_count = (df['tiers_hit'] == tier).sum()
        tier_pct = tier_count / len(df) * 100
        print(f"{tier} tiers: {tier_count} trades ({tier_pct:.1f}%)")
    
    # Exit Reason Analysis
    print(f"\n--- Exit Reasons ---")
    print(df['exit_reason'].value_counts())
    
    # Time-based Analysis
    print(f"\n--- Entry Time Analysis ---")
    df['entry_hour'] = pd.to_datetime(df['entry_time'], utc=True).dt.hour
    for hour in sorted(df['entry_hour'].unique()):
        hour_data = df[df['entry_hour'] == hour]
        wr = (hour_data['result']=='WIN').sum() / len(hour_data) * 100
        print(f"{hour:02d}:00 - {hour+1:02d}:00: {len(hour_data)} trades, WR={wr:.1f}%")
    
    return {
        'asset': asset_name,
        'total_trades': len(df),
        'win_rate': (df['result']=='WIN').sum()/len(df)*100,
        'avg_win': df[df['result']=='WIN']['pnl_pct'].mean(),
        'avg_loss': df[df['result']=='LOSS']['pnl_pct'].mean(),
        'avg_mae': df['mae_pct'].mean(),
        'avg_mfe': df['mfe_pct'].mean(),
        'avg_ib_range': df['ib_range_pct'].mean(),
        'mfe_0.5r': (df['mfe_pct'] >= 0.5).sum() / len(df) * 100,
        'mfe_1.0r': (df['mfe_pct'] >= 1.0).sum() / len(df) * 100
    }


# Analyze each asset
assets = [
    ('NQ1', 'docs/strategies/initial_balance_break/historical_validation/nq_2019_2020.csv'),
    ('ES1', 'docs/strategies/initial_balance_break/multi_asset_validation/es1_2019_2020.csv'),
    ('RTY1', 'docs/strategies/initial_balance_break/multi_asset_validation/rty1_2019_2020.csv'),
    ('YM1', 'docs/strategies/initial_balance_break/multi_asset_validation/ym1_2019_2020.csv'),
    ('GC1', 'docs/strategies/initial_balance_break/multi_asset_validation/gc1_2019_2020.csv'),
]

results = []
for asset_name, csv_path in assets:
    result = analyze_asset(asset_name, csv_path)
    if result:
        results.append(result)

# Comparison table
print(f"\n{'='*100}")
print("ASSET COMPARISON SUMMARY")
print(f"{'='*100}\n")

df_summary = pd.DataFrame(results)
print(df_summary.to_string(index=False))

# Save detailed analysis
output_path = Path('docs/strategies/initial_balance_break/multi_asset_validation/detailed_analysis.csv')
df_summary.to_csv(output_path, index=False)
print(f"\n✓ Detailed analysis saved to: {output_path}")
