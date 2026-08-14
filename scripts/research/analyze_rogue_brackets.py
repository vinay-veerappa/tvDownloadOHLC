import pandas as pd

csv_path = r"C:\Users\vinay\tvDownloadOHLC\NinjaTrader Grid 2026-08-13 11-37 PM.csv"
df = pd.read_csv(csv_path).dropna(subset=['Instrument', 'Action', 'Price', 'Time'])
df['Time'] = pd.to_datetime(df['Time'])
df = df.sort_values('Time').reset_index(drop=True)

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

print("=" * 80)
print("ANALYSIS OF ALL 92 TRADES IN CSV")
print("=" * 80)
print(f"Total Trades: {len(tdf)}")
print(f"Total Net PnL: ${tdf['PnL'].sum():,.2f}")

normal_trades = tdf[tdf['Points'].between(-15, 25)]
rogue_trades = tdf[~tdf['Points'].between(-15, 25)]

print("\n--- NORMAL TRADES (Strict 10pt Stop / 20pt Target) ---")
print(f"Count: {len(normal_trades)}")
w = normal_trades[normal_trades['PnL'] > 0]
l = normal_trades[normal_trades['PnL'] <= 0]
gp = w['PnL'].sum()
gl = abs(l['PnL'].sum())
print(f"Win Rate: {len(w)/len(normal_trades)*100:.2f}%")
print(f"Gross Profit: ${gp:,.2f}")
print(f"Gross Loss:   -${gl:,.2f}")
print(f"Net Profit:   ${normal_trades['PnL'].sum():,.2f}")
print(f"Profit Factor: {gp/gl:.3f}")

print("\n--- ROGUE / UNATTACHED BRACKET TRADES ---")
print(rogue_trades[['Direction', 'EntryTime', 'ExitTime', 'EntryPrice', 'ExitPrice', 'Points', 'PnL', 'ExitName']].to_string())
