import os
path = os.path.join("logs", "hub.log")
if os.path.exists(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    print(f"Total lines in {path}: {len(lines)}")
    print(f"\nLast 50 lines of {path}:")
    for line in lines[-50:]:
        print(line.strip())
else:
    print(f"{path} does not exist.")
