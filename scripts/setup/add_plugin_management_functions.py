"""
Add plugin management functions (remove, update UI, etc.)
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find where to add functions (after loadAndApplyPlugin, before initChart)
insertion_point = content.find("        window.loadAndApplyPlugin = loadAndApplyPlugin; // Expose globally")
if insertion_point == -1:
    print("❌ Could not find insertion point")
    exit(1)

# Move to end of that line
insertion_point = content.find("\n", insertion_point) + 1

# Plugin management functions
management_functions = """
        // Plugin Management Functions
        function updatePluginList() {
            const listDiv = document.getElementById('plugin-list');
            const countSpan = document.getElementById('plugin-count');
            
            if (window.activePlugins.length === 0) {
                listDiv.innerHTML = '<div style="color: #888; font-size: 12px; padding: 10px; text-align: center;">No plugins loaded</div>';
                countSpan.textContent = '0';
                return;
            }
            
            countSpan.textContent = window.activePlugins.length.toString();
            
            let html = '';
            window.activePlugins.forEach((plugin, index) => {
                html += `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px; margin: 2px 0; background: #1e222d; border-radius: 3px;">
                        <span style="color: #d1d4dc; font-size: 12px;">${plugin.displayName || plugin.name}</span>
                        <button onclick="removePlugin(${index})" style="background: #ef5350; color: white; border: none; padding: 2px 6px; border-radius: 2px; cursor: pointer; font-size: 10px;">✕</button>
                    </div>
                `;
            });
            listDiv.innerHTML = html;
        }
        window.updatePluginList = updatePluginList;
        
        function removePlugin(index) {
            if (index < 0 || index >= window.activePlugins.length) return;
            
            const plugin = window.activePlugins[index];
            
            try {
                // Remove primitive
                if (plugin.instance && plugin.instance.detach) {
                    plugin.instance.detach();
                }
                // Remove indicator series
                if (plugin.series && window.chart.removeSeries) {
                    window.chart.removeSeries(plugin.series);
                }
                
                window.activePlugins.splice(index, 1);
                window.pluginModules.delete(plugin.name);
                
                updatePluginList();
                console.log(`✅ Removed plugin: ${plugin.displayName || plugin.name}`);
            } catch (error) {
                console.error(`Error removing plugin:`, error);
                alert(`Error removing plugin: ${error.message}`);
            }
        }
        window.removePlugin = removePlugin;
        
        function clearAllPlugins() {
            if (window.activePlugins.length === 0) {
                alert('No plugins to remove');
                return;
            }
            
            if (!confirm(`Remove all ${window.activePlugins.length} plugins?`)) {
                return;
            }
            
            // Remove all in reverse order
            for (let i = window.activePlugins.length - 1; i >= 0; i--) {
                const plugin = window.activePlugins[i];
                try {
                    if (plugin.instance && plugin.instance.detach) {
                        plugin.instance.detach();
                    }
                    if (plugin.series && window.chart.removeSeries) {
                        window.chart.removeSeries(plugin.series);
                    }
                } catch (error) {
                    console.error(`Error removing ${plugin.name}:`, error);
                }
            }
            
            window.activePlugins = [];
            window.pluginModules.clear();
            updatePluginList();
            console.log('✅ All plugins removed');
        }
        window.clearAllPlugins = clearAllPlugins;
        
        function togglePluginManager() {
            const manager = document.getElementById('plugin-manager');
            manager.style.display = manager.style.display === 'none' ? 'block' : 'none';
        }
        window.togglePluginManager = togglePluginManager;

"""

# Insert the management functions
new_content = content[:insertion_point] + management_functions + content[insertion_point:]

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("✅ Added plugin management functions")
print("✅ updatePluginList() - Updates UI with current plugins")
print("✅ removePlugin(index) - Removes individual plugin")
print("✅ clearAllPlugins() - Removes all plugins with confirmation")
print("✅ togglePluginManager() - Shows/hides plugin list")
