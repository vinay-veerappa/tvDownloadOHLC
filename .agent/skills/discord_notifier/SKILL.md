---
name: Discord Notifier
description: Upload files and send messages to Discord channels via webhooks.
---

# Discord Notifier Skill

This skill provides utilities to send messages and upload files to Discord channels using named webhooks.

## Prerequisites

- A Discord webhook URL for the target channel
- Webhooks can be stored in `discord_webhooks.json` or hardcoded in the script

## Usage

### Upload to a Named Channel
```bash
python scripts/utils/discord_notify.py --channel test_channel --file /path/to/file.png --message "Here's your chart!"
```

### Available Channels
- `test_channel` - Default test/development channel

### Add New Channels
Edit `discord_webhooks.json` in the project root:
```json
{
  "test_channel": "https://discord.com/api/webhooks/...",
  "alerts": "https://discord.com/api/webhooks/..."
}
```

### Send a Text Message Only
```bash
python scripts/utils/discord_notify.py -c test_channel --message "Daily analysis complete!"
```

### Upload Multiple Files
```bash
python scripts/utils/discord_notify.py -c test_channel -f file1.png -f file2.png
```

## Integration

The script is integrated with the Daily Analysis workflow (`run_daily_prep.py`). After generating the ICT chart, it automatically posts to the `test_channel`.

## Script Location
`scripts/utils/discord_notify.py`

