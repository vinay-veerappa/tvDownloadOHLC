"""Run 3 blind vision reads and save."""
import asyncio
import json
import os
from pathlib import Path

_REPO = Path(__file__).parent.parent.parent.parent
_env = _REPO / ".env"
if _env.exists():
    with open(_env, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k not in os.environ:
                    os.environ[k] = v

import google.antigravity as agy

PROMPTS = {
    "bullish": "Make the STRONGEST BULLISH case from this chart. Be specific with price levels.",
    "bearish": "Make the STRONGEST BEARISH case from this chart. Be specific with price levels.",
    "neutral": "Describe exactly what you see on this chart, no directional bias.",
}


async def run():
    img = agy.Image.from_file("data/vision/charts/ES1_2026-08-04_small.png")
    config = agy.LocalAgentConfig(system_instructions="You are an institutional ICT/SMC analyst.")
    results = {}
    for key, prompt in PROMPTS.items():
        async with agy.Agent(config) as agent:
            resp = await agent.chat([img, prompt])
            chunks = []
            async for t in resp:
                chunks.append(t)
            results[key] = "".join(chunks)
            print(f"{key}: {len(results[key])} chars")

    out = _REPO / "data" / "vision" / "blind_analyses"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "test_blind.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    for k, v in results.items():
        print(f"\n=== {k.upper()} ===")
        print(v[:300])


asyncio.run(run())