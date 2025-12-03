import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

def connect_driver():
    print("Connecting to existing Chrome instance on port 9222...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    return webdriver.Chrome(options=chrome_options)

def test_export():
    driver = connect_driver()
    wait = WebDriverWait(driver, 10)
    
    print("Attempting to open menu...")
    # 1. Open Menu
    menu_selectors = [
        (By.CSS_SELECTOR, "button[data-name='save-load-menu']"),
        (By.XPATH, "//button[contains(@class, 'js-save-load-menu-open-button')]"),
        (By.XPATH, "//div[@data-name='header-toolbar-save-load']//button"),
        (By.XPATH, "//button[contains(@aria-label, 'Manage layouts')]"),
        (By.XPATH, "//div[contains(@class, 'layoutName')]")
    ]
    
    layout_menu = None
    for by, val in menu_selectors:
        try:
            layout_menu = wait.until(EC.element_to_be_clickable((by, val)))
            layout_menu.click()
            print(f"Clicked menu using {val}")
            break
        except:
            continue
            
    if not layout_menu:
        print("Failed to open menu.")
        return

    time.sleep(2)
    
    print("Looking for Export button...")
    # 2. Find Export Button
    # Dump all text in the menu to see what's there
    try:
        menu_items = driver.find_elements(By.CSS_SELECTOR, "div[data-role='menuitem']")
        print(f"Found {len(menu_items)} menu items.")
        for item in menu_items:
            print(f"Item: '{item.text}'")
            if "Export" in item.text:
                print(">>> FOUND EXPORT ITEM via text check")
                item.click()
                print("Clicked it.")
                return
    except Exception as e:
        print(f"Error inspecting menu: {e}")

    # Fallback specific selectors
    export_selectors = [
        (By.XPATH, "//*[contains(text(), 'Export chart data')]"),
        (By.CSS_SELECTOR, "div[data-role='menuitem'][aria-label*='Export']")
    ]
    
    for by, val in export_selectors:
        try:
            btn = driver.find_element(by, val)
            print(f"Found button via {val}: displayed={btn.is_displayed()}")
            btn.click()
            print("Clicked.")
            return
        except Exception as e:
            print(f"Failed {val}: {e}")

if __name__ == "__main__":
    test_export()
