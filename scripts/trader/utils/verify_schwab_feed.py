import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import logging

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from schwab.auth import easy_client
    from schwab.client import Client
except ImportError:
    easy_client = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("verify_feed")

REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_PATH = REPO_ROOT / "secrets.json"
TOKEN_PATH = REPO_ROOT / "token.json"

SCHWAB_SYMBOLS = ["$VIX", "$VVIX"]
YF_SYMBOLS = ["^VIX", "^VVIX", "BZ=F", "^TNX", "DX-Y.NYB", "ES=F", "NQ=F"]

def get_schwab_client():
    if not easy_client:
        log.warning("schwab-py is not installed.")
        return None

    if not SECRETS_PATH.exists() or not TOKEN_PATH.exists():
        log.warning(f"Missing Schwab credentials at {SECRETS_PATH} or {TOKEN_PATH}")
        return None

    try:
        with open(SECRETS_PATH, "r") as f:
            secrets = json.load(f)
        
        client = easy_client(
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            callback_url='https://127.0.0.1:8182',
            token_path=str(TOKEN_PATH),
            enforce_enums=False
        )
        return client
    except Exception as e:
        log.error(f"Schwab Auth failed: {e}")
        return None

def verify_schwab(client):
    log.info("--- Testing Schwab API Quotes ---")
    if not client:
        log.error("Schwab client not available. Test skipped.")
        return False
    
    success = True
    for symbol in SCHWAB_SYMBOLS:
        try:
            resp = client.get_quote(symbol)
            if resp.status_code == 200:
                data = resp.json()
                if symbol in data:
                    quote = data[symbol].get("quote", {})
                    last_price = quote.get("lastPrice", "N/A")
                    net_change = quote.get("netChange", "N/A")
                    log.info(f"[OK] Schwab Quote {symbol}: Last={last_price}, Change={net_change}")
                else:
                    log.warning(f"[WARN] Schwab returned 200 but no data for {symbol}")
                    success = False
            else:
                log.error(f"[FAIL] Schwab Quote {symbol}: {resp.status_code} - {resp.text}")
                success = False
        except Exception as e:
            log.error(f"[FAIL] Schwab Exception {symbol}: {e}")
            success = False
    return success

def verify_yfinance():
    log.info("--- Testing yfinance Fallback Quotes ---")
    if not yf:
        log.error("yfinance library not installed. Fallback test skipped.")
        return False
    
    success = True
    for symbol in YF_SYMBOLS:
        try:
            ticker = yf.Ticker(symbol)
            fast_info = ticker.fast_info
            last_price = fast_info.last_price
            prev_close = fast_info.previous_close
            change = last_price - prev_close if prev_close else 0.0
            log.info(f"[OK] yfinance Quote {symbol}: Last={last_price:.2f}, Change={change:.2f}")
        except Exception as e:
            log.error(f"[FAIL] yfinance Exception {symbol}: {e}")
            success = False
    return success

if __name__ == "__main__":
    log.info("Starting Feed Verification...")
    
    client = get_schwab_client()
    schwab_ok = verify_schwab(client)
    
    yf_ok = verify_yfinance()
    
    if schwab_ok and yf_ok:
        log.info("SUCCESS: Schwab and yfinance feeds are fully operational.")
        sys.exit(0)
    elif yf_ok:
        log.warning("WARNING: Schwab feed failed, but yfinance fallback is fully operational.")
        sys.exit(0)
    else:
        log.error("CRITICAL: Both Schwab and yfinance feeds failed. Data pipeline broken.")
        sys.exit(1)
