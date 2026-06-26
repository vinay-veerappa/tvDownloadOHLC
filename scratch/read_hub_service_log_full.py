import os
path = "logs/hub_service.log"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        safe_content = content.encode('ascii', errors='replace').decode('ascii')
        print(safe_content)
else:
    print(f"{path} does not exist.")
