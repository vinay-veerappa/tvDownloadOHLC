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
    actions = ActionChains(driver)
    
    # Press Alt+G
    actions.key_down(Keys.ALT).send_keys('g').key_up(Keys.ALT).perform()
    time.sleep(2)
    
    # Check if modal appeared. If not, try clicking the calendar icon.
    try:
        # Calendar icon usually has class 'icon-wNyKS1Qc' or similar, or aria-label 'Go to'
        # Let's look for the button we found earlier
        buttons = driver.find_elements(By.CSS_SELECTOR, "button")
        for btn in buttons:
            txt = btn.get_attribute("aria-label") or btn.get_attribute("title") or btn.text
            if txt and "Go to" in txt:
                print(f"FOUND GO TO BUTTON: {txt}")
                # Try standard click
                try:
                    btn.click()
                except:
                    # Try ActionChains
                    ActionChains(driver).move_to_element(btn).click().perform()
                time.sleep(1)
                break
    except:
        pass

    # The dialog should appear. We need to find the input field.
    try:
        # Common selectors for the Go To Date input
        input_selectors = [
            (By.CSS_SELECTOR, "input[data-role='date-input']"),
            (By.CSS_SELECTOR, "div[data-name='date-input'] input"),
            (By.CSS_SELECTOR, "input[type='text']"),
            (By.XPATH, "//input[@placeholder='YYYY-MM-DD']"), 
            (By.XPATH, "//div[contains(@class, 'dialog')]//input") 
        ]
        
        # We need to wait for the modal
        wait = WebDriverWait(driver, 5)
        
        date_input = None
        for by, val in input_selectors:
            try:
                date_input = wait.until(EC.visibility_of_element_located((by, val)))
                if date_input.is_displayed() and date_input.is_enabled():
                    break
            except:
                continue
                
        if date_input:
            # Clear using Backspace loop (more robust than clear())
            # Click to focus
            date_input.click()
            time.sleep(0.5)
            
            # Send Backspace 15 times to clear existing date
            for _ in range(15):
                date_input.send_keys(Keys.BACK_SPACE)
                time.sleep(0.1)
                
            # Type date character by character
            for char in list(date_str):
                date_input.send_keys(char)
                time.sleep(0.1)
                
            date_input.send_keys(Keys.ENTER)
            print("Date entered.")
            time.sleep(5) # Wait for load
            return True
        else:
            print("Could not find date input in modal. Trying blind typing...")
            # Blind typing fallback
            actions.send_keys(date_str).send_keys(Keys.ENTER).perform()
            time.sleep(5)
            return True
            
    except Exception as e:
        print(f"Failed to go to date: {e}")
        actions.send_keys(Keys.ESCAPE).perform()
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

def run_enhanced_downloader():
    driver = connect_driver()
    wait = WebDriverWait(driver, 20)
    
    # Main Loop
    # Target: 2 months ago
    target_date = datetime.now() - timedelta(days=60)
    print(f"Target Date: {target_date}")
    
    max_iterations = 50 # Safety limit
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
