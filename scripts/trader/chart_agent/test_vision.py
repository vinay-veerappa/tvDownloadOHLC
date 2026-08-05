"""Test vision verifier with Gemini SDK."""
import os
os.environ["GEMINI_API_KEY"] = "***REMOVED-ROTATED-KEY***"

import sys, time
sys.path.insert(0, ".")
from scripts.trader.chart_agent.agent_loop import get_available_models, run_vision_verifier
from pathlib import Path

models = get_available_models()
print("Vision models:", [m["name"] for m in models["vision"]])

sample_verdict = """bias: bearish
primary_pd_array: Daily SSL (7629.00)
htf_story: Price in deep premium after Judas Swing sweep of Asia High to 7799.50, rejected back to Midnight Open."""

chart = Path("data/vision/charts/ES1_2026-08-04_small.png")
for vm in models["vision"][:1]:
    t0 = time.time()
    result = run_vision_verifier(chart, sample_verdict, vm)
    elapsed = time.time() - t0
    print(f'{vm["name"]} ({vm["provider"]}): {elapsed:.1f}s, {len(result)} chars')
    print("---")
    print(result[:800])