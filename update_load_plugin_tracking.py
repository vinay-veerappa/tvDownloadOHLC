"""
Update loadAndApplyPlugin to track displayName and update UI
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find and replace the primitive tracking line
old_primitive_push = "                    window.activePlugins.push({ name: moduleName, instance: primitive });"
new_primitive_push = "                    window.activePlugins.push({ name: moduleName, displayName: displayName, instance: primitive });"

content = content.replace(old_primitive_push, new_primitive_push)

# Find and replace the indicator tracking line
old_indicator_push = "                    window.activePlugins.push({ name: moduleName, series: indicatorSeries });"
new_indicator_push = "                    window.activePlugins.push({ name: moduleName, displayName: displayName, series: indicatorSeries });"

content = content.replace(old_indicator_push, new_indicator_push)

# Add updatePluginList() calls after success alerts
content = content.replace(
    '                    alert(`${displayName} enabled!`);',
    '                    alert(`${displayName} enabled!`);\n                    updatePluginList();'
)

content = content.replace(
    '                    alert(`${displayName} added!`);',
    '                    alert(`${displayName} added!`);\n                    updatePluginList();'
)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Updated loadAndApplyPlugin to store displayName")
print("✅ Added updatePluginList() calls after plugin load")
print("✅ Plugin list will automatically update when plugins are added")
