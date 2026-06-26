import os
path = "output.log"
if os.path.exists(path):
    with open(path, "r", encoding="utf-16-le", errors="ignore") as f:
        content = f.read()
    lines = content.splitlines()
    print(f"Total lines in output.log: {len(lines)}")
    print("\nLast 50 lines of output.log:")
    for line in lines[-50:]:
        print(line)
else:
    print("output.log does not exist.")
