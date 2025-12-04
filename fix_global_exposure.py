"""
Fix global function exposure issue in chart_ui.html
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Add global exposure for chart and series right after line 246
# Find the line: "            });"  after wickDownColor
# Add global exposure

# Fix 2: Add global exposure for functions at the end of initChart
# We'll add them right before the "// Initial Load" comment

# Let's find the right positions
lines = content.split('\n')

# Find where to add chart/series exposure (after line 246)
for i, line in enumerate(lines):
    if 'wickDownColor' in line and 'wickUpColor' in lines[i-1]:
        # Found the series definition, add exposure after the closing });
        if i+1 < len(lines) and '});' in lines[i+1]:
            lines.insert(i+2, '')
            lines.insert(i+3, '            // Expose globally for plugins')
            lines.insert(i+4, '            window.chart = chart;')
            lines.insert(i+5, '            window.chartSeries = series;')
            print(f"Added chart/series exposure after line {i+2}")
            break

# Find where to add function exposures (before "// Initial Load")
for i, line in enumerate(lines):
    if '// Initial Load' in line:
        # Add global exposures before this line
        exposures = [
            '',
            '            // Expose functions globally for HTML onclick handlers',
            '            window.changeTimeframe = changeTimeframe;',
            '            window.setTool = setTool;',
            '            window.clearDrawings = clearDrawings;',
            '            window.jumpToDate = jumpToDate;',
            '            window.toggleStrategy = toggleStrategy;',
            '            window.addIndicatorFromMenu = addIndicatorFromMenu;',
            '            window.addWatermark = addWatermark;',
            ''
        ]
        for idx, exp in enumerate(exposures):
            lines.insert(i + idx, exp)
        print(f"Added function exposures before line {i}")
        break

# Write back
new_content = '\n'.join(lines)
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("✅ Fixed global exposure issue!")
print("✅ Added window.chart and window.chartSeries")
print("✅ Added global exposure for all interactive functions")
