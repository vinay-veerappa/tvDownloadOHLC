"""
Add plugin and indicator dropdown menus to chart_ui.html toolbar
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find the divider before indicators (around line 158)
# Look for the comment "<!-- Indicators & Strategy -->"
insertion_point = content.find("            <!-- Indicators & Strategy -->")
if insertion_point == -1:
    print("❌ Could not find insertion point")
    exit(1)

# Plugin menus HTML to insert BEFORE the indicators comment
plugin_menus = """            <!-- Enhanced Plugins Menu -->
            <div class="menu-dropdown">
                <button>🧩 Plugins</button>
                <div class="menu-content">
                    <div class="menu-category">Tooltips</div>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('tooltip', 'Tooltip', 'primitive');">Crosshair Tooltip</a>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('delta-tooltip', 'Delta Tooltip', 'primitive');">Delta Tooltip</a>
                    
                    <div class="menu-category">Visual</div>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('volume-profile', 'Volume Profile', 'primitive');">Volume Profile</a>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('session-highlighting', 'Session Highlighting', 'primitive');">Session Highlighting</a>
                    
                    <div class="menu-category">Drawing Tools</div>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('vertical-line', 'Vertical Line', 'primitive');">Vertical Line</a>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('anchored-text', 'Anchored Text', 'primitive');">Anchored Text</a>
                    
                    <div class="menu-category">Price Lines</div>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('user-price-lines', 'Price Lines', 'primitive');">User Price Lines</a>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('user-price-alerts', 'Price Alerts', 'primitive');">Price Alerts</a>
                </div>
            </div>

            <!-- Enhanced Indicators Menu -->
            <div class="menu-dropdown">
                <button>📊 Plugin Indicators</button>
                <div class="menu-content">
                    <div class="menu-category">Trend</div>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('moving-average', 'Moving Average', 'indicator');">Moving Average</a>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('momentum', 'Momentum', 'indicator');">Momentum</a>
                    
                    <div class="menu-category">Price Analysis</div>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('average-price', 'Average Price', 'indicator');">Average Price</a>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('median-price', 'Median Price', 'indicator');">Median Price</a>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('weighted-close', 'Weighted Close', 'indicator');">Weighted Close</a>
                    
                    <div class="menu-category">Mathematical</div>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('percent-change', 'Percent Change', 'indicator');">Percent Change</a>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('correlation', 'Correlation', 'indicator');">Correlation</a>
                    <a href="#" onclick="event.preventDefault(); loadAndApplyPlugin('product', 'Product', 'indicator');">Product</a>
                </div>
            </div>

"""

# Insert the plugin menus before the indicators comment
new_content = content[:insertion_point] + plugin_menus + content[insertion_point:]

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("✅ Added 'Plugins' dropdown menu")
print("✅ Added 'Plugin Indicators' dropdown menu")
print("✅ Menus include 16+ plugin options")
print("✅ All menu items call loadAndApplyPlugin() function")
