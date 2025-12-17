
import json
import requests
import os

def test_reddit_refinement():
    if not os.path.exists("token.json") or not os.path.exists("secrets.json"):
        print("Missing files.")
        return

    with open("token.json", "r") as f:
        token_data = json.load(f)
    
    acc_token = token_data.get('token', {}).get('access_token')
    
    auth_header = f"Bearer {acc_token}"
    
    header_sets = [
        {"Authorization": auth_header, "accept": "application/json"},
        {"Authorization": auth_header, "accept": "*/*"},
        {"Authorization": auth_header, "accept": "application/json", "Content-Type": "application/json"},
    ]
    
    url = "https://api.schwabapi.com/trader/v1/accounts/accountNumbers"
    
    for h in header_sets:
        print(f"\n--- Testing with headers: {list(h.keys())} | accept={h.get('accept')} ---")
        try:
            resp = requests.get(url, headers=h)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
            if resp.status_code == 401:
                print(f"WWW-Authenticate: {resp.headers.get('WWW-Authenticate')}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_reddit_refinement()
