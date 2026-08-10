"""
Extract Expected Values / Expected Moves from TOS for ES, NQ, SPX, SPY, QQQ, DIA, IWM.
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

from scripts.market_data.tos_web_ui_extractor import parse_page_expected_moves, PROFILE_DIR
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

    results = {
        "extracted_at": datetime.now().isoformat(),
        "extracted_at_formatted": timestamp_str,
        "tickers": {}
    }

    if not PROFILE_DIR.exists():
        print(f"Error: Profile directory {PROFILE_DIR} does not exist.")
        return results

    async with async_playwright() as p:
        print(f"[TOS-Extract] Launching browser context using profile: {PROFILE_DIR}")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )

        page = context.pages[0] if context.pages else await context.new_page()

        for symbol in TICKERS:
            url_sym = symbol if symbol.startswith("/") else f"/{symbol}" if symbol in ["ES", "NQ"] else symbol
            clean_sym = symbol.upper()
            url = f"https://trade.thinkorswim.com/trade?symbol={url_sym}"
            print(f"[TOS-Extract] Fetching {clean_sym} ({url})...")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(4.0)

                series = await parse_page_expected_moves(page)
                
                # Also try searching for price
                spot_price = None
                try:
                    price_el = await page.query_selector("[data-test-id*='last-price'], .last-price, span[class*='price']")
                    if price_el:
                        txt = await price_el.inner_text()
                        txt_clean = txt.replace(",", "").replace("$", "").strip()
                        spot_price = float(txt_clean)
                except Exception:
                    pass

                results["tickers"][clean_sym] = {
                    "symbol": clean_sym,
                    "spot_price": spot_price,
                    "series_count": len(series),
                    "expirations": series
                }
                print(f"  -> {clean_sym}: Found {len(series)} expirations.")

            except Exception as e:
                print(f"  -> {clean_sym}: Error: {e}")
                results["tickers"][clean_sym] = {
                    "symbol": clean_sym,
                    "error": str(e),
                    "expirations": []
                }

        await context.close()

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
        spot = f"${tdata.get('spot_price'):,.2f}" if tdata.get("spot_price") else "N/A"
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
