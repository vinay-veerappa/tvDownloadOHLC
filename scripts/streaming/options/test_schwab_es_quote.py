import requests
import json

# Load access token from token.json
token_data = json.load(open('token.json'))
access_token = token_data['token']['access_token']

#url = 'https://api.schwabapi.com/marketdata/v1/AAPL/quotes'
url = 'https://api.schwabapi.com/marketdata/v1/quotes?symbols=%2FES&fields=quote'
headers = {
    'Authorization': f'Bearer {access_token}',
    'Accept': 'application/json',
}

response = requests.get(url, headers=headers)
print(url)
print('\nStatus:', response.status_code)
print('Response:')
print(response.text)
