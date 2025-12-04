"""
Remove Anchored Text from menu (requires configuration)
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Remove Anchored Text line
content = content.replace(
    '                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin(\'anchored-text\', \'Anchored Text\', \'primitive\');">Anchored Text</a>\n',
    ''
)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Removed 'Anchored Text' from menu (requires configuration)")
print("✅ Menu now shows only zero-config plugins that work immediately")
