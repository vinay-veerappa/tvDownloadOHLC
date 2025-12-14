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

# Import rollover generator if needed (assuming it's in the same dir)
try:
    from futures_rollover_calendar import FuturesRolloverCalendar
except ImportError:
    FuturesRolloverCalendar = None

# --- Configuration ---
# Removed hardcoded ROLLOVER_CSV_NAME
DEFAULT_DOWNLOAD_DIR = os.path.join(os.getcwd(), "data", "downloads_contracts_replay")

# --- Helper Functions (From Enhanced Script) ---

def close_blocking_dialogs(driver):
    """
    Attempts to close common blocking dialogs (e.g. 'Session disconnected', 'Go to date' stuck, etc.)
    """
    try:
        # Generic selectors for dialog close/cancel/ok buttons
        selectors = [
            (By.CSS_SELECTOR, "div[data-name='go-to-date-dialog'] button[data-name='cancel']"), # Cancel Go To
            (By.CSS_SELECTOR, "div[data-name='go-to-date-dialog'] button[data-name='close']"),
            (By.CSS_SELECTOR, "button[data-name='warning-dialog-ok']"), # Generic warning
            (By.XPATH, "//button[contains(text(), 'Got it')]"),
            (By.XPATH, "//button[contains(text(), 'Close')]"),
            (By.CSS_SELECTOR, "div[role='dialog'] button[name='cancel']"),
            (By.CSS_SELECTOR, "div[role='dialog'] button[aria-label='Close']"),
            # Replay specific
            (By.XPATH, "//button[contains(., 'Start new')]"),
            (By.XPATH, "//button[contains(., 'Continue')]")
        ]
        
        for by, val in selectors:
            try:
                # Use short timeout
                db = driver.find_elements(by, val)
                for btn in db:
                    if btn.is_displayed():
                        print(f"[Dialog] Closing dialog via: {val}")
                        btn.click()
                        time.sleep(0.5)
            except:
                pass
                
        # Also try pressing ESC as a failsafe for active modals
        # ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    except:
        pass

def connect_driver(download_dir):
    print("Connecting to existing Chrome instance on port 9222...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Check for multiple tabs
    handles = driver.window_handles
    print(f"Connected. Open tabs: {len(handles)}")
    
    # Find the correct tab
    found_tab = False
    for handle in handles:
        try:
            driver.switch_to.window(handle)
            title = driver.title
            url = driver.current_url
            if "TradingView" in title or "chart" in url.lower():
                print(f"Locked onto TradingView tab: {handle}")
                found_tab = True
                break
        except:
            continue
            
    if not found_tab:
        print("WARNING: Could not identify a TradingView tab. Using current default.")
    
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    print(f"Target Download Directory: {download_dir}")
    
    try:
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": download_dir
        })
    except Exception as e:
        print(f"Warning: Failed to set download behavior via CDP: {e}")
    
    return driver

def safe_action_perform(driver, action_builder_func, retries=3):
    last_err = None
    for i in range(retries):
        try:
            # unique focus attempt
            try:
                driver.find_element(By.CSS_SELECTOR, "body").click()
            except:
                pass

            actions = action_builder_func(driver)
            actions.perform()
            return True
        except Exception as e:
            last_err = e
            # print(f"Action failed (attempt {i+1}/{retries}): {e}")
            time.sleep(1)
    
    print(f"Action failed after {retries} attempts: {last_err}")
    return False

def switch_ticker(driver, ticker):
    print(f"\n[Ticker] Switching to: {ticker}...")
    
    def build_switch_action(d):
        actions = ActionChains(d)
        actions.send_keys(ticker).send_keys(Keys.ENTER)
        return actions

    if safe_action_perform(driver, build_switch_action):
        time.sleep(5) # Wait for load

def jump_to_start(driver):
    print("[Nav] Jumping to start of data (Alt+Shift+Left)...")
    
    def build_jump_action(d):
        actions = ActionChains(d)
        actions.key_down(Keys.ALT).key_down(Keys.SHIFT).send_keys(Keys.LEFT).key_up(Keys.SHIFT).key_up(Keys.ALT)
        return actions
        
    safe_action_perform(driver, build_jump_action)
    time.sleep(5)

