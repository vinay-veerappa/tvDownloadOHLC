from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def dump_source():
    print("Connecting to existing Chrome instance on port 9222...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=chrome_options)
    
    print("Dumping page source...")
    with open("page_source_debug.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("Saved to page_source_debug.html")

if __name__ == "__main__":
    dump_source()
