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
            
        pnl = pts * 20.0 * qty  # NQ point value = $20
        
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
            'DurationMins': (row['Time'] - open_entry['Time']).total_seconds() / 60.0
        })
        open_entry = None

tdf = pd.DataFrame(trades)

# Add Temporal Columns
tdf['Year'] = tdf['EntryTime'].dt.year
tdf['DayOfWeek'] = tdf['EntryTime'].dt.day_name()
tdf['Hour'] = tdf['EntryTime'].dt.hour

print("=" * 85)
print("YEAR-BY-YEAR PERFORMANCE (2,175 TRADES)")
print("=" * 85)
print(f"{'YEAR':<6} | {'TRADES':<6} | {'WIN RATE':<9} | {'GROSS WIN':<12} | {'GROSS LOSS':<12} | {'NET PROFIT':<12} | {'PF':<6}")
print("-" * 85)
for y, g in tdf.groupby('Year'):
    w = g[g['PnL'] > 0]
    l = g[g['PnL'] <= 0]
    gp = w['PnL'].sum()
    gl = abs(l['PnL'].sum())
    net = g['PnL'].sum()
    wr = len(w) / len(g) * 100
    pf = gp / gl if gl > 0 else np.nan
    print(f"{y:<6} | {len(g):>6d} | {wr:>8.1f}% | ${gp:>10,.2f} | -${gl:>10,.2f} | ${net:>10,.2f} | {pf:>6.2f}")

print("\n" + "=" * 85)
print("DAY-OF-WEEK PERFORMANCE")
print("=" * 85)
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
for d in days_order:
    g = tdf[tdf['DayOfWeek'] == d]
    if len(g) == 0: continue
    w = g[g['PnL'] > 0]
    l = g[g['PnL'] <= 0]
    gp = w['PnL'].sum()
    gl = abs(l['PnL'].sum())
    net = g['PnL'].sum()
    wr = len(w) / len(g) * 100
    pf = gp / gl if gl > 0 else np.nan
    print(f"{d:<10} | {len(g):>6d} trades | WR: {wr:>5.1f}% | Net: ${net:>10,.2f} | PF: {pf:>5.2f}")

print("\n" + "=" * 85)
print("HOURLY WINDOW PERFORMANCE (ET)")
print("=" * 85)
for h, g in tdf.groupby('Hour'):
    w = g[g['PnL'] > 0]
    l = g[g['PnL'] <= 0]
    gp = w['PnL'].sum()
    gl = abs(l['PnL'].sum())
    net = g['PnL'].sum()
    wr = len(w) / len(g) * 100
    pf = gp / gl if gl > 0 else np.nan
    print(f"Hour {h:02d}:00 ET | {len(g):>6d} trades | WR: {wr:>5.1f}% | Net: ${net:>10,.2f} | PF: {pf:>5.2f}")

print("\n" + "=" * 85)
print("DIRECTIONAL LONG vs SHORT BREAKDOWN")
print("=" * 85)
for d, g in tdf.groupby('Direction'):
    w = g[g['PnL'] > 0]
    l = g[g['PnL'] <= 0]
    gp = w['PnL'].sum()
    gl = abs(l['PnL'].sum())
    net = g['PnL'].sum()
    wr = len(w) / len(g) * 100
    pf = gp / gl if gl > 0 else np.nan
    print(f"{d:<6} | {len(g):>6d} trades | WR: {wr:>5.1f}% | Net: ${net:>10,.2f} | PF: {pf:>5.2f}")
