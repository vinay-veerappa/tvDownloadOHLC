import pandas as pd

# Load pullback results
df = pd.read_csv('docs/strategies/initial_balance_break/pullback_results_45min.csv')

print("="*80)
print("PULLBACK STRATEGY DIAGNOSTIC ANALYSIS")
print("="*80)

print(f"\nTotal Trades: {len(df)}")
print(f"Win Rate: {(df['result']=='WIN').sum()/len(df)*100:.1f}%")

print("\nConfluence Score Distribution:")
print(df['confluence_score'].value_counts().sort_index())

print("\nConfluence Reasons (first 10):")
print(df['confluence_reasons'].value_counts().head(10))

print("\nTiers Hit Distribution:")
print(df['tiers_hit'].value_counts().sort_index())

print("\nBreakeven Moved:")
print(df['breakeven_moved'].value_counts())

print("\nAverage Stats:")
print(f"  Avg MAE: {df['mae_pct'].mean():.3f}%")
print(f"  Avg MFE: {df['mfe_pct'].mean():.3f}%")
print(f"  Avg PnL: {df['pnl_pct'].mean():.3f}%")

print("\nMFE Reach Analysis:")
for r in [0.25, 0.5, 0.75, 1.0]:
    pct = (df['mfe_pct'] >= r).sum() / len(df) * 100
    print(f"  {r}R: {pct:.1f}% of trades")

print("\nSample Trades:")
print(df[['date','entry_time','direction','confluence_score','pnl_pct','mae_pct','mfe_pct','tiers_hit','result']].head(20).to_string(index=False))
