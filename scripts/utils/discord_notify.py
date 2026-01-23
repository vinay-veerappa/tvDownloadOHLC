"""
Discord Notifier Utility

Upload files and send messages to Discord via webhooks.

Usage:
    python discord_notify.py --channel test_channel --file /path/to/file.png --message "Description"
    python discord_notify.py --message "Text only message"
"""

import os
import sys
import json
import argparse
import requests

# Named webhook channels (can be extended via discord_webhooks.json)
WEBHOOK_CHANNELS = {
    "test_channel": "https://discord.com/api/webhooks/1463758018096271483/dW3Q5Y9IyuQIhykvN2z-YSR3F5Qa2OKfiUcSezh3cqX-IOItzAEWJrGXFRZmr0qZRZtt",
    # Add more channels here or in discord_webhooks.json
}

DEFAULT_CHANNEL = "test_channel"

def get_webhook_url(channel_name=None, override_url=None):
    """Get webhook URL from channel name, override, or config file."""
    if override_url:
        return override_url
    
    channel = channel_name or DEFAULT_CHANNEL
    
    # Try loading from discord_webhooks.json first
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(root_dir, "discord_webhooks.json")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                channels = json.load(f)
                if channel in channels:
                    return channels[channel]
        except:
            pass
    
    # Fallback to built-in channels
    if channel in WEBHOOK_CHANNELS:
        return WEBHOOK_CHANNELS[channel]
    
    print(f"Error: Unknown channel '{channel}'. Available: {list(WEBHOOK_CHANNELS.keys())}")
    return None

def send_message(webhook_url, message, files=None):
    """
    Send a message and/or files to Discord.
    
    Args:
        webhook_url: Discord webhook URL
        message: Text message to send
        files: List of file paths to upload
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Prepare payload
        payload = {}
        if message:
            payload['content'] = message
        
        # Prepare files
        files_data = []
        opened_files = []
        
        if files:
            for i, file_path in enumerate(files):
                if os.path.exists(file_path):
                    f = open(file_path, 'rb')
                    opened_files.append(f)
                    filename = os.path.basename(file_path)
                    files_data.append((f'file{i}', (filename, f)))
                else:
                    print(f"Warning: File not found: {file_path}")
        
        # Send request
        if files_data:
            response = requests.post(
                webhook_url,
                data={'content': message} if message else None,
                files=files_data
            )
        else:
            response = requests.post(
                webhook_url,
                json=payload
            )
        
        # Close files
        for f in opened_files:
            f.close()
        
        if response.status_code in [200, 204]:
            print(f"✅ Discord: Message sent successfully!")
            return True
        else:
            print(f"❌ Discord Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Discord Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Send to Discord")
    parser.add_argument("--message", "-m", help="Message to send", default="")
    parser.add_argument("--file", "-f", action="append", help="File(s) to upload")
    parser.add_argument("--channel", "-c", help="Named channel (e.g., test_channel)", default=DEFAULT_CHANNEL)
    parser.add_argument("--webhook", "-w", help="Direct webhook URL override")
    
    args = parser.parse_args()
    
    if not args.message and not args.file:
        print("Error: Provide --message and/or --file")
        sys.exit(1)
    
    webhook_url = get_webhook_url(args.channel, args.webhook)
    if not webhook_url:
        sys.exit(1)
        
    success = send_message(webhook_url, args.message, args.file)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

