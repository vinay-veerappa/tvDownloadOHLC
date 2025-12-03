import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import argparse
import glob
from datetime import datetime, timedelta

def connect_driver():
    print("Connecting to existing Chrome instance on port 9222...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Check for multiple tabs
    handles = driver.window_handles
    print(f"Connected. Open tabs: {len(handles)}")
    if len(handles) > 1:
        print("WARNING: Multiple tabs detected. This might cause 'Multiple Session' errors.")
        print("Please close other TradingView tabs.")
    
    # Set download directory
    download_dir = os.path.join(os.getcwd(), "data", "downloads_es_futures")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    print(f"Target Download Directory: {download_dir}")
    
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": download_dir
    })
    
    return driver

def get_data_bounds(download_dir, parquet_file=None):
    """
    Scans all CSV files in the download directory AND an optional Parquet file
    to find the global minimum (oldest) and maximum (newest) timestamps.
    """
    min_dates = []
    max_dates = []
    
    # 1. Check Parquet File
    if parquet_file and os.path.exists(parquet_file):
        print(f"Reading bounds from Parquet: {parquet_file}")
        try:
            # Try to read just the time column if we can guess it, otherwise read all
            # We'll assume 'time' or first column.
            df_p = pd.read_parquet(parquet_file)
            
            time_col = None
            # Heuristic: Check common names or first column
            possible_names = ['time', 'Time', 'date', 'Date', 'datetime', 'timestamp']
            for name in possible_names:
                if name in df_p.columns:
                    time_col = name
                    break
            
            if not time_col and len(df_p.columns) > 0:
                # Fallback to first column if it looks like time
                time_col = df_p.columns[0]
            
            if time_col:
                print(f"Using column '{time_col}' from Parquet.")
                if pd.api.types.is_numeric_dtype(df_p[time_col]):
                    times = pd.to_datetime(df_p[time_col], unit='s')
                else:
                    times = pd.to_datetime(df_p[time_col])
                
                if not times.empty:
                    min_dates.append(times.min())
                    max_dates.append(times.max())
            elif isinstance(df_p.index, pd.DatetimeIndex):
                 print("Using DatetimeIndex from Parquet.")
                 if not df_p.index.empty:
                    min_dates.append(df_p.index.min())
                    max_dates.append(df_p.index.max())
            else:
                print("Could not identify time column in Parquet.")
                
        except Exception as e:
            print(f"Error reading Parquet: {e}")

    # 2. Check CSV files
    files = glob.glob(os.path.join(download_dir, "*.csv"))
    if files:
        print(f"Scanning {len(files)} CSV files for data bounds...")
        for f in files:
            try:
                df = pd.read_csv(f)
                if df.empty:
                    continue
                    
                time_col = df.columns[0]
                if pd.api.types.is_numeric_dtype(df[time_col]):
                    times = pd.to_datetime(df[time_col], unit='s')
                else:
                    times = pd.to_datetime(df[time_col])
                
                min_dates.append(times.min())
                max_dates.append(times.max())
            except Exception as e:
                continue
            
    if not min_dates:
        return None, None
        
    global_min = min(min_dates)
    global_max = max(max_dates)
    print(f"Global Data Bounds: Oldest={global_min}, Newest={global_max}")
    return global_min, global_max

def switch_ticker(driver, ticker):
    print(f"Switching to ticker: {ticker}...")
    actions = ActionChains(driver)
    # Ensure chart is focused
    try:
        driver.find_element(By.CSS_SELECTOR, "canvas").click()
    except:
        pass
    
    actions.send_keys(ticker).perform()
    time.sleep(1)
    actions.send_keys(Keys.ENTER).perform()
    time.sleep(5) # Wait for load

def jump_to_start(driver):
    print("Jumping to start of data (Alt+Shift+Left)...")
    actions = ActionChains(driver)
    # Ensure chart is focused
    try:
        driver.find_element(By.CSS_SELECTOR, "canvas").click()
    except:
        pass
    actions.key_down(Keys.ALT).key_down(Keys.SHIFT).send_keys(Keys.LEFT).key_up(Keys.SHIFT).key_up(Keys.ALT).perform()
    time.sleep(5)

