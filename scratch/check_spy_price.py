
import requests
import json

HUB_URL = "http://127.0.0.1:8080"

def check_spy():
    try:
        # get_option_chain returns the underlying as well
        params = {
            "symbol": "SPY",
            "strikeCount": 1
        }
        resp = requests.post(f"{HUB_URL}/request", json={"method": "get_option_chain", "params": params}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print("Hub Option Chain Response (Underlying Part):")
            # The data might be nested in 'data' if it's a 'success' status
            if data.get("status") == "success":
                inner = data.get("data", {})
                print(json.dumps(inner.get("underlying", {}), indent=2))
                print(f"underlyingPrice: {inner.get('underlyingPrice')}")
            else:
                # Direct response
                print(json.dumps(data.get("underlying", {}), indent=2))
                print(f"underlyingPrice: {data.get('underlyingPrice')}")
        else:
            print(f"Hub returned status {resp.status_code}")
    except Exception as e:
        print(f"Failed to reach Hub: {e}")

if __name__ == "__main__":
    check_spy()
