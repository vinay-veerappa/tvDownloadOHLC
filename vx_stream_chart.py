from schwab.auth import easy_client
from schwab.client import Client
from schwab.streaming import StreamClient

import asyncio
import json

# Assumes you've already created a token. See the authentication page for more
# information.
client = easy_client(
        api_key='h0R0afB9sjKVRZsjmgoQTtsXwLM6z0ffq9LOAarsA0d7dl0d',
        app_secret='P9G0ZzUyGtYFrVX9UPwenDBtn8EljzCmNa5PmspBxdARfpn1D5N0lQt3Y4cqlBSm',
        callback_url='https://127.0.0.1:8182',
        token_path='token.json')
stream_client = StreamClient(client, account_id=48382579)

async def read_stream():
    await stream_client.login()

    def print_message(message):
      print(json.dumps(message, indent=4))

    # Always add handlers before subscribing because many streams start sending
    # data immediately after success, and messages with no handlers are dropped.
    stream_client.add_nasdaq_book_handler(print_message)
    await stream_client.nasdaq_book_subs(['GOOG'])

    while True:
        await stream_client.handle_message()

asyncio.run(read_stream())