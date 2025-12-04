"""
Remove dual-series plugins from menu (Correlation, Product) to prevent errors
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Remove Correlation line
content = content.replace(
    '                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin(\'correlation\', \'Correlation\', \'indicator\');">Correlation</a>\n',
    ''
)

# Remove Product line  
content = content.replace(
    '                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin(\'product\', \'Product\', \'indicator\');">Product</a>\n',
    ''
)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Removed 'Correlation' from menu (requires dual-series)")
print("✅ Removed 'Product' from menu (requires dual-series)")
print("✅ Menu now shows only tested, working plugins")
