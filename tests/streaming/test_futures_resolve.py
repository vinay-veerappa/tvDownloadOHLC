import asyncio
import json
import os
from scripts.streaming.providers.schwab_py_provider import SchwabPyProvider

async def test_futures_resolution():
    provider = SchwabPyProvider("secrets.json", "token.json")
    await provider.initialize()
    
    # Try to get quotes for the root symbol to see if it resolves or provides the active contract
    # Normally, you fetch /ES and look for the 'activeLink' or similar, 
    # OR you fetch a list of futures to find the one with the highest volume/OI.
    
    symbols = ["/ES", "/NQ"]
    print(f"Fetching quotes for: {symbols}")
    
    result = await provider.send_rest_request("get_quotes", {"symbols": symbols})
    print(json.dumps(result, indent=2))
    
    # Also try get_futures_status or similar if available
    # In schwab-py, we usually check the response for alternative symbols or 'active' status.

if __name__ == "__main__":
    asyncio.run(test_futures_resolution())
