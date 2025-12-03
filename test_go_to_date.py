import time
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
    return webdriver.Chrome(options=chrome_options)

def test_go_to_date(target_date="2024-01-01 12:00"):
    driver = connect_driver()
    wait = WebDriverWait(driver, 10)
    actions = ActionChains(driver)
    
    print(f"Testing Go To Date: {target_date}")
    
    # 0. Enter Bar Replay Mode (User Request)
    print("Attempting to enter Bar Replay mode...")
    try:
        # Selectors for Bar Replay button (toolbar)
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
                    time.sleep(2)
                    break
            except:
                continue
                
        if not replay_btn:
            print("Could not find Bar Replay button.")
        
        # Check for "Continue your last replay?" dialog
        print("Checking for Replay dialog...")
        time.sleep(1)
        try:
            # Look for "Start new" button
            start_new_btn = None
            start_new_selectors = [
                (By.XPATH, "//button[contains(text(), 'Start new')]"),
                (By.CSS_SELECTOR, "button[data-name='start-new-replay']"), # Guessing data-name
                (By.XPATH, "//div[contains(@class, 'dialog')]//button[contains(., 'Start new')]")
            ]
            
            for by, val in start_new_selectors:
                try:
                    start_new_btn = driver.find_element(by, val)
                    if start_new_btn.is_displayed():
                        start_new_btn.click()
                        print(f"Clicked 'Start new' button using {val}")
                        time.sleep(1)
                        break
                except:
                    continue
            
            if not start_new_btn:
                print("No 'Start new' dialog found (maybe already in replay mode or fresh start).")
                
        except Exception as e:
            print(f"Error checking replay dialog: {e}")

    except Exception as e:
        print(f"Error toggling Bar Replay: {e}")

    # 1. Find "Select date..." in Replay Toolbar
    print("Looking for Replay 'Select date' option...")
    
    # It might be under a dropdown or a direct button
    # Based on image, there is a "Select bar" button that might have a dropdown arrow, or it's a menu.
    
    try:
        # Try finding the dropdown trigger using data-qa-id
        print("Looking for dropdown trigger...")
        trigger = None
        
        trigger_selectors = [
            (By.CSS_SELECTOR, "[data-qa-id='select-date-bar-mode-menu']"),
            (By.CSS_SELECTOR, "button[data-qa-id='select-date-bar-mode-menu']"),
            (By.CSS_SELECTOR, "div[class*='selectDateBar__button']"), # The text part
            # The arrow part might be a sibling
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
            print("Could not find dropdown trigger.")
            return

        # Now look for "Select date..." in the open menu
        # Class-based selector strategy
        print("Looking for 'Select date' using class selector...")
        try:
            # Find ALL elements with 'selectDateBar' in class
            elements = driver.find_elements(By.CSS_SELECTOR, "[class*='selectDateBar']")
            print(f"Found {len(elements)} elements with 'selectDateBar' class.")
            
            found = False
            for el in elements:
                print(f"Element text: '{el.text}'")
                if "Select date" in el.text:
                    print("MATCH FOUND! Clicking...")
                    el.click()
                    found = True
                    time.sleep(2)
                    break
            
            if not found:
                print("No element with 'Select date' text found in class matches.")
                
        except Exception as e:
            print(f"Error searching classes: {e}")

        # Check if dialog opened
        print("Checking if dialog opened...")

    except Exception as e:
        print(f"Error interacting with replay menu: {e}")
        return

    # 2. Handle Date Input (if the dialog opened)
    print("Looking for date input in Replay dialog...")
    
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
                print(f"Found input using {val}")
                break
        except:
            continue
            
    if not date_input:
        print("Could not find date input!")
        return

    # 3. Clear and Type
    print("Clearing input...")
    date_input.click()
    time.sleep(0.5)
    
    # Try Ctrl+A + Delete first (standard)
    date_input.send_keys(Keys.CONTROL, "a")
    time.sleep(0.1)
    date_input.send_keys(Keys.DELETE)
    time.sleep(0.1)
    
    # Also send Backspace loop just in case
    for _ in range(5):
        date_input.send_keys(Keys.BACK_SPACE)
    
    print(f"Typing date: {target_date}")
    for char in list(target_date):
        date_input.send_keys(char)
        time.sleep(0.15) # Slower typing
        
    # Verify value
    current_val = date_input.get_attribute("value")
    print(f"Input value is now: '{current_val}'")
        
    print("Pressing Enter...")
    date_input.send_keys(Keys.ENTER)
    time.sleep(1)
    
    # Check if dialog is still open
    try:
        dialog = driver.find_element(By.CSS_SELECTOR, "div[data-name='go-to-date-dialog']")
        print("Dialog still open. Enter might not have worked.")
        
        # Dump dialog HTML
        print("Dialog HTML:")
        print(dialog.get_attribute('outerHTML'))
        
        # Look for a Go button
        print("Looking for Go button...")
        go_btn = dialog.find_element(By.CSS_SELECTOR, "button[data-name='submit-button']")
        if go_btn:
            print("Found Go button. Clicking...")
            go_btn.click()
        else:
            print("No specific Go button found.")
            
    except:
        print("Dialog closed (or not found). Assuming success.")

    print("Waiting 5 seconds for chart to load...")
    time.sleep(5)
    print("Test complete. Check if chart moved.")

if __name__ == "__main__":
    test_go_to_date("2025-11-01 10:00")
