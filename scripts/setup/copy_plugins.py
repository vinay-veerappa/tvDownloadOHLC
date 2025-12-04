import os
import shutil
import glob

SOURCE_DIR = r"c:\Users\vinay\tvDownloadOHLC\temp_repo\plugin-examples\compiled"
DEST_DIR = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\plugins"

if not os.path.exists(DEST_DIR):
    os.makedirs(DEST_DIR)
    print(f"Created {DEST_DIR}")

# Walk through source and copy .js files
count = 0
for root, dirs, files in os.walk(SOURCE_DIR):
    for file in files:
        if file.endswith(".js"):
            src_path = os.path.join(root, file)
            dst_path = os.path.join(DEST_DIR, file)
            shutil.copy2(src_path, dst_path)
            print(f"Copied {file}")
            count += 1

print(f"Total plugins copied: {count}")