def is_in_replay_mode(driver):
    try:
        # Check 1: Jump to Realtime button
        if len(driver.find_elements(By.CSS_SELECTOR, "button[data-name='jump-to-realtime']")) > 0:
            return True
        # Check 2: Select Date button
        if len(driver.find_elements(By.CSS_SELECTOR, "[data-qa-id='select-date-bar-mode-menu']")) > 0:
            return True
        return False
    except:
        return False

def enter_replay_mode(driver):
    if is_in_replay_mode(driver):
        print("[Replay] Already in Bar Replay mode.")
        return

    print("[Replay] Attempting to enter Bar Replay mode...")
    try:
        # 1. Click Bar Replay Button
        replay_selectors = [
            (By.ID, "header-toolbar-replay"),
            (By.CSS_SELECTOR, "button[aria-label='Bar Replay']"),
            (By.CSS_SELECTOR, "button[data-name='replay-mode']")
        ]
        
        clicked = False
        for by, val in replay_selectors:
            try:
                replay_btn = driver.find_element(by, val)
                if replay_btn.is_displayed():
                    replay_btn.click()
                    clicked = True
                    time.sleep(1)
                    break
            except:
                continue
                
        if not clicked:
            print("[Replay] Replay button not found in main toolbar.")
            return

        # 2. Handle 'Start new' / 'Continue' dialog if it appears
        start_time = time.time()
        while time.time() - start_time < 5:
            if is_in_replay_mode(driver):
                return

            # Check for dialogs
            dialog_selectors = [
                (By.XPATH, "//button[contains(., 'Start new')]"), # Robust for spans
                (By.XPATH, "//button[contains(., 'Continue')]"),
                (By.CSS_SELECTOR, "button[data-name='start-new-replay']"),
                (By.CSS_SELECTOR, "button[data-name='continue-replay']"),
                (By.XPATH, "//div[contains(@class, 'dialog')]//button[contains(., 'Start new')]")
            ]
            
            for by, val in dialog_selectors:
                try:
                    btns = driver.find_elements(by, val)
                    for btn in btns:
                        if btn.is_displayed():
                            print(f"[Replay] Clicking dialog button: {val}")
                            btn.click()
                            time.sleep(1)
                            break
                except:
                    pass
            time.sleep(0.5)
            
    except Exception as e:
        print(f"[Replay] Error entering Bar Replay mode: {e}")

