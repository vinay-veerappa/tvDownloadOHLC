import re

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find and extract the plugin-related code that needs to be global
plugin_code = '''
        // Plugin/Module Registry (Global scope)
        window.pluginModules = new Map();
        window.activePlugins = [];

        // Dynamic module loader (Global scope - needs access to series)
        async function loadAndApplyPlugin(moduleName, displayName, type = 'primitive') {
            if (window.pluginModules.has(moduleName)) {
                alert(`${displayName} already loaded`);
                return;
            }
            
            // Get the series from the global chart (set by initChart)
            const series = window.chartSeries;
            if (!series) {
                alert('Chart not initialized yet. Please wait for the chart to load.');
                return;
            }
            
            try {
                // Import from plugins directory
                const module = await import('./plugins/' + moduleName + '.js');
                window.pluginModules.set(moduleName, module);
                
                // Apply based on type
                if (type === 'primitive') {
                    // For TooltipPrimitive, VertLine, etc.
                    const PrimitiveClass = module.default || module[Object.keys(module)[0]];
                    
                    let primitive;
                    if (moduleName === 'tooltip' || moduleName === 'delta-tooltip') {
                         primitive = new PrimitiveClass({
                            lineColor: 'rgba(0, 0, 0, 0.5)',
                            labelBackgroundColor: 'rgba(255, 255, 255, 0.9)',
                            labelTextColor: '#000'
                         });
                    } else {
                         primitive = new PrimitiveClass();
                    }

                    series.attachPrimitive(primitive);
                    window.activePlugins.push({ name: moduleName, instance: primitive });
                    console.log(`${displayName} enabled!`);
                }
                else if (type === 'indicator') {
                    // For moving-average, etc.
                    const indicatorFn = module.default || module[Object.keys(module)[0]];
                    const indicatorSeries = indicatorFn(series, { length: 20 });
                    window.activePlugins.push({ name: moduleName, series: indicatorSeries });
                    console.log(`${displayName} added!`);
                }
                
            } catch (error) {
                console.error(`Failed to load ${displayName}:`, error);
                alert(`Error loading ${displayName}: ${error.message}`);
            }
        }

'''

# Remove the plugin code from inside initChart function
pattern = r'\s*// Plugin/Module Registry.*?}\s*}\s*\n'
content = re.sub(pattern, '\n', content, flags=re.DOTALL)

# Add the plugin code before the initChart function
pattern2 = r'(<script>\s*// Wait for LightweightCharts to be ready)'
replacement2 = r'<script>' + plugin_code + r'        // Wait for LightweightCharts to be ready'
content = re.sub(pattern2, replacement2, content, count=1)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Moved plugin loader to global scope")
