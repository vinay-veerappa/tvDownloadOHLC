import os
path = "C:/Users/vinay/.gemini/antigravity-ide/brain/1b9711e9-b979-43b3-aefc-9ff22c3a6a3f/.system_generated/tasks/task-1905.log"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        print(f.read())
else:
    print("Log file not found.")
