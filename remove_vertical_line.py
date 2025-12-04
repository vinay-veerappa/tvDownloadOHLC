"""
Remove Vertical Line from menu (requires configuration with chart reference and time)
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Remove Vertical Line
content = content.replace(
    '                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin(\'vertical-line\', \'Vertical Line\', \'primitive\');">Vertical Line</a>\n',
    ''
)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Removed 'Vertical Line' from menu (requires configuration)")
print("✅ Needs: chart reference and time coordinate")
