import os

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    # Identify the start of the dangling block
    if '<option value="" disabled selected>+ Indicators</option>' in line:
        skip = True
    
    # Identify the end of the dangling block (the last option)
    if '<option value="atr">ATR (14)</option>' in line:
        skip = False
        continue # Skip this last line too

    if skip:
        continue
        
    new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"Processed {len(lines)} lines. New count: {len(new_lines)}")
