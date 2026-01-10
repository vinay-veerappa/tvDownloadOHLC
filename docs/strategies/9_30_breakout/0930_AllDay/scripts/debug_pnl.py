
import pandas as pd
import glob
import os
from analyze_v3_comprehensive import load_strategy_data, calc_stats_extended

files = glob.glob(r"ORB_V3_Doji*.xlsx")
files.sort(key=os.path.getmtime, reverse=True)
target = files[0]

print(f"Debugging: {target}")
data = load_strategy_data(target, "DEBUG")
df = data['merged']

print("\n--- Columns ---")
print(df.columns.tolist())

print("\n--- First 5 Rows of Net P&L ---")
print(df[['Net P&L USD']].head())

print("\n--- Loss Check ---")
losses = df[df['Net P&L USD'] <= 0]
print(f"Count of Losses: {len(losses)}")
if not losses.empty:
    print(f"Avg Loss: {losses['Net P&L USD'].mean()}")
else:
    print("NO LOSSES FOUND. Check column data types.")
    print(df['Net P&L USD'].dtypes)
