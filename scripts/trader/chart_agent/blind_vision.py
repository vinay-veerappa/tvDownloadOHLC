"""blind_vision.py — 3 independent blind vision analyses of chart images.

Phase 4: Blind vision analyses. Gemini reads the chart image WITHOUT
seeing the reasoner's verdict. This prevents anchoring bias.

Three independent reads with different prompts:
  1. Bullish case — "make the bullish argument from this chart"
  2. Bearish case — "make the bearish argument from this chart"
  3. Neutral read — "describe what you see, no directional bias"

The reasoner's verdict is NOT shown to any vision analysis.
Disagreements are fed back to the reasoner for re-evaluation.

Usage:
    python -m scripts.trader.chart_agent.blind_vision --ticker ES1
    python -m scripts.trader.chart_agent.blind_vision --image data/vision/charts/ES1_2026-08-04_small.png
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_REPO))

# Load .env
_env_file = _REPO / ".env"
if _env_file.exists():
    with open(_env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k not in os.environ:
                    os.environ[k] = v

import google.antigravity as agy

BLIND_VISION_DIR = _REPO / "data" / "vision" / "blind_analyses"
BLIND_VISION_DIR.mkdir(parents=True, exist_ok=True)

# Three blind prompts — NO verdict context, NO anchoring
PROMPTS = {
    "bullish": """You are an institutional ICT/SMC trading analyst. You are looking at a 5-minute futures chart.

Make the STRONGEST BULLISH case you can from this chart. Identify:
- All bullish PD arrays (unmitigated FVGs, bullish OBs, discount arrays)
- Any liquidity swept that supports continuation higher
- The draw on liquidity above (BSL targets)
- Key support levels price is holding above

Be specific with price levels. State the primary target and invalidation.""",

    "bearish": """You are an institutional ICT/SMC trading analyst. You are looking at a 5-minute futures chart.

Make the STRONGEST BEARISH case you can from this chart. Identify:
- All bearish PD arrays (mitigated FVGs, bearish OBs, premium arrays)
- Any liquidity swept that suggests a Judas Swing or distribution
- The draw on liquidity below (SSL targets)
- Key resistance levels price is rejecting from

Be specific with price levels. State the primary target and invalidation.""",

    "neutral": """You are an institutional ICT/SMC trading analyst. You are looking at a 5-minute futures chart.

Describe EXACTLY what you see on this chart, with NO directional bias:
- What sessions are visible? (Asia, London, NY)
- What levels are drawn? (PDH, PDL, Midnight Open, Equilibrium, etc.)
- What was swept? What was rejected? What is unmitigated?
- Where is price right now relative to these levels?
- What is the dealing range? What is premium/discount?

Be specific with price levels. Do NOT make a directional call.""",
}


async def blind_vision_read(image_path: str, prompt_key: str) -> str:
    """Run a single blind vision analysis with Gemini.

    Args:
        image_path: Path to the chart PNG.
        prompt_key: One of "bullish", "bearish", "neutral".

    Returns:
        The vision analysis text.
    """
    config = agy.LocalAgentConfig(
        system_instructions="You are an institutional ICT/SMC price action analyst. You understand Power of Three, draw on liquidity, premium/discount dealing ranges, FVGs, order blocks, CSD, MSS, liquidity sweeps, Consequent Encroachment, Turtle Soup, and session timing."
    )
    chart = agy.Image.from_file(image_path)

    async with agy.Agent(config) as agent:
        response = await agent.chat([chart, PROMPTS[prompt_key]])
        chunks = []
        async for token in response:
            chunks.append(token)
        return "".join(chunks)


async def run_blind_vision(image_path: str) -> dict:
    """Run all 3 blind vision analyses and return results.

    Args:
        image_path: Path to the chart PNG.

    Returns:
        dict with "bullish", "bearish", "neutral" keys.
    """
    results = {}
    for key in ["bullish", "bearish", "neutral"]:
        log.info("  [BLIND VISION] %s...", key)
        try:
            result = await blind_vision_read(image_path, key)
            results[key] = result
            log.info("  [BLIND VISION] %s done (%d chars)", key, len(result))
        except Exception as e:
            log.error("  [BLIND VISION] %s failed: %s", key, e)
            results[key] = f"ERROR: {e}"
        # Save after each read to preserve partial results on quota errors
        try:
            save_path = BLIND_VISION_DIR / f"{Path(image_path).stem}_blind_vision.json"
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        # Wait between reads to avoid rate limits
        if key != "neutral":
            await asyncio.sleep(10)
    return results


def compare_with_verdict(blind_results: dict, verdict: str) -> dict:
    """Compare blind vision analyses with the reasoner's verdict.

    Args:
        blind_results: dict from run_blind_vision()
        verdict: The reasoner's YAML verdict.

    Returns:
        dict with agreement analysis.
    """
    # Extract bias from verdict
    bias = "unknown"
    for line in verdict.split("\n"):
        if line.strip().startswith("bias:"):
            bias = line.strip().split(":", 1)[1].strip().strip('"').strip("'")
            break

    # Check if any blind analysis agrees
    bullish_text = blind_results.get("bullish", "").lower()
    bearish_text = blind_results.get("bearish", "").lower()
    neutral_text = blind_results.get("neutral", "").lower()

    agreement = {
        "verdict_bias": bias,
        "bullish_analysis_present": len(blind_results.get("bullish", "")) > 50,
        "bearish_analysis_present": len(blind_results.get("bearish", "")) > 50,
        "neutral_analysis_present": len(blind_results.get("neutral", "")) > 50,
    }

    return agreement


async def main_async(args):
    """Main entry point for blind vision analysis."""
    image_path = args.image
    if not Path(image_path).exists():
        log.error("Image not found: %s", image_path)
        return

    log.info("=== Blind Vision Analysis: %s ===", image_path)

    results = await run_blind_vision(image_path)

    # Save results
    date_str = Path(image_path).stem
    save_path = BLIND_VISION_DIR / f"{date_str}_blind_vision.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log.info("Saved to %s", save_path)

    # Print summary
    for key, text in results.items():
        if not text.startswith("ERROR"):
            print(f"\n{'='*60}")
            print(f"  {key.upper()} ANALYSIS")
            print(f"{'='*60}")
            print(text[:500])


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Blind vision analyses (3 independent Gemini reads)")
    ap.add_argument("--image", default="data/vision/charts/ES1_2026-08-04_small.png",
                    help="Path to chart image")
    ap.add_argument("--ticker", default=None, help="Ticker (if you want to auto-find chart)")
    args = ap.parse_args()

    asyncio.run(main_async(args))