def scroll_back(driver, iterations=2):
    print(f"Scrolling back {iterations} times...")
    actions = ActionChains(driver)
    
    # Focus on the chart
    try:
        # Try multiple selectors for the chart area
        canvas = driver.find_element(By.CSS_SELECTOR, "canvas")
        canvas.click()
        print("Clicked canvas to focus.")
    except:
        print("Could not click canvas, assuming focused.")
        
    # Use Alt + Shift + Left Arrow to jump to the oldest bar
    # Send it ONCE, then wait for load
    actions.key_down(Keys.ALT).key_down(Keys.SHIFT).send_keys(Keys.LEFT).key_up(Keys.SHIFT).key_up(Keys.ALT).perform()
    print("Sent Alt+Shift+Left. Waiting for data load...")
    time.sleep(5) # Wait 5 seconds for data to load
        
def perform_export(driver, wait):
    print("Attempting export...")
    try:
        # 1. Open Menu
        menu_selectors = [
            (By.CSS_SELECTOR, "button[data-name='save-load-menu']"),
            (By.XPATH, "//button[contains(@class, 'js-save-load-menu-open-button')]"),
            (By.XPATH, "//div[@data-name='header-toolbar-save-load']//button"),
            (By.XPATH, "//button[contains(@aria-label, 'Manage layouts')]"),
             (By.XPATH, "//div[contains(@class, 'layoutName')]")
        ]
        
        layout_menu = None
        # Retry loop for menu
        for _ in range(3):
            for by, val in menu_selectors:
                try:
                    layout_menu = wait.until(EC.element_to_be_clickable((by, val)))
                    layout_menu.click()
                    time.sleep(1)
                    # Check if menu opened (look for Export button immediately)
                    # Use a very broad check for any element containing "Export"
                    # This avoids issues with ellipsis (...) vs (…) vs no ellipsis
                    if len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Export')]")) > 0:
                        break
                except:
                    continue
            if layout_menu:
                break
            time.sleep(1)
        
        if not layout_menu:
            print("Layout menu not found.")
            driver.save_screenshot("debug_menu_not_found.png")
            return None

        time.sleep(1)
        
        # 2. Click Export
        # Robust method: Iterate over all menu items and find the one with "Export"
        export_btn = None
        try:
            menu_items = driver.find_elements(By.CSS_SELECTOR, "div[data-role='menuitem']")
            print(f"Found {len(menu_items)} menu items.")
            for item in menu_items:
                # Check text (handle potential newlines or extra spaces)
                if "Export" in item.text:
                    print(f"Found Export item: '{item.text}'")
                    # Try standard click
                    try:
                        item.click()
                    except:
                        print("Standard click failed, trying ActionChains...")
                        ActionChains(driver).move_to_element(item).click().perform()
                    
                    export_btn = item
                    break
        except Exception as e:
            print(f"Error iterating menu items: {e}")

        if not export_btn:
            print("Export button not found (via menu item iteration).")
            # Fallback to old selector just in case
            try:
                fallback = driver.find_element(By.XPATH, "//*[contains(text(), 'Export')]")
                fallback.click()
                export_btn = fallback
            except:
                return None
            
        # 3. Confirm Export (Click the button in the dialog)
        time.sleep(1)
        print("Waiting for Export dialog button...")
        dialog_btn_selectors = [
            (By.CSS_SELECTOR, "button[name='submit']"),
            (By.XPATH, "//button[contains(text(), 'Export')]"),
            (By.XPATH, "//span[contains(text(), 'Export')]"),
            (By.CSS_SELECTOR, "div[data-name='export-chart-data-dialog'] button[type='submit']")
        ]
        
        export_submit = None
        for by, val in dialog_btn_selectors:
            try:
                export_submit = wait.until(EC.element_to_be_clickable((by, val)))
                export_submit.click()
                print(f"Clicked Export dialog button using {val}")
                break
            except:
                continue
                
        if not export_submit:
            print("Export dialog button not found.")
            return None
            
        print("Export confirmed.")
        
        # Wait for download
        time.sleep(5)
        
        # Find the downloaded file
        # We assume it's the latest CSV in the current directory (if we set prefs) 
        # OR we check the default Downloads folder.
        # Since we attached to existing Chrome, it goes to default Downloads.
        # We need to find the latest CSV there.
        
        # TODO: Logic to find and move the file
        return True
        
    except Exception as e:
        print(f"Export failed: {e}")
        return None