def go_to_date(driver, date_str):
    print(f"[Nav] Going to date: {date_str}...")
    
    # Snapshot before
    # driver.save_screenshot("debug_nav_start.png")
    
    # 1. Open Replay Date Menu
    trigger_found = False
    try:
        # Try finding the dropdown trigger
        trigger_selectors = [
            (By.CSS_SELECTOR, "button[data-qa-id='select-date-bar-mode-menu']"),
            (By.CSS_SELECTOR, "[data-name='calendar']"), # Common name?
            (By.CSS_SELECTOR, "div[class*='selectDateBar'] button"),
            (By.XPATH, "//button[contains(@class, 'button') and .//*[contains(@class, 'calendar')]]") # Icon check?
        ]
        
        # Try Alt+G as primary first? It's often more reliable if focus is right.
        print("[Nav] Trying Alt+G to open menu...")
        ActionChains(driver).key_down(Keys.ALT).send_keys('g').key_up(Keys.ALT).perform()
        time.sleep(1)
        
        # Check if input appeared
        if len(driver.find_elements(By.CSS_SELECTOR, "input[data-role='date-input']")) > 0:
            print("[Nav] Alt+G worked, input found.")
            trigger_found = True
        else:
            print("[Nav] Alt+G didn't show input. Trying clicks...")
            for by, val in trigger_selectors:
                try:
                    trigger = driver.find_element(by, val)
                    if trigger.is_displayed():
                        print(f"[Nav] Clicking trigger: {val}")
                        trigger.click()
                        time.sleep(1)
                        trigger_found = True
                        break
                except:
                    continue
    except Exception as e:
        print(f"[Nav] Error opening menu: {e}")

    # 2. Handle Date Input
    try:
        wait = WebDriverWait(driver, 5)
        # Broader input selectors
        input_selectors = [
            (By.CSS_SELECTOR, "input[data-role='date-input']"),
            (By.CSS_SELECTOR, "div[data-name='date-input'] input"),
            (By.CSS_SELECTOR, "span[class*='dateInput'] input"),
            (By.XPATH, "//div[contains(@class, 'dialog')]//input")
        ]
        
        date_input = None
        for by, val in input_selectors:
            try:
                date_input = wait.until(EC.visibility_of_element_located((by, val)))
                if date_input.is_displayed():
                    print(f"[Nav] Found date input via: {val}")
                    break
            except:
                continue
                
        if date_input:
            date_input.click()
            time.sleep(0.2)
            # Robust clear
            date_input.send_keys(Keys.CONTROL, "a")
            time.sleep(0.1)
            date_input.send_keys(Keys.BACK_SPACE)
            time.sleep(0.1)
            
            # Type date - Only YYYY-MM-DD
            date_only = date_str.split(" ")[0]
            print(f"[Nav] Typing: {date_only}")
            date_input.send_keys(date_only)
            time.sleep(0.5)
            date_input.send_keys(Keys.ENTER)
            print("[Nav] Sent Enter.")
            
            # Verify if Dialog closed?
            time.sleep(5) # Give it time to load
            return True
        else:
            print("[Nav] Date input NOT found. saving screenshot.")
            driver.save_screenshot("debug_nav_failed.png")
            return False
    except Exception as e:
        print(f"[Nav] Failed to go to date: {e}")
        driver.save_screenshot("debug_nav_exception.png")
        return False

def perform_export(driver):
    print("[Export] Attempting export...")
    wait = WebDriverWait(driver, 5)
    try:
        # 1. Open Menu
        menu_selectors = [
            (By.CSS_SELECTOR, "button[data-name='save-load-menu']"),
            (By.XPATH, "//button[contains(@class, 'js-save-load-menu-open-button')]"),
            (By.XPATH, "//div[@data-name='header-toolbar-save-load']//button")
        ]
        
        layout_menu = None
        for by, val in menu_selectors:
            try:
                layout_menu = wait.until(EC.element_to_be_clickable((by, val)))
                layout_menu.click()
                time.sleep(1)
                break
            except:
                continue
        
        if not layout_menu:
            print("[Export] Layout menu not found.")
            return False

        # 2. Click Export
        try:
             # Find "Export" in menu items
            menu_items = driver.find_elements(By.CSS_SELECTOR, "div[data-role='menuitem']")
            # DEBUG: Print found items
            # print(f"[Debug] Found {len(menu_items)} menu items: {[i.text for i in menu_items]}")
            
            export_btn = None
            for item in menu_items:
                if "Export" in item.text:
                    print(f"[Export] Found item: '{item.text}'")
                    item.click()
                    export_btn = item
                    break
            
            if not export_btn:
                print("[Export] 'Export' not found in menu items. Trying broader fallback...")
                # Fallback - Broad check for ANY element with Export text visible
                fallback = driver.find_element(By.XPATH, "//*[contains(text(), 'Download')]")
                if fallback.is_displayed():
                    fallback.click()
                    print("[Export] Clicked fallback 'Export' element.")
                else:
                    print("[Export] Fallback element found but not displayed.")
                    return False
        except Exception as e:
            print(f"[Export] Error finding/clicking Export: {e}")
            return False
            
        # 3. Confirm Export
        time.sleep(1)
        actions = ActionChains(driver)
        actions.key_down(Keys.ENTER).send_keys(Keys.ENTER).key_up(Keys.ENTER)
        actions.perform()
        # dialog_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[name='Download']")))
        # dialog_btn.click()

        
        print("[Export] Confirmed.")
        time.sleep(3) # Wait for download
        return True
        
    except Exception as e:
        print(f"[Export] Failed: {e}")
        return False

