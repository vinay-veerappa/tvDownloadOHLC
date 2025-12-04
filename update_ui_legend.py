"""
Phase 3: Update chart_ui.html for Chart Legend
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Legend CSS Link
if '<link rel="stylesheet" href="css/legend.css">' not in content:
    content = content.replace(
        '<link rel="stylesheet" href="css/modal.css">',
        '<link rel="stylesheet" href="css/modal.css">\n    <link rel="stylesheet" href="css/legend.css">'
    )

# 2. Add Legend HTML
# Insert it after #chart-container starts, or just before it?
# It's fixed position, so anywhere in body is fine.
# Let's put it after #drawing-sidebar
legend_html = """
    <!-- Chart Legend -->
    <div id="chart-legend" class="chart-legend">
        <!-- Populated by JS -->
    </div>
"""

if '<div id="chart-legend"' not in content:
    content = content.replace('<!-- Left Sidebar -->', legend_html + '\n    <!-- Left Sidebar -->')

# 3. Remove Old Plugin Manager
import re

# Remove Plugin Manager Div
content = re.sub(r'<div id="plugin-manager".*?</div>\s*</div>', '', content, flags=re.DOTALL)

# Remove Toggle Button
content = re.sub(r'<button id="toggle-plugin-manager".*?</button>', '', content, flags=re.DOTALL)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Updated chart_ui.html for Chart Legend")
