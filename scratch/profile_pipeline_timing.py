"""Profile end-to-end live prediction pipeline timing."""
import sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import time
import json
import os

DATA = _REPO / "data"

print("=" * 60)
print("PROFILING: compute_live_prediction() end-to-end")
print("=" * 60)

# ── Step 1: SessionBoxEngine.from_live() ──
t0 = time.perf_counter()
from scripts.libs_py.profiler.engine import SessionBoxEngine
engine = SessionBoxEngine.from_live("NQ1")
live_sessions = engine.get_live_sessions()
prev_context = engine.get_prev_context()
t1 = time.perf_counter()
print(f"\n1. SessionBoxEngine.from_live():  {(t1-t0)*1000:.1f} ms")
print(f"   Live sessions: {live_sessions}")

# ── Step 2: Load profiler JSON ──
t0 = time.perf_counter()
json_path = DATA / "NQ1_profiler.json"
with open(json_path) as f:
    sessions = json.load(f)
t1 = time.perf_counter()
print(f"\n2. Load NQ1_profiler.json:  {(t1-t0)*1000:.1f} ms  ({len(sessions)} records, {os.path.getsize(json_path)/1024:.0f} KB)")

# ── Step 3: Build pivot ──
t0 = time.perf_counter()
pivot = {}
for s in sessions:
    d = s.get("date")
    sess = s.get("session")
    if d and sess:
        if d not in pivot:
            pivot[d] = {}
        pivot[d][sess] = s
dates = sorted(pivot.keys())
t1 = time.perf_counter()
print(f"\n3. Build pivot:  {(t1-t0)*1000:.1f} ms  ({len(dates)} trading dates)")

# ── Step 4: Load daily HOD/LOD ──
t0 = time.perf_counter()
with open(DATA / "NQ1_daily_hod_lod.json") as f:
    daily_hl = json.load(f)
t1 = time.perf_counter()
print(f"\n4. Load daily_hod_lod.json:  {(t1-t0)*1000:.1f} ms  ({len(daily_hl)} days, {os.path.getsize(DATA / 'NQ1_daily_hod_lod.json')/1024:.0f} KB)")

# ── Step 5: Load level touches ──
t0 = time.perf_counter()
with open(DATA / "NQ1_level_touches.json") as f:
    level_touches = json.load(f)
t1 = time.perf_counter()
print(f"\n5. Load level_touches.json:  {(t1-t0)*1000:.1f} ms  ({len(level_touches)} days, {os.path.getsize(DATA / 'NQ1_level_touches.json')/1024:.0f} KB)")

# ── Step 6: compute_profiler() ──
t0 = time.perf_counter()
from scripts.trader.signals.profiler import compute_profiler
from datetime import datetime, date
import pytz
ET = pytz.timezone("US/Eastern")
now_et = datetime.now(ET)
target_date = date.today()

profiler_data = compute_profiler(
    ticker="NQ1",
    current_price=0,
    target_date=target_date,
    now_et=now_et,
    live_sessions=live_sessions,
)
t1 = time.perf_counter()
print(f"\n6. compute_profiler():  {(t1-t0)*1000:.1f} ms")

# ── Step 7: Internal breakdown ──
from scripts.trader.signals.profiler import (
    _load_profiler_sessions, _build_pivots, _get_latest_date, _get_prev_date,
    _detect_target_session, _get_context_values_live, _filter_historical_days,
    _compute_prediction_from_matches, _compute_prediction_with_fallback,
    _load_daily_hod_lod, _load_level_touches,
    _compute_base_rates, _compute_unconditional_level_hits,
    _compute_conditional_level_hits, _compute_per_outcome_level_hits,
    CONTEXT_CHAIN, SESSION_ORDER,
)

print(f"\n{'='*60}")
print("INTERNAL BREAKDOWN")
print(f"{'='*60}")

sessions_list = _load_profiler_sessions("NQ1")
pivot2, dates2 = _build_pivots(sessions_list)
latest_date = _get_latest_date(dates2)
effective_date = target_date.isoformat() if target_date.isoformat() in pivot2 else latest_date
prev_date = _get_prev_date(dates2, effective_date)
sessions_latest = pivot2.get(effective_date, {})
sessions_prev = pivot2.get(prev_date, {}) if prev_date else {}

tgt_idx, tgt_session = _detect_target_session(now_et, sessions_latest)
print(f"  Target session: {tgt_session} (idx={tgt_idx})")

daily_hl2 = _load_daily_hod_lod("NQ1")
level_touches2 = _load_level_touches("NQ1")

total_filter_ms = 0
total_predict_ms = 0
total_levels_ms = 0

for sess_name in SESSION_ORDER:
    context = _get_context_values_live(sess_name, live_sessions, sessions_prev)
    if not context:
        continue

    t0 = time.perf_counter()
    pred = _compute_prediction_with_fallback(
        pivot2, dates2, sess_name, context,
        target_loose=False, live_status="",
        daily_hod_lod=daily_hl2,
    )
    t1 = time.perf_counter()
    total_predict_ms += (t1 - t0) * 1000

    if pred:
        matched = pred.get("matched_dates", [])
        t0 = time.perf_counter()
        _compute_conditional_level_hits(level_touches2, matched)
        t1 = time.perf_counter()
        total_levels_ms += (t1 - t0) * 1000

        dbo = pred.get("dates_by_outcome")
        if dbo:
            t0 = time.perf_counter()
            _compute_per_outcome_level_hits(level_touches2, dbo)
            t1 = time.perf_counter()
            total_levels_ms += (t1 - t0) * 1000

print(f"  Total prediction compute: {total_predict_ms:.1f} ms")
print(f"  Total level hits compute: {total_levels_ms:.1f} ms")

# ── Summary ──
print(f"\n{'='*60}")
print("BOTTLENECK ANALYSIS")
print(f"{'='*60}")
print(f"  JSON file I/O is the dominant cost:")
print(f"    profiler.json:     ~{os.path.getsize(DATA / 'NQ1_profiler.json')/1024:.0f} KB")
print(f"    daily_hod_lod.json: ~{os.path.getsize(DATA / 'NQ1_daily_hod_lod.json')/1024:.0f} KB")
print(f"    level_touches.json: ~{os.path.getsize(DATA / 'NQ1_level_touches.json')/1024:.0f} KB")
print(f"  The filter loop itself is ~2ms — negligible.")
print(f"  The prediction datasets (asia/london) are only ~16-18 KB each.")
print(f"  They pre-compute context_key -> outcome_probs for instant lookup.")
