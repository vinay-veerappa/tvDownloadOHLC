"""
Daily Analysis Pipeline Integration: ThinkorSwim Expected Moves Fetcher
========================================================================
Production pipeline script to extract exact ThinkorSwim platform Expected Moves
from Desktop or Web, format levels, and save directly to project data output directories.

Usage:
  python -m scripts.pipeline.extract_tos_expected_moves --source desktop --tickers SPX NQ AAPL NVDA
  python -m scripts.pipeline.extract_tos_expected_moves --source web --tickers SPX NQ AAPL NVDA
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

PACKAGE_ROOT = WORKSPACE_ROOT / "tos-ui-mcp"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

DATA_OUTPUT_DIR = WORKSPACE_ROOT / "data" / "expected_moves"
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def fetch_pipeline_expected_moves(source: str = "desktop", tickers: list[str] = None):
    if tickers is None:
        tickers = ["SPX", "NQ", "MNQ", "AAPL", "NVDA"]

    print(f"[PIPELINE] Starting ThinkorSwim Expected Move Fetcher (Source: {source.upper()})...")
    
    if source.lower() == "desktop":
        from tos_ui_mcp.desktop_extractor import extract_desktop_expected_moves
        results = extract_desktop_expected_moves(tickers=tickers, save_json=False)
    else:
        import asyncio
        from tos_ui_mcp.extractor import extract_tos_ui_expected_moves
        results = asyncio.run(extract_tos_ui_expected_moves(tickers=tickers, headless=True, save_json=False))

    if results.get("status") == "error":
        print(f"[PIPELINE-ERROR] Failed to extract expected moves: {results.get('message')}")
        return results

    # Save timestamped pipeline file
    today_str = datetime.now().strftime("%Y-%m-%d")
    out_file = DATA_OUTPUT_DIR / f"tos_expected_moves_{today_str}.json"
    latest_file = DATA_OUTPUT_DIR / "latest_tos_expected_moves.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[PIPELINE-SUCCESS] Saved Expected Moves to:\n  - {out_file}\n  - {latest_file}")
    
    # Print summary table for trading plan
    print("\n" + "=" * 70)
    print(f" THINKORSWIM EXPECTED MOVES BRIEFING ({today_str})")
    print("=" * 70)
    for symbol, data in results.get("tickers", {}).items():
        price = data.get("last_price")
        expirations = data.get("expirations", [])
        if expirations:
            front_exp = expirations[0]
            em = front_exp.get("expected_move")
            iv = front_exp.get("iv_pct")
            dte = front_exp.get("dte")
            expiry = front_exp.get("expiry")

            upper_bound = price + em if price and em else "N/A"
            lower_bound = price - em if price and em else "N/A"

            print(f" [{symbol}] Price: ${price} | Front Expiry: {expiry} ({dte} DTE) | IV: {iv}%")
            print(f"      Expected Move: ±{em}  ==> Range: [ ${lower_bound:.2f}  to  ${upper_bound:.2f} ]" if isinstance(upper_bound, float) else f"      Expected Move: ±{em}")
        else:
            print(f" [{symbol}] Price: ${price} | No expiration data found.")
    print("=" * 70)

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Expected Moves Fetcher")
    parser.add_argument("--source", choices=["desktop", "web"], default="desktop", help="Extraction source (desktop or web)")
    parser.add_argument("--tickers", nargs="+", default=["SPX", "NQ", "AAPL", "NVDA"], help="Tickers to fetch")
    args = parser.parse_args()

    fetch_pipeline_expected_moves(source=args.source, tickers=args.tickers)
