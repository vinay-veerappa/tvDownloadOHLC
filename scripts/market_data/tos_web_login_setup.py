"""
ThinkorSwim Web One-Time Login & Session Setup
==============================================
Launches a visible Chromium browser with a persistent user data profile (~/.tos_web_profile).
Log into trade.thinkorswim.com manually and complete 2FA once.
After logging in, press ENTER in the terminal to save the session state for future automated runs.
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

PROFILE_DIR = Path.home() / ".tos_web_profile"

async def setup_tos_web_session():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"============================================================")
    print(f" ThinkorSwim Web Session Setup")
    print(f" Profile Directory: {PROFILE_DIR}")
    print(f"============================================================")
    print("1. A Chromium browser window will open.")
    print("2. Log into trade.thinkorswim.com manually.")
    print("3. Complete 2FA / Security Verification.")
    print("4. Once you see the main ThinkorSwim Trade dashboard, return here and press ENTER.")
    print("------------------------------------------------------------")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://trade.thinkorswim.com/", wait_until="domcontentloaded")

        input("\n>>> Press ENTER after you have logged in and completed 2FA successfully <<< ")

        await context.close()
        print("\n[SUCCESS] TOS Web session state saved to persistent profile!")
        print("Subsequent scraper runs will use this profile automatically without 2FA.")

if __name__ == "__main__":
    asyncio.run(setup_tos_web_session())
