import pandas as pd
import numpy as np

csv_path = r"C:\Users\vinay\tvDownloadOHLC\NinjaTrader Grid 2026-08-14 12-02 AM.csv"
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
            'EntryName': open_entry['Name'],
            'Quantity': qty,
            'TimeHHMM': open_entry['Time'].hour * 100 + open_entry['Time'].minute
        })
        open_entry = None

tdf = pd.DataFrame(trades)

print("=" * 80)
print("FILTER IMPACT ON THE 2,175 NINJATRADER TRADES")
print("=" * 80)

# Filter 1: Strict Morning Initial Balance (09:30 to 10:30 ET) vs Late Morning (10:30 to 11:30 ET)
ib_trades = tdf[tdf['TimeHHMM'].between(930, 1030)]
late_trades = tdf[tdf['TimeHHMM'] > 1030]

print(f"\n1. Initial Balance (09:30 - 10:30 ET):")
w1 = ib_trades[ib_trades['PnL'] > 0]
l1 = ib_trades[ib_trades['PnL'] <= 0]
gp1 = w1['PnL'].sum()
gl1 = abs(l1['PnL'].sum())
print(f"   Trades: {len(ib_trades)} | Win Rate: {len(w1)/len(ib_trades)*100:.2f}% | Net: ${ib_trades['PnL'].sum():,.2f} | PF: {gp1/gl1:.3f}")

print(f"\n2. Late Morning Chop (After 10:30 ET):")
w2 = late_trades[late_trades['PnL'] > 0]
l2 = late_trades[late_trades['PnL'] <= 0]
gp2 = w2['PnL'].sum()
gl2 = abs(l2['PnL'].sum())
print(f"   Trades: {len(late_trades)} | Win Rate: {len(w2)/len(late_trades)*100:.2f}% | Net: ${late_trades['PnL'].sum():,.2f} | PF: {gp2/gl2:.3f}")

# Filter 2: Max 1 Trade Per Day (First Setup of the Day)
tdf['Date'] = tdf['EntryTime'].dt.date
first_trade_of_day = tdf.groupby('Date').first().reset_index()

print(f"\n3. One-and-Done (First Pristine Setup of Each Day):")
w3 = first_trade_of_day[first_trade_of_day['PnL'] > 0]
l3 = first_trade_of_day[first_trade_of_day['PnL'] <= 0]
gp3 = w3['PnL'].sum()
gl3 = abs(l3['PnL'].sum())
print(f"   Trades: {len(first_trade_of_day)} | Win Rate: {len(w3)/len(first_trade_of_day)*100:.2f}% | Net: ${first_trade_of_day['PnL'].sum():,.2f} | PF: {gp3/gl3:.3f}")

# Filter 3: First Trade of the Day in Initial Balance (09:30 - 10:30 ET)
ib_first = first_trade_of_day[first_trade_of_day['TimeHHMM'].between(930, 1030)]
print(f"\n4. First Setup of the Day in Initial Balance Window (09:30 - 10:30 ET):")
w4 = ib_first[ib_first['PnL'] > 0]
l4 = ib_first[ib_first['PnL'] <= 0]
gp4 = w4['PnL'].sum()
gl4 = abs(l4['PnL'].sum())
print(f"   Trades: {len(ib_first)} | Win Rate: {len(w4)/len(ib_first)*100:.2f}% | Net: ${ib_first['PnL'].sum():,.2f} | PF: {gp4/gl4:.3f}")
