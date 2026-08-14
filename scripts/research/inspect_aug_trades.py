import pandas as pd

csv_path = r"C:\Users\vinay\tvDownloadOHLC\NinjaTrader Grid 2026-08-13 11-37 PM.csv"
df = pd.read_csv(csv_path).dropna(subset=['Instrument', 'Action', 'Price', 'Time'])
df['Time'] = pd.to_datetime(df['Time'])
df = df.sort_values('Time').reset_index(drop=True)

# Pair entries and exits
trades = []
open_entry = None

for idx, row in df.iterrows():
    if row['E/X'] == 'Entry':
        open_entry = row
    elif row['E/X'] == 'Exit' and open_entry is not None:
        direction = "Long" if open_entry['Action'] == 'Buy' else "Short"
        entry_price = open_entry['Price']
        exit_price = row['Price']
        qty = open_entry['Quantity']
        
        if direction == "Long":
            pts = exit_price - entry_price
        else:
            pts = entry_price - exit_price
            
        pnl = pts * 20.0 * qty
        
        trades.append({
            'Instrument': row['Instrument'],
            'Direction': direction,
            'EntryTime': open_entry['Time'],
            'ExitTime': row['Time'],
            'EntryPrice': entry_price,
            'ExitPrice': exit_price,
            'Points': pts,
            'PnL': pnl,
            'ExitName': row['Name'],
            'EntryName': open_entry['Name']
        })
        open_entry = None

tdf = pd.DataFrame(trades)

print("FIRST 25 TRADES IN AUGUST/SEPTEMBER 2025:")
print(tdf[['Direction', 'EntryTime', 'ExitTime', 'EntryPrice', 'ExitPrice', 'Points', 'PnL', 'ExitName']].head(25).to_string())

print("\nWORST 10 LOSING TRADES:")
print(tdf.sort_values('PnL').head(10)[['Direction', 'EntryTime', 'ExitTime', 'EntryPrice', 'ExitPrice', 'Points', 'PnL', 'ExitName']].to_string())
