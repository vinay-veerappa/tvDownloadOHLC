import pandas as pd
import numpy as np

df = pd.read_csv('scripts/backtest/9_30_breakout/results/v6_backtest_details.csv')

print('=== V6 BACKTEST ANALYSIS ===')
print(f'Total Trades: {len(df)}')
print(f'Win Rate: {(df["Result"] == "WIN").mean():.2%}')
print(f'Gross PnL: {df["PnL_Pct"].sum():.2f}%')
print()

# By Direction
print('--- BY DIRECTION ---')
for dir in ['LONG', 'SHORT']:
    sub = df[df['Direction'] == dir]
    print(f'{dir}: {len(sub)} trades, WR: {(sub["Result"] == "WIN").mean():.2%}, PnL: {sub["PnL_Pct"].sum():.2f}%')
print()

# By Entry Type
print('--- BY ENTRY TYPE ---')
for et in df['Entry_Type'].unique():
    sub = df[df['Entry_Type'] == et]
    print(f'{et}: {len(sub)} trades, WR: {(sub["Result"] == "WIN").mean():.2%}, PnL: {sub["PnL_Pct"].sum():.2f}%')
print()

# By Day of Week
print('--- BY DAY OF WEEK ---')
for dow in ['Mon', 'Wed', 'Thu', 'Fri']:
    sub = df[df['DayOfWeek'] == dow]
    if len(sub) > 0:
        print(f'{dow}: {len(sub)} trades, WR: {(sub["Result"] == "WIN").mean():.2%}, PnL: {sub["PnL_Pct"].sum():.2f}%')
print()

# By Year
print('--- BY YEAR ---')
df['Year'] = pd.to_datetime(df['Date']).dt.year
yearly = df.groupby('Year').agg({'PnL_Pct': 'sum', 'Result': lambda x: (x == 'WIN').mean()}).round(2)
yearly.columns = ['PnL_%', 'WinRate']
print(yearly.to_string())
print()

# Risk Analysis
print('--- RISK ANALYSIS ---')
print(f'Avg MAE (Heat): {df["MAE_Pct"].mean():.4f}%')
print(f'Avg MFE (Run-up): {df["MFE_Pct"].mean():.4f}%')
print(f'MAE > MFE (Bad Trades): {(df["MAE_Pct"] > df["MFE_Pct"]).sum()} / {len(df)}')
print()

# Exit Reason Breakdown
print('--- EXIT REASONS ---')
for reason in df['Exit_Reason'].unique():
    sub = df[df['Exit_Reason'] == reason]
    print(f'{reason}: {len(sub)} trades ({len(sub)/len(df)*100:.1f}%)')
