"""
Add plugin loader function to chart_ui.html
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find the position right before "// Wait for LightweightCharts ES module to load"
insertion_point = content.find("        // Wait for LightweightCharts ES module to load")

if insertion_point == -1:
    print("❌ Could not find insertion point")
    exit(1)

# Plugin loader code to insert
plugin_loader = """        // ===== PLUGIN SYSTEM =====
        // Plugin/Module Registry
        window.pluginModules = new Map();
        window.activePlugins = [];

        // Dynamic module loader
        async function loadAndApplyPlugin(moduleName, displayName, type = 'primitive') {
            if (window.pluginModules.has(moduleName)) {
                alert(`${displayName} already loaded`);
                return;
            }
            
            try {
                const module = await import('./plugins/' + moduleName + '.js');
                window.pluginModules.set(moduleName, module);
                
                // Apply based on type
                if (type === 'primitive') {
                    // For TooltipPrimitive, VertLine, etc.
                    const PrimitiveClass = module[Object.keys(module)[0]];
                    const primitive = new PrimitiveClass();
                    window.chartSeries.attachPrimitive(primitive);
                    window.activePlugins.push({ name: moduleName, instance: primitive });
                    console.log(`✅ Plugin '${displayName}' loaded and attached`);
                    alert(`${displayName} enabled!`);
                }
                else if (type === 'indicator') {
                    // For moving-average, etc.
                    const indicatorFn = module[Object.keys(module)[0]];
                    const indicatorSeries = indicatorFn(window.chartSeries, { length: 20 });
                    window.activePlugins.push({ name: moduleName, series: indicatorSeries });
                    console.log(`✅ Indicator '${displayName}' loaded and applied`);
                    alert(`${displayName} added!`);
                }
                
            } catch (error) {
                console.error(`Failed to load ${displayName}:`, error);
                alert(`Error loading ${displayName}: ${error.message}`);
            }
        }
        window.loadAndApplyPlugin = loadAndApplyPlugin; // Expose globally

"""

# Insert the plugin loader before the comment
new_content = content[:insertion_point] + plugin_loader + content[insertion_point:]

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("✅ Added loadAndApplyPlugin() function")
print("✅ Added plugin registry (Map and Array)")
print("✅ Exposed loadAndApplyPlugin globally")
