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
    download_dir = os.path.join(os.getcwd(), "downloads_es_futures")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    print(f"Target Download Directory: {download_dir}")
    
    # Send CDP command to set download behavior
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": download_dir
    })
    
    return driver

def scroll_back(driver, iterations=5):
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
            time.sleep(0.5)
            date_input.send_keys(Keys.CONTROL, "a")
            time.sleep(0.1)
            date_input.send_keys(Keys.DELETE)
            time.sleep(0.1)
            
            # Type date
            for char in list(date_str):
                date_input.send_keys(char)
                time.sleep(0.1)
                
            date_input.send_keys(Keys.ENTER)
            print("Date entered.")
            time.sleep(5) 
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
    downloads_path = os.path.join(os.getcwd(), "downloads_es_futures")
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

def run_enhanced_downloader():
    driver = connect_driver()
    wait = WebDriverWait(driver, 20)
    
    # Enter Bar Replay Mode first
    enter_replay_mode(driver)
    
    # Main Loop
    # Target: 2 months ago
    target_date = datetime.now() - timedelta(days=60)
    print(f"Target Date: {target_date}")
    
    max_iterations = 3 # User requested next 3 sets
    iteration = 0
    last_oldest_time = None
    
    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration}/{max_iterations} ---")
        
        # 1. Scroll Back to load data around the target date
        # This ensures we have a full buffer of data before exporting
        scroll_back(driver, iterations=5)
        
        # 2. Export Data (Current View)
        success = perform_export(driver, wait)
        if not success:
            print("Stopping due to export failure.")
            break
            
        # 2. Find and Analyze Downloaded File
        time.sleep(5) # Wait for file to close
        csv_file = get_latest_csv()
        if not csv_file:
            print("No CSV found.")
            break
            
        print(f"Analyzed file: {csv_file}")
        try:
            df = pd.read_csv(csv_file)
            time_col = df.columns[0] 
            
            if pd.api.types.is_numeric_dtype(df[time_col]):
                df['parsed_time'] = pd.to_datetime(df[time_col], unit='s')
            else:
                df['parsed_time'] = pd.to_datetime(df[time_col])
                
            oldest_dt = df['parsed_time'].min()
            print(f"Oldest data in file: {oldest_dt}")
            
            # Check if we reached the target
            if oldest_dt < target_date:
                print(f"Reached target date {target_date}! Stopping.")
                break
            
            if last_oldest_time and oldest_dt >= last_oldest_time:
                print("Data not getting older. Stopping.")
                break
            
            last_oldest_time = oldest_dt
            
            # 3. Calculate Next Target Date
            next_target = oldest_dt - timedelta(minutes=1)
            target_str = next_target.strftime("%Y-%m-%d %H:%M")
            
            # 4. Go To Date
            go_to_date(driver, target_str)
            
        except Exception as e:
            print(f"Error analyzing CSV: {e}")
            break
        
        time.sleep(5)

if __name__ == "__main__":
    run_enhanced_downloader()
