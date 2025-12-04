"""
Phase 0.2: Replace inline JS with module import in chart_ui.html
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the start of the script tag (line 170)
# Find the end of the script tag (line 811)

start_line = 169  # Index 169 is line 170
end_line = 811    # Index 811 is line 812

# Verify lines
print(f"Line {start_line+1}: {lines[start_line].strip()}")
print(f"Line {end_line}: {lines[end_line-1].strip()}")

# Keep everything before the script tag
new_lines = lines[:start_line]

# Add the module import
new_lines.append('    <!-- Main Application Module -->\n')
new_lines.append('    <script type="module" src="js/main.js"></script>\n')

# Add everything after the script tag
new_lines.extend(lines[end_line:])

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("✅ Replaced inline JS with module import successfully!")
print(f"✅ Removed {end_line - start_line} lines of inline JS")
print(f"✅ Total lines: {len(lines)} → {len(new_lines)}")
