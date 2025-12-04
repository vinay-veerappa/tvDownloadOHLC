"""
Add plugin management UI - list loaded plugins with remove buttons
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find where to add the plugin manager (after the chart div, before status)
insertion_point = content.find('        <div id="status">')
if insertion_point == -1:
    print("❌ Could not find status div")
    exit(1)

# Plugin manager HTML to insert BEFORE status div
plugin_manager_html = """        <!-- Plugin Manager -->
        <div id="plugin-manager" style="position: absolute; top: 60px; right: 10px; background: rgba(42, 46, 57, 0.95); border: 1px solid #4a4e59; border-radius: 4px; padding: 10px; width: 250px; max-height: 400px; overflow-y: auto; display: none;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid #4a4e59; padding-bottom: 8px;">
                <h3 style="margin: 0; font-size: 14px; color: #d1d4dc;">Active Plugins</h3>
                <button onclick="clearAllPlugins()" style="background: #d32f2f; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 11px;">Clear All</button>
            </div>
            <div id="plugin-list">
                <div style="color: #888; font-size: 12px; padding: 10px; text-align: center;">No plugins loaded</div>
            </div>
        </div>
        <button id="toggle-plugin-manager" onclick="togglePluginManager()" style="position: absolute; top: 65px; right: 10px; background: #2962FF; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; z-index: 100;">
            📋 Plugins (<span id="plugin-count">0</span>)
        </button>

"""

# Insert the plugin manager
new_content = content[:insertion_point] + plugin_manager_html + content[insertion_point:]

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("✅ Added plugin manager UI")
print("✅ Shows active plugins with remove buttons")
print("✅ Added toggle button for plugin list")
print("✅ Added 'Clear All' functionality")
