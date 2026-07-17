"""Benchmark vectorized vs original profiler pipeline."""
import sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import time
import json
import pandas as pd
from collections import defaultdict

DATA_DIR = _REPO / "data"

# Load data once
with open(DATA_DIR / "NQ1_profiler.json") as f:
    sessions = json.load(f)

# Build pivot (same as _build_pivots)
pivot = {}
for s in sessions:
    d = s.get("date")
    sess = s.get("session")
    if d and sess:
        if d not in pivot:
            pivot[d] = {}
        pivot[d][sess] = s
dates = sorted(pivot.keys())

# Context: Asia=ST, London=SF, NY1=SF (today's live context)
context_values = [
    ("Asia", "Short True", False),
    ("London", "Short False", False),
    ("NY1", "Short False", False),
]
target_session = "NY2"

# ── OLD: Python for loop ──
def old_filter(pivot, dates, target_session, context_values):
    ctx_map = {sess: (status, broken) for sess, status, broken in context_values}
    chain = [("curr:Asia", "Asia"), ("curr:London", "London"), ("curr:NY1", "NY1")]
    prev_sessions = set()
    for ctx_spec, sess_name in chain:
        if ctx_spec.startswith("prev:"):
            prev_sessions.add(sess_name)

    matched = []
    for i, curr_date in enumerate(dates):
        if i == 0:
            continue
        prev_date = dates[i - 1]
        ok = True
        for sess_name, (live_status, live_broken) in ctx_map.items():
            if sess_name in prev_sessions:
                hist_rec = pivot.get(prev_date, {}).get(sess_name, {})
            else:
                hist_rec = pivot.get(curr_date, {}).get(sess_name, {})
            hist_status = hist_rec.get("status", "")
            hist_broken = hist_rec.get("broken", False)
            if hist_status != live_status:
                ok = False
                break
            if live_broken and not hist_broken:
                ok = False
                break
        if ok:
            matched.append(curr_date)
    return matched

# ── NEW: Vectorized ──
def new_filter(pivot, dates, target_session, context_values):
    ctx_map = {sess: (status, broken) for sess, status, broken in context_values}
    chain = [("curr:Asia", "Asia"), ("curr:London", "London"), ("curr:NY1", "NY1")]
    prev_sessions = set()
    for ctx_spec, sess_name in chain:
        if ctx_spec.startswith("prev:"):
            prev_sessions.add(sess_name)

    rows = []
    for d in dates:
        day = pivot.get(d, {})
        row = {"date": d}
        for sess_name in ctx_map:
            rec = day.get(sess_name, {})
            row[f"{sess_name}_status"] = rec.get("status", "")
            row[f"{sess_name}_broken"] = bool(rec.get("broken", False))
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return []

    for sess_name in prev_sessions:
        status_col = f"{sess_name}_status"
        broken_col = f"{sess_name}_broken"
        if status_col in df.columns:
            df[f"prev_{status_col}"] = df[status_col].shift(1)
            df[f"prev_{broken_col}"] = df[broken_col].shift(1)

    mask = pd.Series(True, index=df.index)
    for sess_name, (live_status, live_broken) in ctx_map.items():
        if sess_name in prev_sessions:
            hist_status_col = f"prev_{sess_name}_status"
            hist_broken_col = f"prev_{sess_name}_broken"
        else:
            hist_status_col = f"{sess_name}_status"
            hist_broken_col = f"{sess_name}_broken"

        if hist_status_col not in df.columns:
            continue

        hist_status = df[hist_status_col].fillna("")
        hist_broken = df[hist_broken_col].fillna(False)
        status_mask = hist_status == live_status
        if live_broken:
            broken_mask = hist_broken
            mask = mask & status_mask & broken_mask
        else:
            mask = mask & status_mask

    mask.iloc[0] = False
    return df.loc[mask, "date"].tolist()

# ── Benchmark ──
print(f"Dates: {len(dates)} | Context: {[(s, st) for s, st, _ in context_values]}")

# Warmup
old_filter(pivot, dates, target_session, context_values)
new_filter(pivot, dates, target_session, context_values)

# Old
t0 = time.perf_counter()
for _ in range(100):
    old_result = old_filter(pivot, dates, target_session, context_values)
t_old = (time.perf_counter() - t0) / 100
print(f"OLD (Python loop): {t_old*1000:.2f} ms  → {len(old_result)} matches")

# New
t0 = time.perf_counter()
for _ in range(100):
    new_result = new_filter(pivot, dates, target_session, context_values)
t_new = (time.perf_counter() - t0) / 100
print(f"NEW (vectorized):  {t_new*1000:.2f} ms  → {len(new_result)} matches")

# Verify same results
assert set(old_result) == set(new_result), "RESULTS DIFFER!"
print(f"\nSpeedup: {t_old/t_new:.1f}x")
print("Results match ✓")