def go_to_date(driver, date_str):
    print(f"Going to date: {date_str}...")
    
    # 1. Find "Select date..." in Replay Toolbar
    print("Looking for Replay 'Select date' option...")
    try:
        # Try finding the dropdown trigger using data-qa-id
        trigger = None
        trigger_selectors = [
            (By.CSS_SELECTOR, "[data-qa-id='select-date-bar-mode-menu']"),
            (By.CSS_SELECTOR, "button[data-qa-id='select-date-bar-mode-menu']"),
            (By.CSS_SELECTOR, "div[class*='selectDateBar__button']")
        ]
        
        for by, val in trigger_selectors:
            try:
                trigger = driver.find_element(by, val)
                if trigger.is_displayed():
                    print(f"Found trigger: {val}")
                    trigger.click()
                    time.sleep(1)
                    break
            except:
                continue
                
        if not trigger:
            print("Could not find dropdown trigger. Trying Alt+G fallback...")
            ActionChains(driver).key_down(Keys.ALT).send_keys('g').key_up(Keys.ALT).perform()
            time.sleep(2)
        else:
            # Look for "Select date..." in the open menu
            print("Looking for 'Select date' using class selector...")
            try:
                # Find ALL elements with 'selectDateBar' in class
                elements = driver.find_elements(By.CSS_SELECTOR, "[class*='selectDateBar']")
                found = False
                for el in elements:
                    if "Select date" in el.text:
                        print("MATCH FOUND! Clicking...")
                        el.click()
                        found = True
                        time.sleep(2)
                        break
                if not found:
                    print("No element with 'Select date' text found.")
            except Exception as e:
                print(f"Error searching classes: {e}")

    except Exception as e:
        print(f"Error finding replay menu: {e}")

    # 2. Handle Date Input
    try:
        wait = WebDriverWait(driver, 5)
        input_selectors = [
            (By.CSS_SELECTOR, "input[data-role='date-input']"),
            (By.CSS_SELECTOR, "div[data-name='date-input'] input"),
            (By.CSS_SELECTOR, "input[type='text']"),
            (By.XPATH, "//input[@placeholder='YYYY-MM-DD']"), 
            (By.XPATH, "//div[contains(@class, 'dialog')]//input") 
        ]
        
        date_input = None
        for by, val in input_selectors:
            try:
                date_input = wait.until(EC.visibility_of_element_located((by, val)))
                if date_input.is_displayed() and date_input.is_enabled():
                    break
            except:
                continue
                
        if date_input:
            # Clear input
            date_input.click()
            time.sleep(0.2)
            date_input.send_keys(Keys.CONTROL, "a")
            time.sleep(0.05)
            date_input.send_keys(Keys.DELETE)
            time.sleep(0.05)
            
            # Type date
            for char in list(date_str):
                date_input.send_keys(char)
                time.sleep(0.05) # Reduced from 0.1
                
            date_input.send_keys(Keys.ENTER)
            print("Date entered.")
            time.sleep(2) # Reduced from 5
            return True
        else:
            print("Could not find date input.")
            return False
            
    except Exception as e:
        print(f"Failed to go to date: {e}")
        return False

import glob
import os
from datetime import datetime, timedelta

def get_latest_csv():
    # Look in our custom download folder
    downloads_path = os.path.join(os.getcwd(), "data", "downloads_es_futures")
    list_of_files = glob.glob(os.path.join(downloads_path, "*.csv")) 
    if not list_of_files:
        return None
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file

