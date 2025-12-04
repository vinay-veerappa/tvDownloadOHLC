"""
Phase 0.1: Extract CSS from chart_ui.html into separate files
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the <style> tag (line 27) and </style> tag (line 163)
# Replace lines 27-163 with just the CSS links

new_lines = lines[:26]  # Keep everything before <style>

# Add the CSS link tags
new_lines.append('    <!-- CSS -->\n')
new_lines.append('    <link rel="stylesheet" href="css/main.css">\n')
new_lines.append('    <link rel="stylesheet" href="css/toolbar.css">\n')

# Add everything after </style> (line 163 onwards)
new_lines.extend(lines[162:])  # Line 163 is index 162

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("✅ Extracted CSS successfully!")
print(f"✅ Removed {len(lines[26:162])} lines of inline CSS")
print("✅ Added 3 lines linking to external CSS files")
print(f"✅ Total lines: {len(lines)} → {len(new_lines)}")
print(f"✅ Reduction: {len(lines) - len(new_lines)} lines")
