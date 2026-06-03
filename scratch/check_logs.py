import os

log_path = "c:/Users/vinay/tvDownloadOHLC/strategy_engine.log"
if not os.path.exists(log_path):
    log_path = "strategy_engine.log"

if os.path.exists(log_path):
    print(f"Reading logs from {log_path}...")
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    
    matches = [line.strip() for line in lines if "ZERO_DTE_PCS_10D_5W_SPY" in line]
    print(f"Found {len(matches)} matching log lines.")
    for m in matches[-15:]:
        print(m)
else:
    print("strategy_engine.log not found.")