def enter_replay_mode(driver):
    print("Attempting to enter Bar Replay mode...")
    try:
        # 1. Click Bar Replay Button
        replay_selectors = [
            (By.ID, "header-toolbar-replay"),
            (By.CSS_SELECTOR, "button[aria-label='Bar Replay']"),
            (By.CSS_SELECTOR, "button[data-name='replay-mode']")
        ]
        
        replay_btn = None
        for by, val in replay_selectors:
            try:
                replay_btn = driver.find_element(by, val)
                if replay_btn.is_displayed():
                    replay_btn.click()
                    print(f"Clicked Bar Replay button using {val}")
                    time.sleep(1)
                    break
            except:
                continue
                
        if not replay_btn:
            print("Could not find Bar Replay button. Assuming already in mode or hidden.")
            
        # 2. Handle 'Start new' dialog if it appears
        time.sleep(1)
        try:
            start_new_selectors = [
                (By.XPATH, "//button[contains(text(), 'Start new')]"),
                (By.CSS_SELECTOR, "button[data-name='start-new-replay']"),
                (By.XPATH, "//div[contains(@class, 'dialog')]//button[contains(., 'Start new')]")
            ]
            
            for by, val in start_new_selectors:
                try:
                    btn = driver.find_element(by, val)
                    if btn.is_displayed():
                        btn.click()
                        print(f"Clicked 'Start new' button using {val}")
                        time.sleep(1)
                        break
                except:
                    continue
        except:
            pass # Dialog might not appear
            
    except Exception as e:
        print(f"Error entering Bar Replay mode: {e}")

