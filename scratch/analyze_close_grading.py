import pandas as pd
import numpy as np

# Load 1m data to find the 16:00 close price for each logical date
# We can load the NQ1 features or 1m data. Let's see how loaders do it.
from scripts.edgeful.lib.data_loader import get_loader
loader = get_loader()
df_1m = loader.load_1m("NQ1", "2020-01-01", "2026-06-01")

# Group by logical date and find the close at the last bar of the outcome window (15:59 ET)
# In New York time, the last bar in the outcome window is 15:59.
# Let's import normalize_to_eastern and get_logical_trading_date
from scripts.libs_py.nqstats.sessions import normalize_to_eastern, get_logical_trading_date
df_1m_et = normalize_to_eastern(df_1m)
df_1m_et['logical_date'] = get_logical_trading_date(df_1m_et.index)
df_1m_et['datetime'] = df_1m_et.index
df_1m_et['time_str'] = df_1m_et['datetime'].dt.strftime('%H:%M')

# Find close at 15:59:00 for each day
# If 15:59 is missing, take the last close of that logical date before 16:01
df_outcome_bars = df_1m_et[(df_1m_et['time_str'] >= '09:30') & (df_1m_et['time_str'] <= '15:59')]
last_bar_close = df_outcome_bars.groupby('logical_date')['close'].last()

# Load facts
df_facts = pd.read_parquet("data/derived/ib_facts_NQ1.parquet")
df_facts = df_facts[df_facts['session_slot'] == 'NY AM IB']

# Merge last close
df_facts = df_facts.merge(last_bar_close.rename("close_1600"), left_on="trading_day", right_index=True, how="inner")

print(f"Loaded {len(df_facts)} days with close_1600.")

# Recalculate Play 1 win rate
# Play 1 config:
# entry = ib_high (if dir=1) or ib_low (if dir=-1)
# target = ib_high + ib_range (dir=1) or ib_low - ib_range (dir=-1)
# stop = ib_low (dir=1) or ib_high (dir=-1)
# outcome has 'play1_result'

for play_n in [1, 2, 3]:
    df_play = pd.read_parquet("data/derived/ib_play_detail_NQ1.parquet")
    df_play = df_play[(df_play['session_slot'] == 'NY AM IB') & (df_play['play'] == play_n)]
    
    # Merge entry_price and close_1600
    # Let's map facts details:
    facts_map = df_facts[['trading_day', 'ib_high', 'ib_low', 'ib_mid', 'ib_range', 'first_break_dir', 'first_break_idx', 'double_break', 'close_1600']].copy()
    sub_play = df_play.merge(facts_map, on="trading_day", how="inner")
    
    # Setup play prices
    if play_n == 1:
        entry = np.where(sub_play['first_break_dir'] == 1, sub_play['ib_high'], sub_play['ib_low'])
        target = np.where(sub_play['first_break_dir'] == 1, sub_play['ib_high'] + sub_play['ib_range'], sub_play['ib_low'] - sub_play['ib_range'])
        stop = np.where(sub_play['first_break_dir'] == 1, sub_play['ib_low'], sub_play['ib_high'])
        direction = sub_play['first_break_dir']
    elif play_n == 2:
        entry = sub_play['ib_mid']
        target = np.where(sub_play['first_break_dir'] == 1, sub_play['ib_high'] + 0.5 * sub_play['ib_range'], sub_play['ib_low'] - 0.5 * sub_play['ib_range'])
        stop = np.where(sub_play['first_break_dir'] == 1, sub_play['ib_low'], sub_play['ib_high'])
        direction = sub_play['first_break_dir']
    else: # Play 3
        entry = np.where(sub_play['first_break_dir'] == 1, sub_play['ib_high'], sub_play['ib_low'])
        target = sub_play['ib_mid']
        stop = np.where(sub_play['first_break_dir'] == 1, sub_play['ib_high'] + 0.5 * sub_play['ib_range'], sub_play['ib_low'] - 0.5 * sub_play['ib_range'])
        direction = -sub_play['first_break_dir']

    # Let's check how many times target was hit vs stop was hit vs neither
    # We can read 'result' in sub_play. In original code:
    # result = 1 if target hit first. result = -1 if stop hit first or neither hit.
    # So if result == 1 -> target was hit.
    # If result == -1: we want to check if stop was hit. If stop was NOT hit, then it was a no-hit day.
    # How do we know if stop was hit? We can check if mae_pct is greater than the stop distance!
    # Entry to stop distance in percent of ib_mid:
    # stop_dist_pct = abs(entry - stop) / ib_mid * 100
    stop_dist_pct = np.abs(entry - stop) / sub_play['ib_mid'] * 100
    stop_hit_by_mae = sub_play['mae'] >= stop_dist_pct - 1e-5
    
    # Target distance in percent of ib_mid
    tgt_dist_pct = np.abs(target - entry) / sub_play['ib_mid'] * 100
    tgt_hit_by_mfe = sub_play['mfe'] >= tgt_dist_pct - 1e-5

    target_hit = sub_play['result'] == 1
    # If target_hit is False, did it hit stop?
    stop_hit = (~target_hit) & stop_hit_by_mae
    neither_hit = (~target_hit) & (~stop_hit_by_mae)
    
    # Recalculate original wr
    orig_active = sub_play[sub_play['result'] != 0]
    orig_wr = len(orig_active[orig_active['result'] == 1]) / len(orig_active) * 100
    
    # Recalculate with close grading for neither_hit days
    # For neither_hit days, if direction == 1: win if close_1600 > entry, else loss
    # If direction == -1: win if close_1600 < entry, else loss
    close_is_win = np.where(direction == 1, sub_play['close_1600'] > entry, sub_play['close_1600'] < entry)
    
    new_result = np.where(target_hit, 1, np.where(stop_hit, -1, np.where(close_is_win, 1, -1)))
    new_wr = np.sum(new_result == 1) / len(new_result) * 100
    
    print(f"\nPlay {play_n} (NY AM IB):")
    print(f"  Total Active: {len(sub_play)}")
    print(f"  Target Hit: {np.sum(target_hit)} ({np.sum(target_hit)/len(sub_play)*100:.2f}%)")
    print(f"  Stop Hit: {np.sum(stop_hit)} ({np.sum(stop_hit)/len(sub_play)*100:.2f}%)")
    print(f"  Neither Hit: {np.sum(neither_hit)} ({np.sum(neither_hit)/len(sub_play)*100:.2f}%)")
    print(f"    Of which Closed in Profit: {np.sum(neither_hit & close_is_win)} ({np.sum(neither_hit & close_is_win)/np.sum(neither_hit)*100 if np.sum(neither_hit) > 0 else 0.0:.2f}%)")
    print(f"  Original Win Rate (neither=loss): {orig_wr:.2f}%")
    print(f"  New Win Rate (neither=close): {new_wr:.2f}%")
