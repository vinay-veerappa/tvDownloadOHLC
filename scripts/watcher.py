# filepath: scripts/watcher.py
import os
import sys
import time
import json
import urllib.request
from datetime import datetime, timezone

HEARTBEAT_PATH = r"C:\Users\vinay\Documents\NinjaTrader 8\RiskGuard\heartbeat.txt"
CONFIG_DIR = r"c:\Users\vinay\tvDownloadOHLC"
WEBHOOKS_FILE = os.path.join(CONFIG_DIR, "discord_webhooks.json")
STALE_THRESHOLD_SECONDS = 15.0  # Alert after 3 missed heartbeats

def send_discord_alert(webhook_url, message):
    payload = {"content": f"⚠️ **RISK GUARD ALERT:** {message}"}
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "RiskGuardWatchdog"},
        )
        with urllib.request.urlopen(req) as res:
            if res.status != 204 and res.status != 200:
                print(f"[{datetime.now().isoformat()}] Discord Webhook returned status {res.status}", file=sys.stderr)
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Failed to send Discord webhook: {e}", file=sys.stderr)

def get_alerts_webhook():
    if os.path.exists(WEBHOOKS_FILE):
        try:
            with open(WEBHOOKS_FILE, "r") as f:
                data = json.load(f)
                return data.get("alerts")
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Failed to parse webhooks file: {e}", file=sys.stderr)
    return None

def main():
    print(f"[{datetime.now().isoformat()}] Starting Risk Guard Watchdog...")
    print(f"[{datetime.now().isoformat()}] Monitoring path: {HEARTBEAT_PATH}")
    print(f"[{datetime.now().isoformat()}] Alert threshold: {STALE_THRESHOLD_SECONDS} seconds")

    webhook_url = get_alerts_webhook()
    if webhook_url:
        print(f"[{datetime.now().isoformat()}] Discord Webhook loaded: {webhook_url[:40]}...")
    else:
        print(f"[{datetime.now().isoformat()}] No Discord Webhook configured. Logging to console only.", file=sys.stderr)

    last_alert_state = False  # True if we are currently in a stale state to prevent spamming

    while True:
        try:
            if not os.path.exists(HEARTBEAT_PATH):
                msg = f"Heartbeat file does not exist at: {HEARTBEAT_PATH}. Is the NinjaTrader addon running?"
                print(f"[{datetime.now().isoformat()}] {msg}", file=sys.stderr)
                if not last_alert_state and webhook_url:
                    send_discord_alert(webhook_url, msg)
                    last_alert_state = True
                time.sleep(5)
                continue

            # Read timestamp from file
            with open(HEARTBEAT_PATH, "r") as f:
                ts_str = f.read().strip()

            try:
                # Parse ISO timestamp: "2026-07-15T22:34:50.9198559Z"
                # Remove Z and parse
                clean_ts = ts_str.replace("Z", "+00:00")
                hb_time = datetime.fromisoformat(clean_ts).astimezone(timezone.utc)
                now_utc = datetime.now(timezone.utc)
                elapsed = (now_utc - hb_time).total_seconds()

                if elapsed > STALE_THRESHOLD_SECONDS:
                    msg = f"Heartbeat is stale by {elapsed:.1f} seconds! NinjaTrader UI or the Risk Guard Add-On might be frozen or hung."
                    print(f"[{datetime.now().isoformat()}] {msg}", file=sys.stderr)
                    if not last_alert_state:
                        if webhook_url:
                            send_discord_alert(webhook_url, msg)
                        last_alert_state = True
                else:
                    if last_alert_state:
                        msg = f"Heartbeat recovered. Stale delay was {elapsed:.1f} seconds."
                        print(f"[{datetime.now().isoformat()}] {msg}")
                        if webhook_url:
                            send_discord_alert(webhook_url, msg)
                        last_alert_state = False
                    # Normal log output (optional, keep it quiet)
                    # print(f"[{datetime.now().isoformat()}] Heartbeat OK (elapsed: {elapsed:.1f}s)")

            except Exception as ex:
                print(f"[{datetime.now().isoformat()}] Failed to parse timestamp '{ts_str}': {ex}", file=sys.stderr)

        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Watchdog loop error: {e}", file=sys.stderr)

        time.sleep(5)

if __name__ == "__main__":
    main()