def run_enhanced_downloader(args):
    driver = connect_driver()
    wait = WebDriverWait(driver, 20)
    
    # Switch ticker if requested
    if args.ticker:
        switch_ticker(driver, args.ticker)
    
    # Enter Bar Replay Mode first
    # Check if we are already in replay mode
    try:
        # If the "Jump to real-time" button exists, click it to ensure we start at the end
        jump_btns = driver.find_elements(By.CSS_SELECTOR, "button[data-name='jump-to-realtime']")
        if len(jump_btns) > 0:
            print("Already in Bar Replay mode. Jumping to Real-time...")
            jump_btns[0].click()
            time.sleep(2)
        else:
            enter_replay_mode(driver)
    except:
        enter_replay_mode(driver)
    
    # Determine bounds
    download_dir = os.path.join(os.getcwd(), "data", "downloads_es_futures")
    global_min, global_max = get_data_bounds(download_dir, args.parquet_file)
    
    # Define tasks
    tasks = []
    
    # Task 1: Fill Gap (Forward/Recent)
    if args.check_gap:
        if global_max:
            # Check if gap exists (e.g., > 1 hour)
            now = datetime.now()
            if (now - global_max) > timedelta(hours=1):
                print(f"Gap detected: {global_max} -> {now}")
                tasks.append({
                    "type": "gap",
                    "start_date": now,
                    "stop_date": global_max
                })
            else:
                print("No significant gap detected.")
        else:
            print("No existing data to check gap against. Starting fresh download.")
            tasks.append({
                "type": "gap", # Treat as gap fill from Now
                "start_date": datetime.now(),
                "stop_date": datetime.now() - timedelta(days=30*args.months) # Default fallback
            })

    # Task 2: Resume History (Backward)
    if args.resume or (not args.check_gap and not args.resume): # Default if nothing specified? Or just resume.
        # If user didn't specify anything, maybe just resume history?
        # Let's assume if --resume is passed OR no specific mode is passed, we do history.
        # But if --check-gap is passed alone, we only do gap.
        if args.resume or not args.check_gap:
            start_point = global_min if global_min else datetime.now()
            target_date = start_point - timedelta(days=30*args.months)
            print(f"Resuming history download from {start_point} to {target_date}")
            tasks.append({
                "type": "history",
                "start_date": start_point,
                "stop_date": target_date
            })

    if not tasks:
        print("No tasks to perform.")
        return

    for task in tasks:
        print(f"\n--- Starting Task: {task['type'].upper()} ---")
        print(f"Start: {task['start_date']}")
        print(f"Stop: {task['stop_date']}")
        
        current_pointer = task['start_date']
        stop_limit = task['stop_date']
        
        # Initial positioning
        if task['type'] == 'gap':
            # For gap, we start at Now (Realtime)
            # Ensure we are at realtime
            try:
                jump_btns = driver.find_elements(By.CSS_SELECTOR, "button[data-name='jump-to-realtime']")
                if jump_btns:
                    jump_btns[0].click()
            except:
                pass
        else:
            # For history, go to the start point
            go_to_date(driver, current_pointer.strftime("%Y-%m-%d %H:%M"))
            
        # Optional: Use Alt+Shift+Left if requested or to ensure we are at the edge
        if args.use_shortcuts:
            jump_to_start(driver)

        max_iterations = args.iterations if args.iterations else 100 # Safety limit
        iteration = 0
        last_oldest_time = None
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration}/{max_iterations} ({task['type']}) ---")
            
            # 1. Export
            success = perform_export(driver, wait)
            if not success:
                print("Export failed. Retrying once...")
                time.sleep(2)
                success = perform_export(driver, wait)
                if not success:
                    print("Export failed again. Stopping task.")
                    break
            
            # 2. Process File
            try:
                time.sleep(3) # Wait for download
                csv_file = get_latest_csv()
                if not csv_file:
                    print("No CSV found.")
                    break
                    
                # Rename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_filename = f"ES1_1m_{timestamp}_{task['type']}_{iteration}.csv"
                new_path = os.path.join(os.path.dirname(csv_file), new_filename)
                try:
                    os.rename(csv_file, new_path)
                    print(f"Saved: {new_filename}")
                    csv_file = new_path
                except:
                    pass
                
                # Analyze
                df = pd.read_csv(csv_file)
                time_col = df.columns[0]
                if pd.api.types.is_numeric_dtype(df[time_col]):
                    df['parsed_time'] = pd.to_datetime(df[time_col], unit='s')
                else:
                    df['parsed_time'] = pd.to_datetime(df[time_col])
                
                file_min = df['parsed_time'].min()
                file_max = df['parsed_time'].max()
                print(f"File Range: {file_min} <-> {file_max}")
                
                # Check completion conditions
                if task['type'] == 'gap':
                    # We are downloading backwards from Now.
                    # We stop if file_min <= stop_limit (overlap with old data)
                    if file_min <= stop_limit:
                        print(f"Gap filled! (File min {file_min} <= Stop limit {stop_limit})")
                        break
                else:
                    # History
                    # We stop if file_min <= stop_limit
                    if file_min <= stop_limit:
                        print(f"Target history reached! (File min {file_min} <= Stop limit {stop_limit})")
                        break
                
                # Check for progress
                if last_oldest_time and file_min >= last_oldest_time:
                    print("Data not getting older. Stopping to avoid loop.")
                    break
                last_oldest_time = file_min
                
                # Move to next chunk
                next_target = file_min - timedelta(minutes=1)
                go_to_date(driver, next_target.strftime("%Y-%m-%d %H:%M"))
                
            except Exception as e:
                print(f"Error processing file: {e}")
                break
                
            time.sleep(2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhanced OHLC Downloader")
    parser.add_argument("--resume", action="store_true", help="Resume downloading history from the oldest existing data")
    parser.add_argument("--check-gap", action="store_true", help="Check for gap between Now and latest data, and fill it")
    parser.add_argument("--months", type=int, default=3, help="Number of months of history to download (default: 3)")
    parser.add_argument("--iterations", type=int, help="Override number of iterations")
    parser.add_argument("--ticker", type=str, help="Ticker symbol to switch to (e.g., ES1!)")
    parser.add_argument("--use-shortcuts", action="store_true", help="Use Alt+Shift+Left to jump to start")
    parser.add_argument("--parquet-file", type=str, help="Path to existing Parquet file to use for data bounds")
    
    args = parser.parse_args()
    
    run_enhanced_downloader(args)
