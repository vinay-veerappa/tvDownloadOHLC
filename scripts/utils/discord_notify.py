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
    # Add manual overrides here or use discord_webhooks.json
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

def upload_file(webhook_url, file_path, message=None):
    """
    Helper to upload a single file.
    """
    return send_message(webhook_url, message, [file_path])

def send_message(webhook_url, message, files=None):
    """
    Send a message and/or files to Discord.
    
    Args:
        webhook_url: Discord webhook URL
        message: Text message to send
        files: List of file paths to upload
    
    Returns:
        True if all successful, False otherwise
    """
    try:
        # Split message if too long
        MAX_LENGTH = 1900 # Safe margin below 2000
        messages = []
        
        if message:
            if len(message) <= MAX_LENGTH:
                messages.append(message)
            else:
                # Split by newlines to keep formatting
                current_chunk = ""
                for line in message.split('\n'):
                    if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
                        messages.append(current_chunk)
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
                if current_chunk:
                    messages.append(current_chunk)
        else:
            messages = [None] # Just send files if no message

        success = True
        
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

        # Send each message chunk
        for i, msg in enumerate(messages):
            # Only attach files to the last message to avoid duplication or separation context
            # Or send files with the first message? 
            # Strategy: Send text chunks first, then text+files in the last chunk, 
            # OR if no text, just files.
            
            # Actually, standard practice: Send files with the last chunk of text.
            current_files = files_data if (i == len(messages) - 1) else None
            
            payload = {}
            if msg: payload['content'] = msg
            
            if current_files:
                response = requests.post(
                    webhook_url,
                    data={'content': msg} if msg else None,
                    files=current_files
                )
            elif msg:
                # Text only chunk
                response = requests.post(
                    webhook_url,
                    json=payload
                )
            else:
                continue # Should not happen unless empty message and no files

            if response.status_code not in [200, 204]:
                print(f"❌ Discord Error: {response.status_code} - {response.text}")
                success = False
        
        # Close files
        for f in opened_files:
            f.close()
            
        if success:
            print(f"✅ Discord: Message sent successfully ({len(messages)} chunks)!")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ Discord Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Send to Discord")
    parser.add_argument("--message", "-m", help="Message to send", default="")
    parser.add_argument("--message-file", "-mf", help="Path to file containing message text")
    parser.add_argument("--file", "-f", action="append", help="File(s) to upload")
    parser.add_argument("--channel", "-c", help="Named channel (e.g., test_channel)", default=DEFAULT_CHANNEL)
    parser.add_argument("--webhook", "-w", help="Direct webhook URL override")
    
    args = parser.parse_args()
    
    message = args.message
    if args.message_file:
        try:
            with open(args.message_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if message:
                    message += "\n" + content
                else:
                    message = content
        except Exception as e:
            print(f"Error reading message file: {e}")
            sys.exit(1)
    
    if not message and not args.file:
        print("Error: Provide --message, --message-file, and/or --file")
        sys.exit(1)
    
    webhook_url = get_webhook_url(args.channel, args.webhook)
    if not webhook_url:
        sys.exit(1)
        
    success = send_message(webhook_url, message, args.file)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

