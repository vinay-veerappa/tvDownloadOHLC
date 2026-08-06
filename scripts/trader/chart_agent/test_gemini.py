"""Quick test of Gemini vision SDK."""
import asyncio, os, sys
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

sys.path.insert(0, str(_REPO))
import google.antigravity as agy

async def test():
    img = agy.Image.from_file("data/vision/charts/ES1_2026-08-04_small.png")
    config = agy.LocalAgentConfig(system_instructions="You are an ICT analyst.")
    async with agy.Agent(config) as agent:
        resp = await agent.chat([img, "What bias do you see? Bullish or bearish? Be concise."])
        chunks = []
        async for t in resp:
            chunks.append(t)
        return "".join(chunks)

result = asyncio.run(test())
print(result[:300])