def get_latest_csv(download_dir):
    files = glob.glob(os.path.join(download_dir, "*.csv")) 
    if not files:
        return None
    return max(files, key=os.path.getctime)

def get_csv_bounds(csv_file):
    try:
        df = pd.read_csv(csv_file)
        if df.empty: return None
        
        time_col = df.columns[0]
        # Check if numeric (timestamp) or string
        if pd.api.types.is_numeric_dtype(df[time_col]):
             # likely seconds?
             if df[time_col].mean() > 1000000000: # modern timestamp
                 parsed = pd.to_datetime(df[time_col], unit='s')
             else:
                 # maybe not timestamp?
                 parsed = pd.to_datetime(df[time_col], unit='s')
        else:
            parsed = pd.to_datetime(df[time_col])
            
        return parsed.min(), parsed.max()
    except Exception as e:
        print(f"Error reading CSV {csv_file}: {e}")
        return None

# --- Rollover Logic ---

def load_rollover_calendar(csv_path):
    if not os.path.exists(csv_path):
        print(f"[Rollover] {csv_path} not found. Attempting to generate...")
        if FuturesRolloverCalendar:
            cal = FuturesRolloverCalendar()
            # Generate a wide range just in case
            df = cal.generate_es_calendar(2010, 2030)
            cal.export_to_csv(df, csv_path)
            return df
        else:
            print("[Rollover] Generator not available. Cannot proceed efficiently.")
            return None
            
    return pd.read_csv(csv_path)

def get_previous_contract_rollover(contract_name, calendar_df):
    """
    Given 'ESZ2024', find the rollover date of the PREVIOUS contract (e.g., 'ESU2024').
    This is our safety stop date.
    """
    # Parse contract
    try:
        # ESZ2024 -> ES, Z, 2024
        # We assume standard formatting: 2 chars root + 1 char month + 4 chars year
        root = contract_name[:2]
        month_code = contract_name[2]
        year = int(contract_name[3:])
        
        # Find this contract in DF
        current_idx = calendar_df[calendar_df['contract'] == contract_name].index
        
        if len(current_idx) == 0:
            # Try 2-digit year format usually in CSV? No, our generator uses 2 digit logic but contract name might be 4
            # Generator: ES{month}{year_2_digits} e.g. ESH24
            # Script arg usually ESH2024.
            # Let's try to match intelligently
            
            # Convert input to short format for lookup
            short_year = str(year)[-2:]
            short_contract = f"{root}{month_code}{short_year}"
            current_idx = calendar_df[calendar_df['contract'] == short_contract].index
            
        if len(current_idx) > 0:
            idx = current_idx[0]
            if idx > 0:
                prev_row = calendar_df.iloc[idx - 1]
                return pd.to_datetime(prev_row['rollover_date'])
            else:
                return None # No previous contract in calendar
    except Exception as e:
        print(f"[Rollover] Error determining previous contract: {e}")
        
    return None

# --- Main Loop ---

def get_calendar_path(contract_name):
    root = contract_name[:2].upper()
    if root == "ES":
        return "es_rollover_calendar.csv"
    elif root == "CL":
        return "cl_rollover_calendar.csv"
    else:
        # Default fallback or try generic
        return f"{root.lower()}_rollover_calendar.csv"

