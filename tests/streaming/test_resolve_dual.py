import requests
import json
import pprint

def test_resolve_dual():
    url = "http://127.0.0.1:8080/resolve"
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
