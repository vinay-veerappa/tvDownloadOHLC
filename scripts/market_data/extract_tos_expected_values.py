"""
Extract Expected Values / Expected Moves from TOS for ES, NQ, SPX, SPY, QQQ, DIA, IWM.

Uses the tos-ui-mcp submodule's web extractor (tos_ui_mcp.extractor) which provides
login automation, paperMoneyAr mode switching, and the parse_page_expected_moves
function. The submodule must be initialised: `git submodule update --init tos-ui-mcp`.
"""

import asyncio
import json
import math
import sys
import os
from datetime import datetime, date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The tos-ui-mcp submodule provides the maintained web extractor.
TOS_UI_MCP = REPO_ROOT / "tos-ui-mcp"
if str(TOS_UI_MCP) not in sys.path:
    sys.path.insert(0, str(TOS_UI_MCP))

from tos_ui_mcp.extractor import extract_tos_ui_expected_moves
from playwright.async_api import async_playwright

TICKERS = ["ES", "NQ", "SPX", "SPY", "QQQ", "DIA", "IWM"]
OUTPUT_FILE = REPO_ROOT / "data" / "tos_expected_values_115_pst.json"
MARKDOWN_OUTPUT = REPO_ROOT / "data" / "tos_expected_values_summary.md"

async def extract_all_tos_values():
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"==================================================")
    print(f" Executing TOS Expected Values Extraction at {timestamp_str}")
    print(f" Tickers: {', '.join(TICKERS)}")
    print(f"==================================================")

    # Use the tos-ui-mcp extractor directly -- it handles login, profile, and parsing
    data = await extract_tos_ui_expected_moves(tickers=TICKERS, headless=True, save_json=False)

    results = {
        "extracted_at": datetime.now().isoformat(),
        "extracted_at_formatted": timestamp_str,
        "tickers": data.get("tickers", {})
    }

    # Save JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[TOS-Extract] Saved JSON output to: {OUTPUT_FILE}")

    # Generate Markdown Summary
    lines = []
    lines.append(f"# ThinkorSwim (ToS) Expected Values Extraction Report")
    lines.append(f"**Extracted Time:** {timestamp_str}\n")
    lines.append("| Ticker | Spot Price | Front Expiry | DTE | Expected Move (±) |")
    lines.append("|---|---|---|---|---|")

    for sym in TICKERS:
        tdata = results["tickers"].get(sym, {})
        spot = f"${tdata.get('spot_price'):,.2f}" if tdata.get('spot_price') else "N/A"
        exps = tdata.get("expirations", [])
        if exps:
            front = exps[0]
            expiry_str = front.get("expiry", "N/A")
            dte_str = f"{front.get('dte')}d"
            em_str = f"± {front.get('expected_move'):.2f}"
        else:
            expiry_str = "N/A"
            dte_str = "N/A"
            em_str = "N/A"

        lines.append(f"| **{sym}** | {spot} | {expiry_str} | {dte_str} | **{em_str}** |")

    lines.append("\n## All Expirations Detail\n")
    for sym in TICKERS:
        tdata = results["tickers"].get(sym, {})
        exps = tdata.get("expirations", [])
        lines.append(f"### {sym}")
        if not exps:
            lines.append(f"*No expiration headers extracted or error: {tdata.get('error', 'None')}*")
        else:
            lines.append("| Expiry Date | DTE | Expected Move | Raw Header Text |")
            lines.append("|---|---|---|---|")
            for e in exps:
                lines.append(f"| {e.get('expiry')} | {e.get('dte')} | ± {e.get('expected_move'):.2f} | `{e.get('raw_text')}` |")
        lines.append("")

    md_content = "\n".join(lines)
    with open(MARKDOWN_OUTPUT, "w") as f:
        f.write(md_content)
    print(f"[TOS-Extract] Saved Markdown summary to: {MARKDOWN_OUTPUT}")

    return results

if __name__ == "__main__":
    asyncio.run(extract_all_tos_values())