def process_contracts(args):
    # 2. Setup Driver
    driver = connect_driver(args.download_dir)
    
    # 3. Iterate Contracts
    contracts = args.contracts.split(",")
    print(f"Processing {len(contracts)} contracts: {contracts}")
    
    # Load calendars cache
    calendars = {}

    for contract in contracts:
        contract = contract.strip()
        print(f"\n{'='*40}\nStarting Contract: {contract}\n{'='*40}")
        
        # Load specific calendar for this contract root
        csv_name = get_calendar_path(contract)
        if csv_name not in calendars:
             full_path = os.path.join(os.path.dirname(__file__), csv_name) # Assume in same dir
             if not os.path.exists(full_path):
                 # Try current dir
                 full_path = csv_name
                 
             calendars[csv_name] = load_rollover_calendar(full_path)
        
        calendar_df = calendars.get(csv_name)

        # Determine Boundary
        stop_date = None
        if calendar_df is not None:
            rollover_date = get_previous_contract_rollover(contract, calendar_df)
            
            if rollover_date:
                # Add safety buffer (e.g. 10 days BEFORE the rollover of the PREV contract)
                # Actually, we want data *starting* from the rollover of the prev contract.
                stop_date = rollover_date - timedelta(days=10)
                print(f"[Boundary] Previous Contract Rollover: {rollover_date.date()}")
                print(f"[Boundary] Target Stop Date (with buffer): {stop_date.date()}")
            else:
                print("[Boundary] Could not determine previous contract in calendar. Will use default lookback or manual stop.")
        else:
             print(f"[Boundary] No calendar found for {csv_name}. Cannot determine automatic stop.")
            
        # Switch & Replay
        switch_ticker(driver, contract)
        enter_replay_mode(driver)
        
        # Download Loop
        iteration = 0
        last_min_date = None
        
        # Start from "Now" (jump to realtime just in case, though usually viewing contract keeps us effectively at end)
        # Actually for expired contracts, "Realtime" is just the end of that contract.
        
        while iteration < 50: # max loops safety
            iteration += 1
            print(f"\n--- Iteration {iteration} ({contract}) ---")
            
            # Ensure no dialogs blocking
            close_blocking_dialogs(driver)

            # Jump to start
            jump_to_start(driver)
            time.sleep(5)
            jump_to_start(driver)
            time.sleep(3)
            
            # Export
            if not perform_export(driver):
                print("Export failed. Stopping contract.")
                break
                
            # Process File
            csv_file = get_latest_csv(args.download_dir)
            if not csv_file:
                print("No CSV found. Stopping.")
                break
                
            # Check bounds
            min_date, max_date = get_csv_bounds(csv_file)
            if not min_date:
                print("Could not read bounds. Stopping.")
                break
                
            print(f"[Data] Chunk Range: {min_date} -> {max_date}")
            
            # Rename for organization
            new_name = f"{contract}_{min_date.strftime('%Y%m%d')}_{max_date.strftime('%Y%m%d')}_{iteration}.csv"
            new_path = os.path.join(args.download_dir, new_name)
            try:
                # Check if exists (duplicate download?)
                if os.path.exists(new_path):
                     print("File already exists. Duplicate chunk?")
                else:
                    os.rename(csv_file, new_path)
                    print(f"[File] Saved: {new_name}")
            except:
                pass

            # CHECK BOUNDARY
            if stop_date and min_date < stop_date:
                print(f"[Boundary] Reached limit! {min_date} < {stop_date}")
                break
            
            if last_min_date and min_date >= last_min_date:
                print("[Boundary] No new data retrieved (Start date stuck).")
                # Attempt to unblock stuck state?
                close_blocking_dialogs(driver)
                # break # Don't break immediately, maybe try one more jump? 
                # Actually if it's strictly equal, we are stuck.
                print("Stopping to avoid infinite loop.")
                break
                
            last_min_date = min_date
            
            # Move back
            # Jump to 1 day before current min
            target_jump = min_date - timedelta(days=1)
            if not go_to_date(driver, target_jump.strftime("%Y-%m-%d")):
                 print("[Nav] Go To Date failed. Closing dialogs and retrying...")
                 close_blocking_dialogs(driver)
                 time.sleep(1)
                 go_to_date(driver, target_jump.strftime("%Y-%m-%d"))
            
        print(f"Finished {contract}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts", type=str, required=True, help="Comma-sep list of contracts (e.g. ESZ2023,ESH2024)")
    parser.add_argument("--download_dir", type=str, default=DEFAULT_DOWNLOAD_DIR, help="Download directory")
    args = parser.parse_args()
    
    process_contracts(args)
