#!/usr/bin/env python3
"""
Chart Vision Analysis Script using Google Gemini API (google-genai)

Usage:
  python scripts/analyze_chart.py [--image PATH] [--prompt "YOUR PROMPT"] [--model MODEL_NAME]

Requirements:
  1. Get a free API key from Google AI Studio: https://aistudio.google.com/app/apikey
  2. Set environment variable:
       Windows PowerShell: $env:GEMINI_API_KEY="your_api_key_here"
       CMD:               set GEMINI_API_KEY=your_api_key_here
       Linux/macOS:       export GEMINI_API_KEY="your_api_key_here"
"""

import argparse
import os
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Analyze trading chart images using Google Gemini Vision.")
    parser.add_argument(
        "--image",
        type=str,
        default="data/vision/charts/ES1_2026-08-04_small.png",
        help="Path to the chart image file (default: data/vision/charts/ES1_2026-08-04_small.png)",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=(
            "Analyze this trading chart. Describe the price action, key ICT/SMC levels "
            "(PDH, PDL, Equilibrium, FVGs, Order Blocks), and determine the overall bias (Bullish/Bearish)."
        ),
        help="Prompt text for the vision model.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model name (default: gemini-2.5-flash)",
    )

    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n[ERROR] GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        print("\nTo fix this:", file=sys.stderr)
        print("  1. Get your free API key at: https://aistudio.google.com/app/apikey", file=sys.stderr)
        print("  2. Run in PowerShell:", file=sys.stderr)
        print('     $env:GEMINI_API_KEY="your_api_key_here"', file=sys.stderr)
        print(f"  3. Re-run: python {sys.argv[0]}\n", file=sys.stderr)
        sys.exit(1)

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"\n[ERROR] Image file not found: {image_path.resolve()}", file=sys.stderr)
        sys.exit(1)

    try:
        from PIL import Image
        from google import genai
    except ImportError as e:
        print(f"\n[ERROR] Missing required packages: {e}", file=sys.stderr)
        print("Run: pip install google-genai pillow", file=sys.stderr)
        sys.exit(1)

    print(f"--> Loading image: {image_path}")
    print(f"--> Using model: {args.model}")
    print(f"--> Prompt: {args.prompt}\n")
    print("=" * 60)
    print("ANALYSIS RESULTS:")
    print("=" * 60)

    img = Image.open(image_path)
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=args.model,
        contents=[img, args.prompt],
    )

    print(response.text)
    print("=" * 60)

if __name__ == "__main__":
    main()
