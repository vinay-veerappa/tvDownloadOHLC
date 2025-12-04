"""
Fix plugin manager z-index and positioning so it's visible in normal mode
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find and replace the plugin-manager div styling
old_style = 'id="plugin-manager" style="position: absolute; top: 60px; right: 10px; background: rgba(42, 46, 57, 0.95); border: 1px solid #4a4e59; border-radius: 4px; padding: 10px; width: 250px; max-height: 400px; overflow-y: auto; display: none;">'

new_style = 'id="plugin-manager" style="position: fixed; top: 100px; right: 10px; background: rgba(42, 46, 57, 0.98); border: 1px solid #4a4e59; border-radius: 4px; padding: 10px; width: 250px; max-height: 400px; overflow-y: auto; display: none; z-index: 10000; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">'

content = content.replace(old_style, new_style)

# Also fix the toggle button positioning and z-index
old_button_style = 'id="toggle-plugin-manager" onclick="togglePluginManager()" style="position: absolute; top: 65px; right: 10px; background: #2962FF; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; z-index: 100;">'

new_button_style = 'id="toggle-plugin-manager" onclick="togglePluginManager()" style="position: fixed; top: 60px; right: 10px; background: #2962FF; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; z-index: 10001; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">'

content = content.replace(old_button_style, new_button_style)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Fixed plugin manager positioning")
print("✅ Changed from 'absolute' to 'fixed' positioning")
print("✅ Increased z-index to 10000 (manager) and 10001 (button)")
print("✅ Added box shadows for better visibility")
print("✅ Manager should now be visible in normal mode")
