import os
path = "tmp_spoke2.log"
if os.path.exists(path):
    with open(path, "r", encoding="utf-16-le", errors="ignore") as f:
        content = f.read()
    print("Content of tmp_spoke.log:")
    # Replace non-encodable characters for terminal printing
    safe_content = content.replace('\ufeff', '').encode('ascii', errors='replace').decode('ascii')
    print(safe_content)
else:
    print("tmp_spoke.log does not exist.")
