from schwab.auth import easy_client
from schwab.client import Client
from schwab.streaming import StreamClient

import asyncio
import json

# Assumes you've already created a token. See the authentication page for more
# information.
import os
with open("secrets.json", "r") as f:
    secrets = json.load(f)

client = easy_client(
        api_key=secrets["app_key"],
        app_secret=secrets["app_secret"],
        callback_url='https://127.0.0.1:8182',
        token_path='token.json')
stream_client = StreamClient(client, account_id='BB4E515511E76B8B035DC72194CA615919766D183922871CF062DB9ACA6E0EBD')

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