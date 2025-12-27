import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def run_selenium_downloader():
    print("Connecting to existing Chrome instance on port 9222...")
    
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    # We don't use Service/ChromeDriverManager here because we are connecting to an existing instance
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"Failed to connect to Chrome: {e}")
        print("Make sure you have launched Chrome with: chrome.exe --remote-debugging-port=9222")
        return

    wait = WebDriverWait(driver, 20)
    
    try:
        # Assume user is already logged in.
        
        # --- NAVIGATE TO CHART ---
        symbol = "CME_MINI:ES1!"
        chart_url = f"https://www.tradingview.com/chart/?symbol={symbol}"
        
        current_url = driver.current_url
        if chart_url not in current_url:
            print(f"Navigating to chart: {chart_url}")
            driver.get(chart_url)
        else:
            print("Already on chart page.")
        
        # Wait for chart to load
        print("Waiting for chart to load...")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "canvas")))
        print("Chart loaded.")
        time.sleep(5) 
        
        # --- EXPORT DATA ---
        print("Attempting to find Export option...")
        
        try:
            # Try to open the menu.
            menu_selectors = [
                (By.CSS_SELECTOR, "button[data-name='save-load-menu']"),
                (By.XPATH, "//button[contains(@class, 'js-save-load-menu-open-button')]"),
                (By.XPATH, "//div[@data-name='header-toolbar-save-load']//button"),
                (By.XPATH, "//button[contains(@aria-label, 'Manage layouts')]"),
                (By.XPATH, "//button[contains(@aria-label, 'Save layout')]"),
                (By.XPATH, "//div[contains(@class, 'layoutName')]") 
            ]
            
            layout_menu = None
            for by, val in menu_selectors:
                try:
                    layout_menu = wait.until(EC.element_to_be_clickable((by, val)))
                    layout_menu.click()
                    print(f"Clicked Layout menu with {by}={val}")
                    break
                except:
                    continue
            
            if not layout_menu:
                print("Could not find Layout menu button. Trying to find Export button directly...")
            
            time.sleep(2)
            
            # DEBUG: Print all text in the menu to see what's available
            try:
                # Assuming the menu opens a dropdown, let's look for any visible dropdown items
                dropdown_items = driver.find_elements(By.CSS_SELECTOR, "div[data-role='menuitem']")
                print(f"Found {len(dropdown_items)} menu items:")
                for item in dropdown_items:
                    print(f" - '{item.text}'")
            except:
                pass
            
            # Now look for "Export Chart Data..."
            export_selectors = [
                (By.XPATH, "//div[contains(text(), 'Export chart data')]"),
                (By.XPATH, "//div[contains(text(), 'Export Chart Data')]"),
                (By.XPATH, "//span[contains(text(), 'Export chart data')]"),
                (By.XPATH, "//div[@data-name='save-load-menu-item-export-chart-data']"),
                (By.CSS_SELECTOR, "div[data-role='menuitem'][aria-label='Export chart data…']")
            ]
            
            export_btn = None
            for by, val in export_selectors:
                try:
                    export_btn = wait.until(EC.element_to_be_clickable((by, val)))
                    export_btn.click()
                    print(f"Clicked 'Export Chart Data' with {by}={val}")
                    break
                except:
                    continue
            
            if not export_btn:
                raise Exception("Could not find 'Export Chart Data' button")
            
            # --- HANDLE EXPORT MODAL ---
            # Wait for modal
            time.sleep(2)
            export_submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[name='submit']")))
            export_submit.click()
            print("Clicked 'Export' in modal.")
            
            # Wait for download
            time.sleep(5)
            print("Download should have started.")
            
            # Check if file exists (in default download dir, which is usually user's Downloads)
            # Since we attached to existing Chrome, we can't easily change download dir via options 
            # without restarting. So we just notify user.
            print("Please check your default Downloads folder for the CSV file.")
            
        except Exception as e:
            print(f"Could not perform export via menu: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")
        
    finally:
        # Do NOT quit the driver, as it closes the user's browser
        print("Script finished. Detaching from browser.")
        # driver.quit() # Don't quit!

if __name__ == "__main__":
    run_selenium_downloader()
