"""
ThinkorSwim Web UI Expected Move MCP Server
============================================
FastMCP server tool exposing extract_expected_moves_from_tos_ui for AI agents and scripts.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from fastmcp import FastMCP

# Ensure repository root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.market_data.tos_web_ui_extractor import extract_tos_ui_expected_moves

mcp = FastMCP("TOS-UI-ExpectedMove-Extractor")

@mcp.tool()
def extract_expected_moves_from_tos_ui(
    tickers: list[str],
    headless: bool = True,
    output_file: str = "data/tos_ui_expected_moves.json"
) -> str:
    """
    Launches ThinkorSwim Web App (trade.thinkorswim.com) via Playwright, navigates to option chains
    for the given tickers, extracts exact platform-rendered Expected Move values (± XX.XX) from the UI,
    and saves the structured output to JSON.

    Parameters:
      tickers: List of symbols, e.g. ["SPX", "NQ", "ES", "AAPL", "NVDA"]
      headless: Set to True for background execution, False to see browser
      output_file: Relative or absolute path to save the output JSON file
    """
    output_path = Path(BASE_DIR) / output_file if not os.path.isabs(output_file) else Path(output_file)
    
    # Run async extractor
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        data = loop.run_until_complete(
            extract_tos_ui_expected_moves(tickers=tickers, headless=headless, save_json=True)
        )
    finally:
        loop.close()

    if data.get("status") == "error":
        return f"[ERROR] {data.get('message')}"

    ticker_count = len(data.get("tickers", {}))
    return f"[SUCCESS] Successfully extracted TOS UI Expected Moves for {ticker_count} tickers. Output saved to {output_path}."

if __name__ == "__main__":
    mcp.run()
