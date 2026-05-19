import re
from datetime import datetime

def analyze_logs():
    log_path = "strategy_engine.log"
    print("Analyzing strategy_engine.log...")
    
    # We want to find log lines starting with "2026-05-19"
    today_lines = []
    job_registrations = []
    errors = []
    info_ticks = []
    
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "Starting Strategy Engine" in line or "Jobs registered" in line:
                job_registrations.append(line.strip())
            if line.startswith("2026-05-19"):
                today_lines.append(line.strip())
                if "[ERROR]" in line or "Exception" in line or "Error" in line:
                    errors.append(line.strip())
                if "tick_" in line or "eod_analytics" in line or "maintenance" in line:
                    info_ticks.append(line.strip())

    print(f"\nTotal log lines found for today (2026-05-19): {len(today_lines)}")
    
    print("\nMost Recent Job Seeding / Registrations in Logs:")
    for reg in job_registrations[-5:]:
        print(f"  {reg}")
        
    print("\nToday's Tick & Scheduled Job Actions (last 30 actions):")
    for tick in info_ticks[-30:]:
        print(f"  {tick}")
        
    print(f"\nToday's Errors (Total: {len(errors)}):")
    if errors:
        for err in errors[-10:]:
            print(f"  {err}")
    else:
        print("  No errors found in today's logs! Excellent.")

if __name__ == "__main__":
    analyze_logs()
