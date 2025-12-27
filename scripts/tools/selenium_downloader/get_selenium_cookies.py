from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def get_cookies():
    print("Connecting to Chrome on port 9222...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        cookies = driver.get_cookies()
        print(f"Found {len(cookies)} cookies.")
        
        for c in cookies:
            print(f"Name: {c['name']}, Domain: {c['domain']}")
            if c['name'] == 'sessionid':
                print(f"SESSIONID FOUND: {c['value'][:10]}...")
            if c['name'] == 'auth_token': # Not sure if this is the cookie name
                print(f"AUTH_TOKEN FOUND: {c['value'][:10]}...")
                
        return cookies
    except Exception as e:
        print(f"Error: {e}")

def get_local_storage():
    print("Checking Local Storage...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        # We need to be on the tradingview domain to access its local storage
        if "tradingview.com" not in driver.current_url:
            print("Driver not on tradingview.com, cannot access local storage.")
            return

        # Execute JS to get local storage
        ls = driver.execute_script("return window.localStorage;")
        print(f"Found {len(ls)} items in Local Storage.")
        
        for k, v in ls.items():
            if "token" in k.lower() or "auth" in k.lower() or "user" in k.lower():
                print(f"Key: {k}, Value: {v[:50]}...")
                
    except Exception as e:
        print(f"Error: {e}")

def get_js_variables():
    print("Checking JS Variables...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
        # Check window.user
        try:
            user = driver.execute_script("return window.user;")
            print(f"window.user: {user}")
            if user and 'auth_token' in user:
                print(f"AUTH_TOKEN FOUND in window.user: {user['auth_token']}")
        except:
            print("window.user not found")

        # Check window.TV.user
        try:
            user = driver.execute_script("return window.TV.user;")
            # print(f"window.TV.user: {user}") # Might be large
            if user and 'auth_token' in user:
                print(f"AUTH_TOKEN FOUND in window.TV.user: {user['auth_token']}")
        except:
            print("window.TV.user not found")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_cookies()
    get_local_storage()
    get_js_variables()
