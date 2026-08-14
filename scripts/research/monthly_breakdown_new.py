import pandas as pd
import numpy as np

csv_path = r"C:\Users\vinay\tvDownloadOHLC\NinjaTrader Grid 2026-08-13 11-58 PM.csv"
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
            'DurationMins': (row['Time'] - open_entry['Time']).total_seconds() / 60.0
        })
        open_entry = None

tdf = pd.DataFrame(trades)
tdf['YearMonth'] = tdf['EntryTime'].dt.to_period('M')

print("=" * 85)
print(f"{'MONTH':<8} | {'TRADES':<6} | {'WIN RATE':<9} | {'GROSS WIN':<12} | {'GROSS LOSS':<12} | {'NET PROFIT':<12} | {'PF':<6}")
print("=" * 85)

for ym, g in tdf.groupby('YearMonth'):
    w = g[g['PnL'] > 0]
    l = g[g['PnL'] <= 0]
    gp = w['PnL'].sum()
    gl = abs(l['PnL'].sum())
    net = g['PnL'].sum()
    wr = len(w) / len(g) * 100
    pf = gp / gl if gl > 0 else np.nan
    print(f"{str(ym):<8} | {len(g):>6d} | {wr:>8.1f}% | ${gp:>10,.2f} | -${gl:>10,.2f} | ${net:>10,.2f} | {pf:>6.2f}")

print("=" * 85)
print(f"{'TOTAL':<8} | {len(tdf):>6d} | {len(tdf[tdf['PnL']>0])/len(tdf)*100:>8.1f}% | ${tdf[tdf['PnL']>0]['PnL'].sum():>10,.2f} | -${abs(tdf[tdf['PnL']<=0]['PnL'].sum()):>10,.2f} | ${tdf['PnL'].sum():>10,.2f} | {tdf[tdf['PnL']>0]['PnL'].sum()/abs(tdf[tdf['PnL']<=0]['PnL'].sum()):>6.3f}")
print("=" * 85)

# Same-day intraday trades vs overnight holding
intraday_trades = tdf[tdf['EntryTime'].dt.date == tdf['ExitTime'].dt.date]
overnight_trades = tdf[tdf['EntryTime'].dt.date != tdf['ExitTime'].dt.date]

print(f"\nINTRADAY COMPLETED TRADES (Same Day Exit):")
print(f"  Count: {len(intraday_trades)} trades")
print(f"  Win Rate: {len(intraday_trades[intraday_trades['PnL']>0])/len(intraday_trades)*100:.1f}%")
print(f"  Net Profit: ${intraday_trades['PnL'].sum():,.2f}")
print(f"  Profit Factor: {intraday_trades[intraday_trades['PnL']>0]['PnL'].sum() / abs(intraday_trades[intraday_trades['PnL']<=0]['PnL'].sum()):.3f}")

print(f"\nOVERNIGHT HELD TRADES (Next Day Exit):")
print(f"  Count: {len(overnight_trades)} trades")
print(f"  Net Profit: ${overnight_trades['PnL'].sum():,.2f}")
print(f"  Profit Factor: {overnight_trades[overnight_trades['PnL']>0]['PnL'].sum() / abs(overnight_trades[overnight_trades['PnL']<=0]['PnL'].sum()):.3f}")
