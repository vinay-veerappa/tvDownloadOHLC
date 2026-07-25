"""
ThinkorSwim Web UI Expected Move Extractor
==========================================
Uses Playwright with a persistent browser profile (~/.tos_web_profile) to extract
exact platform-rendered Expected Move values (± XX.XX) from trade.thinkorswim.com.

Features:
- Reuses persistent session context (avoids repeated 2FA logins).
- Robust regex matching for expiration series headers (Date, DTE, ± EM).
- Exports structured data to data/tos_ui_expected_moves.json.
- Graceful error handling per ticker.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PROFILE_DIR = Path.home() / ".tos_web_profile"
OUTPUT_FILE = REPO_ROOT / "data" / "tos_ui_expected_moves.json"

# Regex patterns for parsing TOS Web Option Chain headers
# Example strings found in TOS Web DOM:
# "25 JUL 26 (0) ±14.25 (0.5%)"
# "19 DEC 25 (146) ± 245.80"
# "31 JUL 26 6d ± 42.10"
EM_REGEX = re.compile(
    r'(?P<date>[0-9]{1,2}\s+[A-Za-z]{3}\s+[0-9]{2,4})\s*\(?(?P<dte>[0-9]+)\s*(?:d|DTE|\))?.*?[±\+\/-]\s*(?P<em_val>[0-9]+\.?[0-9]*)'
)

# Alternative regex if date is format "JUL 25 2026"
EM_REGEX_ALT = re.compile(
    r'(?P<date>[A-Za-z]{3}\s+[0-9]{1,2},?\s+[0-9]{2,4})\s*\(?(?P<dte>[0-9]+)\s*(?:d|DTE|\))?.*?[±\+\/-]\s*(?P<em_val>[0-9]+\.?[0-9]*)'
)

async def parse_page_expected_moves(page) -> List[Dict[str, Any]]:
    """Inspects the active TOS Web page DOM for option chain headers and extracts expected move numbers."""
    extracted_series = []

    # Wait for option chain container or headers to appear
    selectors_to_try = [
        "[data-test-id*='expiration']",
        "[data-test-id*='option-chain']",
        ".option-chain-expiration",
        "div[class*='expiration']",
        "div[class*='header']",
        "tr",
        "div"
    ]

    # First attempt: Target specific header container elements
    elements = []
    for sel in selectors_to_try[:4]:
        found = await page.query_selector_all(sel)
        if len(found) > 1:
            elements = found
            break

    # If specific containers aren't found, grab all divs/text blocks on the page
    if not elements:
        elements = await page.query_selector_all("div")

    seen_series = set()

    for el in elements:
        try:
            text = await el.inner_text()
            if not text or "±" not in text:
                continue

            # Clean newlines for regex evaluation
            single_line = " ".join(text.split())

            for pattern in [EM_REGEX, EM_REGEX_ALT]:
                match = pattern.search(single_line)
                if match:
                    groups = match.groupdict()
                    exp_date = groups["date"].strip()
                    dte = int(groups["dte"])
                    em_val = float(groups["em_val"])

                    key = (exp_date, dte, em_val)
                    if key not in seen_series:
                        seen_series.add(key)
                        extracted_series.append({
                            "expiry": exp_date,
                            "dte": dte,
                            "expected_move": em_val,
                            "raw_text": single_line
                        })
                    break
        except Exception:
            continue

    # Sort series by DTE
    extracted_series.sort(key=lambda x: x["dte"])
    return extracted_series

async def extract_tos_ui_expected_moves(
    tickers: List[str],
    headless: bool = True,
    save_json: bool = True,
    wait_time_ms: int = 5000
) -> Dict[str, Any]:
    """
    Main extraction function.
    Navigates trade.thinkorswim.com for each ticker and extracts TOS UI Expected Move values.
    """
    if not PROFILE_DIR.exists():
        return {
            "status": "error",
            "message": f"Persistent profile directory {PROFILE_DIR} does not exist. Please run scripts/market_data/tos_web_login_setup.py first!"
        }

    results: Dict[str, Any] = {
        "extracted_at": datetime.now().isoformat(),
        "source": "thinkorswim_web_ui",
        "tickers": {}
    }

    async with async_playwright() as p:
        print(f"[TOS-UI] Launching Chromium (Headless={headless}) using profile: {PROFILE_DIR}")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            viewport={"width": 1400, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )

        page = context.pages[0] if context.pages else await context.new_page()

        for ticker in tickers:
            symbol_clean = ticker.upper().strip()
            print(f"[TOS-UI] Extracting Expected Move for: {symbol_clean}...")
            url = f"https://trade.thinkorswim.com/trade?symbol={symbol_clean}"

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(wait_time_ms / 1000.0)

                series = await parse_page_expected_moves(page)
                
                results["tickers"][symbol_clean] = {
                    "symbol": symbol_clean,
                    "series_count": len(series),
                    "expirations": series
                }
                print(f"[TOS-UI] Found {len(series)} expiration series for {symbol_clean}.")

            except Exception as e:
                print(f"[TOS-UI] Error processing {symbol_clean}: {e}")
                results["tickers"][symbol_clean] = {
                    "symbol": symbol_clean,
                    "error": str(e),
                    "expirations": []
                }

        await context.close()

    if save_json:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(results, f, indent=2)
        print(f"[TOS-UI] Saved results to: {OUTPUT_FILE}")

    return results

if __name__ == "__main__":
    sample_tickers = ["SPX", "NQ", "ES", "AAPL", "NVDA"]
    # Run in non-headless mode for testing if headless profile is initialized
    is_headless = "--headful" not in sys.argv
    output = asyncio.run(extract_tos_ui_expected_moves(sample_tickers, headless=is_headless))
    print(json.dumps(output, indent=2))
