import requests
import json
import pprint

from scripts.streaming.options.config import HUB_RESOLVE_ENDPOINT

def test_resolve_dual():
    url = HUB_RESOLVE_ENDPOINT
    payload = {"symbols": ["/ES", "/NQ", "AAPL"]}
    
    try:
        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            print("Successfully called /resolve")
            pprint.pprint(resp.json())
        else:
            print(f"Failed /resolve: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_resolve_dual()
