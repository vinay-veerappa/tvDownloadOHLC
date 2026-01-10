import pandas as pd

df = pd.read_excel(r'docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_Doji_CME_MINI_MNQ1!_2026-01-08_467b7.xlsx', sheet_name='List of trades')
df['Date and time'] = pd.to_datetime(df['Date and time'])

print('Date Range:')
print(f"Start: {df['Date and time'].min()}")
print(f"End: {df['Date and time'].max()}")
print(f"Duration: {(df['Date and time'].max() - df['Date and time'].min()).days} days")
print(f"Approx months: {(df['Date and time'].max() - df['Date and time'].min()).days / 30:.1f}")
