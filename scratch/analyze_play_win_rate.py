import pandas as pd
import numpy as np

# Load play detail
df_play = pd.read_parquet("data/derived/ib_play_detail_NQ1.parquet")
print("Play Detail Info:")
print(df_play.info())
print("\nOverall Play Win Rates:")
for play_n in [1, 2, 3]:
    sub = df_play[df_play['play'] == play_n]
    tot = len(sub)
    active = sub[sub['result'] != 0]
    wins = active[active['result'] == 1]
    losses = active[active['result'] == -1]
    
    wr = len(wins) / len(active) * 100 if len(active) > 0 else 0.0
    print(f"Play {play_n}: Total={tot}, Active={len(active)}, Wins={len(wins)}, Losses={len(losses)}, WinRate={wr:.2f}%")

print("\nWin Rates by Session Slot:")
for sess in df_play['session_slot'].unique():
    print(f"\n--- Session: {sess} ---")
    for play_n in [1, 2, 3]:
        sub = df_play[(df_play['play'] == play_n) & (df_play['session_slot'] == sess)]
        active = sub[sub['result'] != 0]
        wins = active[active['result'] == 1]
        wr = len(wins) / len(active) * 100 if len(active) > 0 else 0.0
        print(f"  Play {play_n}: Active={len(active)}, WinRate={wr:.2f}%")
