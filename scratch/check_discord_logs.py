def check_discord_logs():
    log_path = "strategy_engine.log"
    print("Checking Discord-related log entries for today (2026-05-19)...")
    
    discord_entries = []
    
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("2026-05-19"):
                if "discord" in line.lower() or "webhook" in line.lower():
                    discord_entries.append(line.strip())
                    
    print(f"\nFound {len(discord_entries)} Discord-related logs for today:")
    # Print the last 40 Discord logs
    for d in discord_entries[-40:]:
        print(f"  {d}")

if __name__ == "__main__":
    check_discord_logs()
