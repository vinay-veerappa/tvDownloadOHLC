import pandas as pd
import numpy as np

# Load facts
df_facts = pd.read_parquet("data/derived/ib_facts_NQ1.parquet")
df_facts = df_facts[df_facts['session_slot'] == 'NY AM IB']

# Load 1m bars to check close prices at 16:00
# Actually, wait, does facts_df have ib_close, ib_high, ib_low, and what else?
# Let's check the columns in facts_df
print("Columns in facts_df:")
print(list(df_facts.columns))

# Let's calculate the outcome at 16:00 close if we can
# facts_df has 'ib_high', 'ib_low', 'ib_range', 'ib_close' (close at 10:30), etc.
# Wait, does facts_df have the 16:00 close?
# In ib.py, facts_df is facts_df = ib_agg.reset_index().
# Let's check if there is a 'close' or 'close_1600' column in facts_df.
# Wait, is 'max_high' and 'min_low' there? Yes.
# Is 'ib_close' there? Yes, but that's the close of the IB window (10:30).
# Let's check if there is a daily close or if we need to load 1m data to check the 16:00 close.
