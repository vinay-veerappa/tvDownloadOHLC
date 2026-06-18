import os
import sys
import json
import schwab

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
token_path = os.path.join(root_dir, "token.json")
secrets_path = os.path.join(root_dir, "secrets.json")

def main():
    print(f"Loading secrets from: {secrets_path}")
    with open(secrets_path, "r") as f:
        secrets = json.load(f)

    print("Starting Schwab Authentication Flow...")
    try:
        client = schwab.auth.client_from_login_flow(
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            callback_url=secrets["callback_url"],
            token_path=token_path,
            enforce_enums=False
        )
        print("\nSuccessfully authenticated and saved token to token.json!")
    except Exception as e:
        print(f"\nError during authentication: {e}")

if __name__ == "__main__":
    main()
