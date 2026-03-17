import schwab
import json

# Load access token from token.json (for client auth)
token_data = json.load(open('token.json'))
access_token = token_data['token']['access_token']

# Create Schwab client using secrets and token
def get_client():
    secrets = json.load(open('secrets.json'))
    return schwab.auth.client_from_token_file(
        token_path='token.json',
        api_key=secrets['app_key'],
        app_secret=secrets['app_secret'],
        enforce_enums=False,
    )

client = get_client()

# Try get_quotes for /ES
symbols = '/ES'
fields = 'quote'
try:
    result = client.get_quotes(symbols, fields=fields)
    print('get_quotes result:')
    print(result)
except Exception as e:
    print('get_quotes error:', e)
