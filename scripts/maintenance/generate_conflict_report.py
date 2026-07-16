import os
import json
import glob
from datetime import datetime
import argparse
import sys

# Add project root to path to import discord_notify
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.utils.discord_notify import get_webhook_url, send_message

DATA_DIR = os.path.join(project_root, "data", "live")

def generate_report():
    """Find and summarize all bootstrap conflict files."""
    conflict_files = glob.glob(os.path.join(DATA_DIR, "bootstrap_conflicts_*.json"))
    
    if not conflict_files:
        return "✅ No bootstrap conflicts found. Data integrity looks good."

    summary = "📉 **Data Integrity Conflict Report**\n"
    summary += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    summary += "---\n"

    total_conflicts = 0
    
    for file_path in conflict_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                symbol = data.get("symbol", "Unknown")
                count = data.get("conflict_count", 0)
                total_conflicts += count
                
                summary += f"### {symbol}\n"
                summary += f"- **Conflicts Found**: {count}\n"
                
                if count > 0:
                    summary += "- **Top Discrepancies**:\n"
                    # Sort by abs diff_pct descending
                    conflicts = sorted(data.get("conflicts", []), key=lambda x: abs(x.get("diff_pct", 0)), reverse=True)
                    
                    # Show top 5
                    for c in conflicts[:5]:
                        summary += f"  - `{c['time_str']}`: Hist {c['historical_open']} vs Boot {c['bootstrap_open']} ({c['diff_pct']}%)\n"
                    
                    if len(conflicts) > 5:
                        summary += f"  - *...and {len(conflicts) - 5} more*\n"
                summary += "\n"
        except Exception as e:
            summary += f"⚠️ Error reading {os.path.basename(file_path)}: {e}\n"

    summary += "---\n"
    summary += f"**Total Conflicts Blocked**: {total_conflicts}\n"
    summary += "Note: These conflicts were automatically rejected from storage to preserve historical accuracy."
    
    return summary

def main():
    parser = argparse.ArgumentParser(description="Generate and notify bootstrap conflicts")
    parser.add_argument("--discord", action="store_true", help="Send report to Discord")
    parser.add_argument("--channel", default="test_channel", help="Discord channel name")
    parser.add_argument("--clear", action="store_true", help="Delete conflict files after reporting")
    
    args = parser.parse_args()
    
    report = generate_report()
    print(report)
    
    if args.discord:
        webhook_url = get_webhook_url(args.channel)
        if webhook_url:
            send_message(webhook_url, report)
        else:
            print("❌ Failed to get Discord webhook URL")

    if args.clear:
        conflict_files = glob.glob(os.path.join(DATA_DIR, "bootstrap_conflicts_*.json"))
        for f in conflict_files:
            try:
                os.remove(f)
                print(f"✅ Cleared {os.path.basename(f)}")
            except Exception as e:
                print(f"❌ Failed to clear {os.path.basename(f)}: {e}")

if __name__ == "__main__":
    main()
