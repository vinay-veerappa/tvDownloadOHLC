"""Test vision verifier with Gemini SDK."""
import os
import sys
from pathlib import Path

# Load .env
_REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_REPO))
_env_file = _REPO / ".env"
if _env_file.exists():
    with open(_env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k not in os.environ:
                    os.environ[k] = v

import time
from scripts.trader.chart_agent.agent_loop import get_available_models, run_vision_verifier

models = get_available_models()
print("Vision models:", [m["name"] for m in models["vision"]])

sample_verdict = """bias: bearish
primary_pd_array: Daily SSL (7629.00)
htf_story: Price in deep premium after Judas Swing sweep of Asia High to 7799.50, rejected back to Midnight Open."""

chart = _REPO / "data" / "vision" / "charts" / "ES1_2026-08-04_small.png"
for vm in models["vision"][:1]:
    t0 = time.time()
    result = run_vision_verifier(chart, sample_verdict, vm)
    elapsed = time.time() - t0
    print(f'{vm["name"]} ({vm["provider"]}): {elapsed:.1f}s, {len(result)} chars')
    print("---")
    print(result[:800])