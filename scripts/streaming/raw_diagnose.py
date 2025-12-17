
import json
import base64
import requests
import datetime
import os

def diagnose_token():
    if not os.path.exists("token.json") or not os.path.exists("secrets.json"):
        print("Missing files.")
        return

    with open("token.json", "r") as f:
        token_data = json.load(f)
    
    with open("secrets.json", "r") as f:
        secrets = json.load(f)

    # Decode access token (JWT if Schwab uses it, or just info)
    acc_token = token_data.get('token', {}).get('access_token')
    if not acc_token:
        print("No access token found.")
        return

    print(f"Token Length: {len(acc_token)}")
    
    # Try to parse if it's a JWT
    try:
        parts = acc_token.split('.')
        if len(parts) == 3:
            payload = json.loads(base64.b64decode(parts[1] + "==").decode('utf-8'))
            print("\n--- JWT Payload ---")
            print(json.dumps(payload, indent=2))
    except:
        print("Token is not a visible JWT.")

    # Check expiration
    expires_at = token_data.get('token', {}).get('expires_at')
    if expires_at:
        dt = datetime.datetime.fromtimestamp(expires_at)
        print(f"Token Expires At: {dt.isoformat()}")

    # Raw Request
    print("\n--- Raw Request to /accounts ---")
    headers = {
        "Authorization": f"Bearer {acc_token}",
        "accept": "application/json"
    }
    url = "https://api.schwabapi.com/trader/v1/accounts"
    resp = requests.get(url, headers=headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response Body: {resp.text}")
    print(f"Response Headers: {dict(resp.headers)}")

if __name__ == "__main__":
    diagnose_token()
