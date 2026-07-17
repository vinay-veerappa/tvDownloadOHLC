"""Verify lookup path with prev_sessions."""
import sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import time
from scripts.libs_py.profiler.engine import SessionBoxEngine
from scripts.trader.signals.profiler import compute_profiler
from datetime import datetime, date
import pytz

ET = pytz.timezone("US/Eastern")
now_et = datetime.now(ET)

e = SessionBoxEngine.from_live("NQ1")
live = e.get_live_sessions()
prev_ctx = e.get_prev_context()

# Convert prev_ctx to sessions_prev format
sessions_prev = {}
for key, val in prev_ctx.items():
    if key.startswith("prev_") and key.endswith("_status"):
        sess = key[5:-7]
        sess_name = {"ny1": "NY1", "ny2": "NY2", "asia": "Asia", "london": "London"}.get(sess, sess.upper())
        broken_key = f"prev_{sess}_broken"
        sessions_prev[sess_name] = {"status": val, "broken": prev_ctx.get(broken_key, False)}

print(f"Live: {live}")
print(f"Prev: {sessions_prev}")

t0 = time.perf_counter()
result = compute_profiler("NQ1", 0, date.today(), now_et, live, sessions_prev)
t1 = time.perf_counter()

print(f"\ncompute_profiler: {(t1-t0)*1000:.0f} ms")
print(f"Source: {result.get('_source')}")
print(f"Target: {result['target_session']}")
p = result["predictions"].get(result["target_session"], {})
print(f"Samples: {p.get('samples')}")
print(f"Probs: {p.get('probabilities')}")
print(f"Fallback: {p.get('fallback_level')}")
