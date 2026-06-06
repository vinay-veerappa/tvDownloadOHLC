import pandas as pd
import numpy as np

# Let's inspect facts_df columns and values for NQ1 NY AM IB
df_facts = pd.read_parquet("data/derived/ib_facts_NQ1.parquet")
df_facts = df_facts[df_facts['session_slot'] == 'NY AM IB']

# Play 1 results count
tot = len(df_facts)
p1_active = df_facts[df_facts['play1_result'] != 0]
p1_win = df_facts[df_facts['play1_result'] == 1]
p1_loss = df_facts[df_facts['play1_result'] == -1]

print("Play 1 (NY AM IB):")
print(f"  Total days: {tot}")
print(f"  Active days: {len(p1_active)}")
print(f"  Wins: {len(p1_win)}")
print(f"  Losses: {len(p1_loss)}")
print(f"  Win Rate: {len(p1_win)/len(p1_active)*100:.2f}%")

# Let's check how many times price actually broke high vs low
print("\nFirst Break Direction:")
print(df_facts['first_break_dir'].value_counts())

# Let's check double breaks
print("\nDouble Breaks:")
print(df_facts['double_break'].value_counts())
