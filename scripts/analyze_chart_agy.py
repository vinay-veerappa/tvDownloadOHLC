#!/usr/bin/env python3
"""
Chart Vision Analysis Script using Antigravity Python SDK (google-antigravity)

Usage:
  python scripts/analyze_chart_agy.py [--image PATH] [--prompt "YOUR PROMPT"]

Requirements:
  Set environment variable:
       PowerShell: $env:GEMINI_API_KEY="your_api_key"
       CMD:        set GEMINI_API_KEY=your_api_key
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

async def main():
    parser = argparse.ArgumentParser(description="Analyze chart images using google-antigravity Python SDK.")
    parser.add_argument(
        "--image",
        type=str,
        default="data/vision/charts/ES1_2026-08-04_small.png",
        help="Path to the chart image file",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Describe the price action, key ICT levels (PDH, PDL, Equilibrium, FVGs), and overall market bias.",
        help="Prompt text for the vision agent",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n[ERROR] GEMINI_API_KEY environment variable is missing.", file=sys.stderr)
        print("Set it in PowerShell before running:", file=sys.stderr)
        print('  $env:GEMINI_API_KEY="your_free_api_key_from_aistudio"\n', file=sys.stderr)
        sys.exit(1)

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"\n[ERROR] File not found: {image_path.resolve()}", file=sys.stderr)
        sys.exit(1)

    import google.antigravity as agy

    print(f"--> [AGY SDK] Loading image: {image_path}")
    print(f"--> [AGY SDK] Prompt: {args.prompt}\n")
    print("=" * 60)
    print("AGY VISION ANALYSIS:")
    print("=" * 60)

    # 1. Create LocalAgentConfig
    config = agy.LocalAgentConfig(
        system_instructions="You are an expert institutional ICT trading analyst."
    )

    # 2. Load chart image using AGY SDK
    chart_image = agy.Image.from_file(str(image_path))

    # 3. Spawn AGY Agent and query
    async with agy.Agent(config) as agent:
        response = await agent.chat([chart_image, args.prompt])
        async for token in response:
            sys.stdout.write(token)
            sys.stdout.flush()
        print()
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
