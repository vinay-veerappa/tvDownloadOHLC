import os
import time
import pandas as pd
import glob
import argparse
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Helper Functions (Reused/Adapted) ---

def connect_driver(download_dir):
    print("Connecting to existing Chrome instance on port 9222...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=chrome_options)
    
    # Switch to TradingView tab
    handles = driver.window_handles
    found_tab = False
    for handle in handles:
        try:
            driver.switch_to.window(handle)
            if "TradingView" in driver.title or "chart" in driver.current_url.lower():
                print(f"Locked onto TradingView tab: {handle}")
                found_tab = True
                break
        except:
            continue
    if not found_tab:
        print("WARNING: Could not identify a TradingView tab. Using current.")

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        
    try:
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": download_dir
        })
    except Exception as e:
        print(f"Warning: Failed to set download behavior: {e}")
        
    return driver

def safe_action_perform(driver, action_builder_func, retries=3):
    last_err = None
    for i in range(retries):
        try:
            # Ensure focus
            try:
                driver.find_element(By.CSS_SELECTOR, "div[id^='header-toolbar-symbol-search']").click()
                # Or just click body? Safer to assume already focused or click canvas if needed.
            except:
                pass
            
            actions = action_builder_func(driver)
            actions.perform()
            return True
        except Exception as e:
            last_err = e
            time.sleep(1)
    if last_err:
        print(f"Action failed: {last_err}")
    return False

def switch_ticker(driver, ticker):
    print(f"\n--- Switching to Ticker: {ticker} ---")
    def build_switch(d):
        return ActionChains(d).send_keys(ticker).send_keys(Keys.ENTER)
    
    # Sometimes need to click to focus first
    try:
        driver.find_element(By.CSS_SELECTOR, "body").click()
    except:
        pass
        
    safe_action_perform(driver, build_switch)
    time.sleep(4) # Wait for chart to load

    # Verification: Check if symbol changed (Optional but good)
    # If "Invalid Symbol" appears, we should detect (hard with pure Selenium without OCR/specific selectors)
    # We will assume success for now.
def jump_to_start(driver):
    print("Jumping to start of data (Alt+Shift+Left)...")
    
    def build_jump_action(d):
        actions = ActionChains(d)
        try:
            d.find_element(By.CSS_SELECTOR, "canvas").click()
        except:
            pass
        actions.key_down(Keys.ALT).key_down(Keys.SHIFT).send_keys(Keys.LEFT).key_up(Keys.SHIFT).key_up(Keys.ALT)
        return actions
        
    safe_action_perform(driver, build_jump_action)
    time.sleep(5)

