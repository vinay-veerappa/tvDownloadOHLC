# Email & SMS Notifier

This document explains how to set up the Email & SMS notification utility (`scripts/utils/email_notify.py`) for the trading bot. This utility allows the bot to send alerts directly to your mobile phone (via Email-to-SMS gateways) or standard email addresses.

## Overview
The utility uses Python's built-in `smtplib` to send emails. It securely reads credentials from the system's `secrets.json` / `secrets.enc` file via the `credentials_manager.py`.

## Configuration

To use the notifier, you need to add the following keys to your `secrets.json` file in the root of the repository:

```json
{
  "email_user": "your.alert.bot@gmail.com",
  "email_password": "your-16-digit-app-password",
  "email_to": "1234567890@vtext.com"
}
```

* `email_user`: The email address the bot will send *from*.
* `email_password`: The password for the email account (see **Gmail App Passwords** below).
* `email_to`: The default destination address. 

### Syncing Secrets (Crucial Step)

The repository uses DPAPI encryption (`secrets.enc`) to securely store credentials. The `credentials_manager.py` will **always prefer `secrets.enc` over `secrets.json`**.

If you manually edit `secrets.json`, the bot **will not see your changes** until you sync them to the encrypted file. After modifying `secrets.json`, run the following in your terminal to sync the changes:

```powershell
.\.venv\Scripts\python.exe -c "import json; from scripts.streaming.credentials_manager import save_secrets, SECRETS_JSON; save_secrets(json.load(open(SECRETS_JSON, 'r')))"
```

## Sending to Mobile Phones (SMS)

To receive alerts as native text messages on your phone, set your `email_to` address to your carrier's SMS gateway:
* **AT&T:** `10-digit-number@txt.att.net`
* **Verizon:** `10-digit-number@vtext.com`
* **T-Mobile:** `10-digit-number@tmomail.net`

## Using a Dedicated Gmail Account (Recommended)

To avoid using your personal email, it is highly recommended to create a free, dedicated "burner" Gmail account for the bot.

Because Google requires 2-Factor Authentication, you **cannot** use your normal Gmail password in `secrets.json`. You must generate an App Password:

1. Log into your dedicated Gmail account and go to [myaccount.google.com](https://myaccount.google.com/).
2. Navigate to **Security**.
3. Ensure **2-Step Verification** is turned ON (required for App Passwords).
4. Search for **App passwords** in the top search bar.
5. Create a new App Password (name it "Trading Bot").
6. Copy the 16-character password (e.g. `abcd efgh ijkl mnop`) and place it in your `secrets.json` under `"email_password"`.

## Usage in Code

To trigger an alert from anywhere in the codebase:

```python
from scripts.utils.email_notify import send_email

# 1. Basic Fire-and-Forget SMS Alert (Non-blocking)
send_email(
    subject="🚨 SPX Level Break",
    body="SPX has crossed the Zero Gamma level."
)

# 2. Sending to Multiple Recipients with Attachments
send_email(
    subject="📊 Daily Macro Report",
    body="Attached is the daily macro overview.",
    to_email=["1234567890@vtext.com", "backup.email@gmail.com"],
    file_paths=["C:/path/to/macro_chart.png", "C:/path/to/walkthrough.md"]
)

# 3. Sending an HTML Email (blocking wait)
send_email(
    subject="🟢 Gamma Regime Change",
    body="<h1>Regime Shift</h1><p>The market has shifted to <b style='color:green'>Positive Gamma</b>.</p>",
    is_html=True,
    blocking=True
)
```

## Advanced Features
* **Async by Default:** `send_email` runs in a background thread so it never blocks your streaming options pipeline or backtesting engine.
* **Auto-Retries:** The utility automatically catches transient SMTP disconnects and retries 3 times with backoff.
* **MIME Auto-detection:** Attachments automatically guess the correct MIME type based on the file extension (e.g., image/png, text/markdown).
