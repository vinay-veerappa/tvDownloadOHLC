# ⚠️ DIRECT SCHWAB AUTH - BYPASSES THE HUB
# This test remains on the legacy schwabdev.Client path because it validates
# the raw option_chains endpoint behavior. If it prompts for a token, refresh
# tokens.db separately; all currently-broken market tests have been moved to the
# Hub proxy. Consider migrating this to the Hub if direct auth becomes flaky.
import json
import os
import pprint
from schwabdev import Client

def test_chains():
    secrets_path = "secrets.json"
    with open(secrets_path, "r") as f:
        secrets = json.load(f)

    client = Client(
        app_key=secrets["app_key"],
        app_secret=secrets["app_secret"],
        callback_url=secrets["callback_url"],
        tokens_db="tokens.db"
    )

    # Test /ES (Root)
    print("\n--- Testing option_chains for /ES ---")
    resp = client.option_chains(symbol="/ES")
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.text}")

    # Test resolved /ES (e.g. check current active contract first)
    print("\n--- Checking active contract for /ES ---")
    q = client.quotes(["/ES"])
    if q.status_code == 200:
        data = q.json()
        active = None
        for sym, val in data.items():
            if val.get("reference", {}).get("product") == "/ES":
                active = sym
                break
        print(f"Active contract: {active}")
        if active:
            print(f"--- Testing option_chains for {active} ---")
            resp = client.option_chains(symbol=active)
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Error: {resp.text}")
    else:
        print("Failed to get quote for /ES")

if __name__ == "__main__":
    test_chains()
