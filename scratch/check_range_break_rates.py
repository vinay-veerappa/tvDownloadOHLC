import pandas as pd
import numpy as np

# Load facts
df_facts = pd.read_parquet("data/derived/ib_facts_NQ1.parquet")
df_facts = df_facts[df_facts['session_slot'] == 'NY AM IB']

print("Range Bucket Detailed Break Rates for NY AM IB (NQ1):")
grouped = df_facts.groupby('range_bucket_full')
for name, group in grouped:
    n = len(group)
    high_broke = np.sum((group['first_break_dir'] == 1) | group['double_break'])
    low_broke = np.sum((group['first_break_dir'] == -1) | group['double_break'])
    db = np.sum(group['double_break'])
    
    hb_rate = high_broke / n * 100 if n > 0 else 0.0
    lb_rate = low_broke / n * 100 if n > 0 else 0.0
    db_rate = db / n * 100 if n > 0 else 0.0
    any_broke = np.sum(group['first_break_dir'] != 0)
    any_rate = any_broke / n * 100 if n > 0 else 0.0
    
    print(f"Bucket: {name:10} | N: {n:5} | High Break: {hb_rate:.2f}% | Low Break: {lb_rate:.2f}% | Double Break: {db_rate:.2f}% | Any Break: {any_rate:.2f}%")
