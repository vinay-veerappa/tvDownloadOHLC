import requests
import json
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestFuturesREST")

from scripts.streaming.options.config import HUB_URL

def hub_request(method, params):
    try:
        resp = requests.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return None

def test_resolve():
    logger.info("--- Testing Resolve ---")
    res = hub_request("resolve", {"symbols": ["/NQ", "/ES"]})
    print(json.dumps(res, indent=2))
    return res

def test_quotes(symbols):
    logger.info(f"--- Testing Quotes for {symbols} ---")
    res = hub_request("get_quotes", {"symbols": symbols})
    print(json.dumps(res, indent=2))
    return res

if __name__ == "__main__":
    # 1. Test Resolve
    resolve_data = test_resolve()
    
    if resolve_data and resolve_data.get("status") == "success":
        data = resolve_data.get("data", {})
        nq_active = data.get("/NQ", {}).get("active")
        if nq_active:
            # 2. Test Quote for active contract
            test_quotes([nq_active])
            
            # 3. Test Quote for a hypothetical futures option symbol
            # We'll just try a guess based on the format provided: ./ROOT{month}{year}{C/P}{strike}
            # For NQM26, strike 18000
            opt_sym = f"./{nq_active.replace('/', '')}C18000"
            logger.info(f"Testing hypothetical option: {opt_sym}")
            test_quotes([opt_sym])
    else:
        logger.error("Resolve failed, cannot proceed with quote tests.")
