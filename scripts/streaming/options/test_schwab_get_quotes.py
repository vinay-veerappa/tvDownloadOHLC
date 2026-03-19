import logging
import json
from scripts.streaming.options.config import SECRETS_PATH, TOKEN_PATH
from scripts.streaming.options.options_fetcher import create_client

# Set up logging to see the output clearly
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

def test_legacy_futures_symbols():
    client = create_client(SECRETS_PATH, TOKEN_PATH)
    
    # Testing variations of the weekly/continuous options roots
    test_symbols = ["NQH0", "/NQW0", "EW0", "/EW0", "NQM", "/NQW"]
    
    log.info("Testing Legacy TOS Futures Options Roots...")
    log.info("=" * 50)
    
    for sym in test_symbols:
        log.info(f"Pinging API for symbol: {sym}")
        
        response = client.get_option_chain(
            symbol=sym,
            contract_type="ALL",
            include_underlying_quote=True,
            strategy="SINGLE",
            strike_count=5 
        )
        
        if response.status_code == 200:
            payload = response.json()
            status = payload.get("status")
            call_map = payload.get("callExpDateMap", {})
            
            if status == "SUCCESS" and call_map:
                log.info(f"  [✓] SUCCESS! Schwab accepted '{sym}'")
                log.info(f"  ↳ Returned {len(call_map)} expiration dates.")
                
                # Print the first available expiration date to verify it's current
                first_exp = list(call_map.keys())[0]
                log.info(f"  ↳ First available expiry: {first_exp}\n")
            else:
                log.info(f"  [!] 200 OK, but chain was empty. Status: {status}\n")
                
        else:
            log.error(f"  [X] HTTP {response.status_code} - API Rejected.\n")

if __name__ == "__main__":
    test_legacy_futures_symbols()