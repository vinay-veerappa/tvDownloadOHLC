import re

file_path = r'c:\Users\vinay\tvDownloadOHLC\scripts\indicators\htf_ema_analysis\HTF_EMA_Analysis.pine'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace "#.2" with "#.00"
content = content.replace('\"#.2\"', '\"#.00\"')

# Replace "#.1" with "#.0"
content = content.replace('\"#.1\"', '\"#.0\"')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Pine script formatting fixed!")
