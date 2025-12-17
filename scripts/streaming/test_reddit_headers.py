
import json
import requests
import os

def test_reddit_style():
    if not os.path.exists("token.json") or not os.path.exists("secrets.json"):
        print("Missing files.")
        return

    with open("token.json", "r") as f:
        token_data = json.load(f)
    
    acc_token = token_data.get('token', {}).get('access_token')
    
    # Reddit Headers
    headers = {
        "Authorization": f"Bearer {acc_token}",
        "accept": "*/*",
        "Content-Type": "application/json"
    }
    
    # Test multiple endpoints
    endpoints = [
        "https://api.schwabapi.com/trader/v1/accounts",
        "https://api.schwabapi.com/trader/v1/accounts/accountNumbers"
    ]
    
    for url in endpoints:
        print(f"\n--- Testing {url} ---")
        resp = requests.get(url, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
        if resp.status_code == 401:
            print(f"Headers[WWW-Authenticate]: {resp.headers.get('WWW-Authenticate')}")

if __name__ == "__main__":
    test_reddit_style()
