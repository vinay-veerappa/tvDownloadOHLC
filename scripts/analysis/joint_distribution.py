"""
Full 4x4 joint distribution: High Quarter × Low Quarter
Shows exactly where all probabilities go for each hour.
"""
import pandas as pd

df = pd.read_parquet('data/NQ1_1m.parquet')
if df.index.tz is None:
    df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
else:
    df.index = df.index.tz_convert('America/New_York')

df['hour'] = df.index.hour
df['minute'] = df.index.minute
df['date_key'] = df.index.date
df['q_int'] = df['minute'] // 15

h_agg = df.groupby(['date_key', 'hour']).agg(
    h_high_idx=('high', 'idxmax'),
    h_low_idx=('low', 'idxmin'),
    n_quarters=('q_int', 'nunique')
).reset_index()

full = h_agg[h_agg['n_quarters'] == 4].copy()
full['high_q'] = full['h_high_idx'].dt.minute // 15
full['low_q'] = full['h_low_idx'].dt.minute // 15

q_map = {0: 'Q1', 1: 'Q2', 2: 'Q3', 3: 'Q4'}

display_order = [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]

for h in display_order:
    hdf = full[full['hour'] == h]
    if hdf.empty:
        continue
    tot = len(hdf)
    print(f'\n=== Hour {h:02d}:00 (N={tot}) ===')
    header = '         | Low=Q1   | Low=Q2   | Low=Q3   | Low=Q4   | Row Total'
    print(header)
    print('-' * len(header))
    
    for hq in range(4):
        cells = []
        row_sum = 0
        for lq in range(4):
            count = int(((hdf['high_q'] == hq) & (hdf['low_q'] == lq)).sum())
            pct = count / tot * 100
            cells.append(f'{pct:6.1f}%')
            row_sum += pct
        label = f'Hi={q_map[hq]:>2}'
        print(f'{label}  | {"  | ".join(cells)}  | {row_sum:6.1f}%')
    
    # Column totals
    col_cells = []
    grand = 0
    for lq in range(4):
        ct = (hdf['low_q'] == lq).sum() / tot * 100
        col_cells.append(f'{ct:6.1f}%')
        grand += ct
    print(f'ColTot | {"  | ".join(col_cells)}  | {grand:6.1f}%')
    
    # Key combos
    q1h_q4l = ((hdf['high_q'] == 0) & (hdf['low_q'] == 3)).sum() / tot * 100
    q1l_q4h = ((hdf['low_q'] == 0) & (hdf['high_q'] == 3)).sum() / tot * 100
    q1h_q2q3l = ((hdf['high_q'] == 0) & (hdf['low_q'].isin([1, 2]))).sum() / tot * 100
    q1l_q2q3h = ((hdf['low_q'] == 0) & (hdf['high_q'].isin([1, 2]))).sum() / tot * 100
    
    print(f'  Q1H/Q4L: {q1h_q4l:.1f}%  |  Q1L/Q4H: {q1l_q4h:.1f}%  |  Q1H/Q2Q3L: {q1h_q2q3l:.1f}%  |  Q1L/Q2Q3H: {q1l_q2q3h:.1f}%')
