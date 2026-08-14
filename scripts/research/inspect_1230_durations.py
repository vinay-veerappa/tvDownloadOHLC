import pandas as pd

df = pd.read_csv(r"C:\Users\vinay\tvDownloadOHLC\NinjaTrader Grid 2026-08-14 12-30 AM.csv")
df = df.dropna(subset=['Instrument', 'Action', 'Price', 'Time'])
df['Time'] = pd.to_datetime(df['Time'])
df = df.sort_values('Time').reset_index(drop=True)

entries = df[df['E/X'] == 'Entry'].copy()
exits = df[df['E/X'] == 'Exit'].copy()

trades = []
open_entry = None

for idx, row in df.iterrows():
    if row['E/X'] == 'Entry':
        open_entry = row
    elif row['E/X'] == 'Exit' and open_entry is not None:
        direction = "Long" if open_entry['Action'] == 'Buy' else "Short"
        entry_price = float(open_entry['Price'])
        exit_price = float(row['Price'])
        qty = float(open_entry['Quantity'])
        
        pts = (exit_price - entry_price) if direction == "Long" else (entry_price - exit_price)
        dur = (row['Time'] - open_entry['Time']).total_seconds()
        
        trades.append({
            'Direction': direction,
            'EntryTime': open_entry['Time'],
            'ExitTime': row['Time'],
            'DurationSec': dur,
            'DurationMins': dur / 60.0,
            'Points': pts,
            'PnL': pts * 20.0 * qty,
            'ExitName': row['Name'],
            'EntryName': open_entry['Name']
        })
        open_entry = None

tdf = pd.DataFrame(trades)
print("TRADE DURATION STATISTICS:")
print(f"Mean Duration    : {tdf['DurationMins'].mean():.2f} minutes ({tdf['DurationSec'].mean():.1f} seconds)")
print(f"Median Duration  : {tdf['DurationMins'].median():.2f} minutes ({tdf['DurationSec'].median():.1f} seconds)")
print(f"Min Duration     : {tdf['DurationSec'].min():.1f} seconds")
print(f"Max Duration     : {tdf['DurationMins'].max():.2f} minutes")

# Check time diff between consecutive bars to identify the chart timeframe
tdf['TimeDiffPrevEntry'] = tdf['EntryTime'].diff().dt.total_seconds()
print(f"\nFirst 10 Trades:")
print(tdf[['Direction', 'EntryTime', 'ExitTime', 'DurationMins', 'Points', 'PnL', 'ExitName']].head(10).to_string())
