"""Quick reasoner comparison script — runs all available reasoners and prints bias."""
import sys, os, json, time
sys.path.insert(0, ".")
from scripts.trader.chart_agent.agent_loop import get_available_models, run_reasoner

models = get_available_models()
reasoners = models["reasoners"]
print("Available reasoners:", [m["name"] for m in reasoners])
print()

for m in reasoners:
    try:
        t0 = time.time()
        verdict = run_reasoner("ES1", m)
        elapsed = time.time() - t0
        bias = "UNKNOWN"
        for line in verdict.split("\n"):
            if line.strip().startswith("bias:"):
                bias = line.strip()
                break
        print(f'{m["name"]} ({m["provider"]}): {elapsed:.1f}s, {len(verdict)} chars -> {bias}')
    except Exception as e:
        print(f'{m["name"]} ({m["provider"]}): ERROR - {str(e)[:100]}')