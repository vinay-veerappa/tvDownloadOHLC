import os
path = "logs/spoke_service.log"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        print(f.read())
else:
    print("logs/spoke_service.log does not exist.")
