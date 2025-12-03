import pandas as pd
import time
import logging
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from tvDatafeed import TvDatafeed, Interval

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_auth_token_from_selenium():
    print("Connecting to Chrome on port 9222 to extract auth_token...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        # Check window.user.auth_token
        token = driver.execute_script("return window.user ? window.user.auth_token : null;")
        if token:
            print("Successfully extracted auth_token from browser session.")
            return token
        else:
            print("Could not find auth_token in window.user.")
            return None
    except Exception as e:
        print(f"Error extracting token: {e}")
        return None

class TvDatafeedHacked(TvDatafeed):
    def __init__(self, username=None, password=None, token=None):
        # We bypass standard init's auth if token is provided
        self.ws_debug = False
        
        if token:
            self.token = token
        else:
            self.token = self._TvDatafeed__auth(username, password)

        if self.token is None:
            self.token = "unauthorized_user_token"
            logger.warning("you are using nologin method, data you access may be limited")

        self.ws = None
        self.session = self._TvDatafeed__generate_session()
        self.chart_session = self._TvDatafeed__generate_chart_session()
        
    def get_hist_large(self, symbol, exchange='NSE', interval=Interval.in_1_minute, n_bars=10000):
        # Fetch as much as possible in one go
        logger.info(f"Fetching {n_bars} bars...")
        df = self.get_hist(symbol, exchange, interval, n_bars)
        return df

if __name__ == "__main__":
    # Try to get token from Selenium first
    token = get_auth_token_from_selenium()
    
    # Fallback to credentials if needed
    username, password = None, None
    if not token:
        try:
            with open("credentials.json", "r") as f:
                creds = json.load(f)
                username = creds.get("username")
                password = creds.get("password")
        except:
            pass

    tv = TvDatafeedHacked(username, password, token=token)
    
    # Target: ES Futures
    symbol = 'ES1!'
    exchange = 'CME_MINI'
    interval = Interval.in_1_minute
    
    # Note: Server seems to limit single request to ~9000 bars
    total_bars = 10000 
    
    print(f"Attempting to download {total_bars} bars for {symbol}:{exchange}...")
    
    df = tv.get_hist_large(symbol, exchange, interval, n_bars=total_bars)
    
    if df is not None:
        filename = "data_hacked_es.csv"
        df.to_csv(filename)
        print(f"Saved {len(df)} rows to {filename}")
        print(f"Time Range: {df.index.min()} to {df.index.max()}")
        print(df.head())
        print(df.tail())
