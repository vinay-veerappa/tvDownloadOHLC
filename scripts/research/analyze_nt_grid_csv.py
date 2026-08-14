import pandas as pd
import numpy as np

csv_path = r"C:\Users\vinay\tvDownloadOHLC\NinjaTrader Grid 2026-08-13 11-37 PM.csv"
df = pd.read_csv(csv_path)

print("=" * 80)
print(f"RAW CSV ROW COUNT: {len(df)}")
print(f"COLUMNS: {list(df.columns)}")
print("=" * 80)

# Filter out empty rows if any
df = df.dropna(subset=['Instrument', 'Action', 'Price', 'Time'])

# NinjaTrader order log pairs: Entry and Exit rows
print(df.head(10))

# Convert Time
df['Time'] = pd.to_datetime(df['Time'])
df = df.sort_values('Time').reset_index(drop=True)

print("\nDATE RANGE IN CSV:")
print(f"Earliest Time: {df['Time'].min()}")
print(f"Latest Time:   {df['Time'].max()}")
print(f"Unique Instruments in CSV: {df['Instrument'].unique()}")

# Pair entries and exits
# In NT8 Grid export:
# Each trade has an Entry row (E/X == 'Entry') and an Exit row (E/X == 'Exit')
entries = df[df['E/X'] == 'Entry'].copy()
exits = df[df['E/X'] == 'Exit'].copy()

print(f"\nTotal Entry Rows: {len(entries)}")
print(f"Total Exit Rows:  {len(exits)}")

# Let's inspect the trades
trades = []
# Group by position / order matching or iterate sequentially
# In NT8, each exit closes the preceding entry
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
            'EntryName': open_entry['Name']
        })
        open_entry = None

trades_df = pd.DataFrame(trades)
print(f"\nSuccessfully Reconstructed Trades: {len(trades_df)}")

if len(trades_df) > 0:
    winners = trades_df[trades_df['PnL'] > 0]
    losers = trades_df[trades_df['PnL'] <= 0]
    
    total_trades = len(trades_df)
    win_count = len(winners)
    loss_count = len(losers)
    win_rate = (win_count / total_trades) * 100
    
    gross_profit = winners['PnL'].sum()
    gross_loss = abs(losers['PnL'].sum())
    net_profit = trades_df['PnL'].sum()
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan
    
    avg_win = winners['PnL'].mean() if len(winners) > 0 else 0
    avg_loss = losers['PnL'].mean() if len(losers) > 0 else 0
    
    print("=" * 80)
    print("NINJATRADER BACKTEST TRADE PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"Total Trades:        {total_trades}")
    print(f"Winners:             {win_count} ({win_rate:.2f}%)")
    print(f"Losers:              {loss_count} ({100 - win_rate:.2f}%)")
    print(f"Gross Profit:        ${gross_profit:,.2f}")
    print(f"Gross Loss:          -${gross_loss:,.2f}")
    print(f"Net Profit:          ${net_profit:,.2f}")
    print(f"Profit Factor:       {profit_factor:.3f}")
    print(f"Average Win:         ${avg_win:,.2f} ({avg_win/20:.2f} pts)")
    print(f"Average Loss:        ${avg_loss:,.2f} ({avg_loss/20:.2f} pts)")
    print(f"Win/Loss Ratio:      {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "N/A")
    
    print("\n--- EXIT REASON BREAKDOWN ---")
    print(trades_df['ExitName'].value_counts())
    
    print("\n--- DIRECTION BREAKDOWN ---")
    for d, g in trades_df.groupby('Direction'):
        w = g[g['PnL'] > 0]
        l = g[g['PnL'] <= 0]
        gp = w['PnL'].sum()
        gl = abs(l['PnL'].sum())
        pf = gp / gl if gl > 0 else np.nan
        print(f"  {d:<6}: {len(g):>3d} trades | Win Rate: {len(w)/len(g)*100:>5.1f}% | Net: ${g['PnL'].sum():>9,.2f} | PF: {pf:.2f}")

    print("\n--- MONTHLY BREAKDOWN ---")
    trades_df['YearMonth'] = trades_df['EntryTime'].dt.to_period('M')
    for ym, g in trades_df.groupby('YearMonth'):
        w = g[g['PnL'] > 0]
        print(f"  {str(ym):<7}: {len(g):>3d} trades | Win Rate: {len(w)/len(g)*100:>5.1f}% | Net: ${g['PnL'].sum():>9,.2f}")
