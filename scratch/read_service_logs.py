import os

for path in ["logs/hub_service.log", "logs/spoke_service.log"]:
    print(f"\n=== {path} ===")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        print(f"Total lines: {len(lines)}")
        for line in lines[-20:]: # print last 20 lines
            # Strip non-ascii for safe console printing
            safe_line = line.strip().encode('ascii', errors='replace').decode('ascii')
            print(safe_line)
    else:
        print("File does not exist.")
