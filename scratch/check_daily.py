def check_daily_runs():
    log_path = "strategy_engine.log"
    print("Checking daily jobs and scan counts in strategy_engine.log for 2026-05-19...")
    
    daily_logs = []
    tick_stock_count = 0
    tick_index_count = 0
    eod_analytics_count = 0
    errors_today = []
    
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("2026-05-19"):
                if "tick_daily" in line or "daily strategy" in line:
                    daily_logs.append(line.strip())
                if "tick_stock" in line:
                    tick_stock_count += 1
                if "tick_index" in line:
                    tick_index_count += 1
                if "eod_analytics" in line or "daily_rollup" in line:
                    eod_analytics_count += 1
                if "[ERROR]" in line or "Exception" in line or "Error" in line:
                    errors_today.append(line.strip())
                    
    print(f"\n[1] Daily Scan Jobs (`tick_daily`):")
    if daily_logs:
        for dl in daily_logs:
            print(f"  {dl}")
    else:
        print("  No `tick_daily` logs found for today.")
        
    print(f"\n[2] Cadence Counts:")
    print(f"  Index Scan Ticks (`tick_index`): {tick_index_count}")
    print(f"  Stock Scan Ticks (`tick_stock`): {tick_stock_count}")
    print(f"  EOD Analytics Rollup: {eod_analytics_count}")
    
    print(f"\n[3] Total Errors Today: {len(errors_today)}")
    if errors_today:
        print("  Sample errors:")
        # unique sample of errors to avoid duplicates cluttering
        unique_samples = list(set([err.split(":")[-1].strip() for err in errors_today]))[:10]
        for s in unique_samples:
            print(f"    - {s}")
            
if __name__ == "__main__":
    check_daily_runs()
