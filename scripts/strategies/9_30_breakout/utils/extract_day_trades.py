import pandas as pd

df = pd.read_excel(r'docs\strategies\9_30_breakout\0930_AllDay\ORB_V3_Doji_CME_MINI_MNQ1!_2026-01-08_467b7.xlsx', sheet_name='List of trades')
df['Date and time'] = pd.to_datetime(df['Date and time'])
df['date'] = df['Date and time'].dt.date
df['time'] = df['Date and time'].dt.strftime('%H:%M')

# Dec 10 and Dec 12
for target in ['2025-12-10', '2025-12-12']:
    day = df[df['date'] == pd.to_datetime(target).date()].copy()
    print(f"\n{'='*70}")
    print(f"{target} - {len(day)} trades")
    print('='*70)
    for _, t in day.iterrows():
        pnl = t['Net P&L USD']
        result = 'WIN' if pnl > 0 else 'LOSS' if pnl < 0 else 'BE'
        entry = t['time']
        signal = t['Signal']
        mae = t.get('MAE USD', 0)
        mfe = t.get('MFE USD', 0)
        print(f"{entry} | {signal:<15} | {result:>4} | PnL: ${pnl:>8.2f} | MAE: ${mae:>7.2f} | MFE: ${mfe:>7.2f}")
