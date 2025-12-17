
import json
import requests
import os

def test_user_preference():
    if not os.path.exists("token.json") or not os.path.exists("secrets.json"):
        print("Missing files.")
        return

    with open("token.json", "r") as f:
        token_data = json.load(f)
    
    acc_token = token_data.get('token', {}).get('access_token')
    
    headers = {
        "Authorization": f"Bearer {acc_token}",
        "accept": "application/json"
    }
    
    url = "https://api.schwabapi.com/trader/v1/userPreference"
    
    print(f"\n--- Testing {url} ---")
    resp = requests.get(url, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.text}")
    print(f"WWW-Authenticate: {resp.headers.get('WWW-Authenticate')}")

if __name__ == "__main__":
    test_user_preference()
