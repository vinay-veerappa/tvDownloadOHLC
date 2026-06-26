from playwright.sync_api import sync_playwright
import time
import os

def main():
    print("Starting Playwright automation check...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Capture console logs
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        # Capture page errors
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        try:
            print("Navigating to http://localhost:3000...")
            page.goto("http://localhost:3000")
            
            print("Waiting for page to load (networkidle)...")
            page.wait_for_load_state("networkidle")
            
            # Wait another 5 seconds for chart and websockets to initialize
            print("Waiting 5 seconds for chart initialization...")
            time.sleep(5)
            
            # Take screenshot of the chart
            screenshot_path = "C:/Users/vinay/.gemini/antigravity-ide/brain/1b9711e9-b979-43b3-aefc-9ff22c3a6a3f/chart_dashboard_test.png"
            page.screenshot(path=screenshot_path)
            print(f"✅ Screenshot saved to {screenshot_path}")
            
            # Log any console output or errors
            print("\n=== Console Logs ===")
            for log in console_logs[-30:]:  # Print last 30 logs
                print(log)
                
            print("\n=== Page Errors ===")
            for err in page_errors:
                print(f"ERROR: {err}")
                
        except Exception as e:
            print(f"Exception during check: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
