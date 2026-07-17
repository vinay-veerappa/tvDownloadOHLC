"""Final benchmark: compute_live_prediction with lookup table."""
import sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import time
from scripts.libs_py.profiler.live_prediction import compute_live_prediction

# Warmup
compute_live_prediction("NQ1")

# Benchmark
t0 = time.perf_counter()
pred = compute_live_prediction("NQ1")
t1 = time.perf_counter()

print(f"Total: {(t1-t0)*1000:.0f} ms")
print(f"Source: {pred.get('_source', '?')}")
print(f"Target: {pred['target_session']}")
print(f"Bias: {pred['bias']}")
print(f"Confidence: {pred['confidence']}")
tgt = pred["target_session"]
p = pred["predictions"].get(tgt, {})
print(f"Samples: {p.get('samples')}")
print(f"Probs: {p.get('probabilities')}")
print(f"Error: {pred.get('error')}")