def perform_export(driver):
    """
    Triggers the Export Data dialog and clicks Export.
    Returns True if successful.
    """
    print("Exporting data...")
    wait = WebDriverWait(driver, 5)

    # Jump to start to load maximum historical data
    time.sleep(2)
    jump_to_start(driver)
    time.sleep(2)
    jump_to_start(driver)
    time.sleep(2)
    
    # 1. Open Menu (Manage Layouts / Save Menu)
    # Using generic 'Export' search first is unrelated to menu open, 
    # but the Export button is hidden in a menu usually.
    # Standard TV: Top right 'Hamburger' or 'down arrow' next to save.
    
    # Trying the 'Export' shortcut if available? No standard shortcut.
    # Let's use the layout menu selectors from previous script
    menu_selectors = [
        (By.CSS_SELECTOR, "button[data-name='save-load-menu']"),
        (By.XPATH, "//button[contains(@class, 'js-save-load-menu-open-button')]"),
        (By.CSS_SELECTOR, "div[data-name='header-toolbar-save-load'] button")
    ]
    
    menu_open = False
    for by, val in menu_selectors:
        try:
            btn = wait.until(EC.element_to_be_clickable((by, val)))
            btn.click()
            menu_open = True
            break
        except:
            continue
            
    if not menu_open:
        print("Could not open Layout menu.")
        return False
        
    time.sleep(1)
    
    # 2. Click "Export Chart Data..."
    try:
        # Search for exact text first, then partial
        export_selectors = [
             (By.XPATH, "//div[contains(@data-name, 'save-load-menu-item-export')]"), # if exists
             (By.XPATH, "//div[contains(text(), 'Download chart data')]"),
             (By.XPATH, "//span[contains(text(), 'Download chart data')]"),
             (By.XPATH, "//div[contains(text(), 'Download chart data')]"),
             # Case-insensitive match (if needed)
             (By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download chart data')]"),
             (By.XPATH, "//div[contains(@class, 'item') and contains(., 'Download chart data')]")
        ]
        
        export_item = None
        for by, val in export_selectors:
            try:
                export_item = driver.find_element(by, val)
                if export_item.is_displayed():
                    print(f"Found Export item via: {val}")
                    break
            except:
                continue
        
        if export_item:
             # Hover first then click? 
             # ActionChains(driver).move_to_element(export_item).perform()
             # time.sleep(0.5)
             export_item.click()
        else:
             print("Could not find specific 'Export Chart Data' item.")
             return False
             
    except Exception as e:
        print(f"Error clicking 'Export' item: {e}")
        return False
        
    time.sleep(1)
    
    # 3. Confirm Dialog
    try:
        #submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[name='Download']")))
        #submit.click()
        actions = ActionChains(driver)
        actions.key_down(Keys.ENTER).send_keys(Keys.LEFT).key_up(Keys.ENTER)
        actions.perform()
        print("Export confirmed.")
        time.sleep(3) # Wait for download
        return True
    except:
        print("Could not find Export submit button.")
        return False

def get_csv_bounds(download_dir, ticker_filter=None):
    """
    Scans CSVs to find the min timestamp.
    Useful to verify if we are getting new data.
    """
    files = glob.glob(os.path.join(download_dir, "*.csv"))
    if not files:
        return None
        
    # Sort by modification time to get the latest
    files.sort(key=os.path.getmtime, reverse=True)
    latest_file = files[0]
    
    # Optional: Check if filename matches ticker
    if ticker_filter and ticker_filter.lower() not in os.path.basename(latest_file).lower():
         # Maybe the file is named "ESZ2024.csv"
         pass

    try:
        df = pd.read_csv(latest_file)
        # Parse time column (usually 1st)
        time_col = df.columns[0]
        # Clean numeric
        if 'time' in time_col.lower() or 'date' in time_col.lower():
            if pd.api.types.is_numeric_dtype(df[time_col]):
                times = pd.to_datetime(df[time_col], unit='s')
            else:
                times = pd.to_datetime(df[time_col])
            
            return times.min()
    except:
        pass
        
    return None

def go_to_date(driver, date_str):
    print(f"Navigating to {date_str}...")
    def build_alt_g(d):
        return ActionChains(d).key_down(Keys.ALT).send_keys('g').key_up(Keys.ALT)
    
    safe_action_perform(driver, build_alt_g)
    time.sleep(1)
    
    # Type date
    try:
        ActionChains(driver).send_keys(date_str).send_keys(Keys.ENTER).perform()
        time.sleep(4) # Wait for chart load
    except Exception as e:
        print(f"Failed to enter date: {e}")

# --- Main Logic ---

def generate_contracts(root, start_year, end_year):
    # Standard Quarterly: H (Mar), M (Jun), U (Sep), Z (Dec)
    quarterly_codes = ['H', 'M', 'U', 'Z']
    # Monthly: F, G, H, J, K, M, N, Q, U, V, X, Z
    monthly_codes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
    
    # Detect if we should use monthly
    # CL (Crude), NG (Nat Gas) are typical monthly
    # ES, NQ, RTY, YM are quarterly
    # GC, SI, HG often have active monthly but quarters are main volume. 
    # For "All available", monthly is safer for CL/NG.
    
    monthly_roots = ['CL', 'NG', 'QM', 'QG', 'HO', 'RB']
    
    use_monthly = root.upper() in monthly_roots
    
    codes = monthly_codes if use_monthly else quarterly_codes
    print(f"Generating {'Monthly' if use_monthly else 'Quarterly'} contracts for {root}...")
    
    contracts = []
    for year in range(start_year, end_year + 1):
        for code in codes:
            contracts.append(f"{root}{code}{year}")
    return contracts

def process_contracts(args):
    driver = connect_driver(args.download_dir)
    
    contracts = generate_contracts(args.ticker_root, args.start_year, args.end_year)
    print(f"Generated {len(contracts)} contracts: {contracts}")
    
    for contract in contracts:
        process_single_contract(driver, contract, args.download_dir)

def process_single_contract(driver, contract, download_dir):
    switch_ticker(driver, contract)
    
    # 1. Export Current View (Latest Data)
    if not perform_export(driver):
        print(f"Skipping {contract} - Export failed (maybe invalid symbol?)")
        return

    # Check bounds
    min_ts = get_csv_bounds(download_dir, contract)
    if not min_ts:
        print("Could not read bounds. Skipping loop.")
        return
        
    print(f"Initial Start Date: {min_ts}")
    
    # Loop to fetch history
    # Safety breakout
    max_loops = 20
    loop_count = 0
    
    last_min_ts = min_ts
    
    while loop_count < max_loops:
        # Calculate Jump Target 
        # Jump back ~3 months or so? Or just go to prev min date?
        # If we just Go To 'min_ts', TV usually centers it, or puts it on right?
        # Better to jump to a specific date prior to min_ts
        target_date = min_ts - timedelta(days=1)
        target_str = target_date.strftime("%Y-%m-%d")
        
        print(f"Loop {loop_count}: Jumping to {target_str}")
        go_to_date(driver, target_str)
        
        # Check if we ACTUALLY moved back
        # We need to perform export to know for sure, OR read screen. 
        # Reading screen is hard. 
        # Exporting is reliable.
        if not perform_export(driver):
            break
            
        new_min = get_csv_bounds(download_dir, contract)
        if not new_min:
            break
            
        print(f"New Start Date: {new_min}")
        
        # --- INFINITE LOOP DETECTION ---
        # If the new chunk's start date is NOT older than previous, we reached value
        # Allow small margin? No, strictly <.
        # Actually, if we download the SAME chunk, 'new_min' will be == 'last_min_ts'.
        if new_min >= last_min_ts:
            print(f"STOPPING: Reached limit of data. {new_min} >= {last_min_ts}")
            break
            
        # Update logic
        last_min_ts = new_min
        min_ts = new_min
        loop_count += 1
    
    print(f"Finished contract {contract}.\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker_root", type=str, default="ES", help="Root ticker (e.g. ES, NQ)")
    parser.add_argument("--start_year", type=int, default=2019, help="Start Year")
    parser.add_argument("--end_year", type=int, default=2021, help="End Year")
    parser.add_argument("--download_dir", type=str, default=r"C:\Users\vinay\tvDownloadOHLC\data\downloads_contracts")
    args = parser.parse_args()
    
    process_contracts(args)
