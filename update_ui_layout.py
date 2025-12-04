"""
Phase 1: Update chart_ui.html for Left Sidebar Layout
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Sidebar CSS Link
if '<link rel="stylesheet" href="css/sidebar.css">' not in content:
    content = content.replace(
        '<link rel="stylesheet" href="css/toolbar.css">',
        '<link rel="stylesheet" href="css/toolbar.css">\n    <link rel="stylesheet" href="css/sidebar.css">'
    )

# 2. Add Sidebar HTML
sidebar_html = """
    <!-- Left Sidebar -->
    <div id="drawing-sidebar">
        <button class="tool-btn" id="btn-line" onclick="setTool('line')" title="Line">📏</button>
        <button class="tool-btn" id="btn-ray" onclick="setTool('ray')" title="Trend Line">📉</button>
        <button class="tool-btn" id="btn-rect" onclick="setTool('rect')" title="Rectangle">▭</button>
        <button class="tool-btn" id="btn-fib" onclick="setTool('fib')" title="Fibonacci">🔢</button>
        <button class="tool-btn" id="btn-vert" onclick="setTool('vert')" title="Vertical Line">│</button>
        <button class="tool-btn" id="btn-text" onclick="addWatermark()" title="Text">T</button>
        
        <div class="tool-separator"></div>
        
        <button class="tool-btn delete" onclick="clearDrawings()" title="Clear All">🗑</button>
    </div>
"""

# Insert sidebar after <body>
if '<div id="drawing-sidebar">' not in content:
    content = content.replace('<body>', '<body>' + sidebar_html)

# 3. Remove Drawing Tools from Toolbar
# We need to remove the block of buttons
# <button id="btn-line" ...> ... <button ... title="Clear All Drawings">🗑</button>

# I'll use regex or string replacement for the specific block
# The block is:
#             <!-- Drawing Tools -->
#             <button id="btn-line" onclick="setTool('line')" title="Draw Price Line">📏 Line</button>
#             <button id="btn-ray" onclick="setTool('ray')" title="Draw Trend Line">📉 Trend</button>
#             <button id="btn-rect" onclick="setTool('rect')" title="Draw Rectangle">▭ Rect</button>
#             <button id="btn-fib" onclick="setTool('fib')" title="Draw Fibonacci">🔢 Fib</button>
#             <button id="btn-vert" onclick="setTool('vert')" title="Draw Vertical Line">│ Vert</button>
#             <button id="btn-text" onclick="addWatermark()" title="Add Watermark">T Text</button>
#             <button onclick="clearDrawings()" title="Clear All Drawings">🗑</button>
# 
#             <div class="divider"></div>

import re

# Regex to remove the drawing tools block
# Note: The buttons in HTML have specific attributes, I'll try to match loosely
pattern = r'<!-- Drawing Tools -->\s*<button id="btn-line".*?title="Clear All Drawings">🗑</button>\s*<div class="divider"></div>'
content = re.sub(pattern, '<!-- Drawing Tools Moved to Sidebar -->', content, flags=re.DOTALL)


# 4. Remove inline styles from #chart-container
# <div id="chart-container" style="display: flex; flex-direction: column; height: calc(100vh - 54px);">
content = content.replace(
    '<div id="chart-container" style="display: flex; flex-direction: column; height: calc(100vh - 54px);">',
    '<div id="chart-container">'
)

# 5. Remove inline styles from #chart
# <div id="chart" style="flex: 1; min-height: 400px;"></div>
content = content.replace(
    '<div id="chart" style="flex: 1; min-height: 400px;"></div>',
    '<div id="chart"></div>'
)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Updated chart_ui.html for Sidebar Layout")
