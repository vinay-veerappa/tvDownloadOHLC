def check_details():
    log_path = "strategy_engine.log"
    print("Checking specific execution details...")
    
    daily_runs = []
    staleness_logs = []
    execution_logs = []
    ict_logs = []
    
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("2026-05-19"):
                line_lower = line.lower()
                if "tick_daily" in line_lower or "daily strategy" in line_lower:
                    daily_runs.append(line.strip())
                if "stale" in line_lower or "staleness" in line_lower:
                    staleness_logs.append(line.strip())
                if "execute" in line_lower or "signal" in line_lower or "trade" in line_lower:
                    # Filter for actual strategy trade execution or entries
                    if any(x in line_lower for x in ["entering", "exiting", "closed", "order", "fill", "paper"]):
                        execution_logs.append(line.strip())
                if "ict" in line_lower or "offload" in line_lower or "executor" in line_lower:
                    ict_logs.append(line.strip())
                    
    print(f"\nDaily Strategy Runs found today ({len(daily_runs)}):")
    for r in daily_runs:
        print(f"  {r}")
        
    print(f"\nStaleness / Guardrail Logs found today ({len(staleness_logs)}):")
    # Show last 15 staleness logs
    for s in staleness_logs[-15:]:
        print(f"  {s}")
        
    print(f"\nTrade Execution Logs found today ({len(execution_logs)}):")
    # Show last 20 execution logs
    for e in execution_logs[-20:]:
        print(f"  {e}")
        
    print(f"\nICT / ThreadPool Logs found today ({len(ict_logs)}):")
    # Show last 10 ict logs
    for i in ict_logs[-10:]:
        print(f"  {i}")

if __name__ == "__main__":
    check_details()
