import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def test_export():
    print("Connecting...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=chrome_options)
    
    # Attach
    handles = driver.window_handles
    for h in handles:
        driver.switch_to.window(h)
        if "TradingView" in driver.title:
            print(f"Found TV tab: {driver.title}")
            break
            
    wait = WebDriverWait(driver, 5)
    
    print("Attempting to detect Menu Button...")
    # List all candidate buttons
    candidates = driver.find_elements(By.TAG_NAME, "button")
    print(f"Found {len(candidates)} buttons on page (too many). Filtering...")
    
    # Try the known selectors
    selectors = [
        "button[data-name='save-load-menu']",
        "div[data-name='header-toolbar-save-load'] button",
        ".js-save-load-menu-open-button"
    ]
    
    menu_btn = None
    for sel in selectors:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                print(f"Selector '{sel}' found {len(elems)} elements.")
                for e in elems:
                    if e.is_displayed():
                        print(f"  -> Element is displayed. Clicking...")
                        e.click()
                        menu_btn = e
                        break
            if menu_btn: break
        except Exception as e:
            print(f"Error checking {sel}: {e}")
            
    time.sleep(2)
    
    print("Checking for Menu Items...")
    # Menu usually has items in a container. 
    # Look for ANY text "Export"
    try:
        exports = driver.find_elements(By.XPATH, "//*[contains(text(), 'Export')]")
        if exports:
            print(f"Found {len(exports)} elements with text 'Export':")
            for ex in exports:
                 print(f"  - Tag: {ex.tag_name}, Text: '{ex.text}', Visible: {ex.is_displayed()}")
                 # Print parent logic to see if it's a menu item
                 parent = ex.find_element(By.XPATH, "..")
                 print(f"    Parent: {parent.tag_name} class='{parent.get_attribute('class')}'")
        else:
            print("No 'Export' text found in DOM.")
            # Dump page source to file?
            # with open("tv_source.html", "w", encoding="utf-8") as f:
            #     f.write(driver.page_source)
    except Exception as e:
        print(f"Error searching text: {e}")

if __name__ == "__main__":
    test_export()
