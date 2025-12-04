"""
Add dropdown menu CSS to chart_ui.html
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find the position after the date picker specific styles (around line 111)
insertion_point = content.find("        /* Date Picker specific */")
if insertion_point == -1:
    print("❌ Could not find insertion point")
    exit(1)

# Move to the end of that section (after the closing brace)
closing_brace = content.find("        }", insertion_point)
if closing_brace == -1:
    print("❌ Could not find closing brace")
    exit(1)

# Move past the closing brace and newline
insertion_point = closing_brace + len("        }")

# CSS to insert
dropdown_css = """

        /* Dropdown Menu Styles */
        .menu-dropdown {
            position: relative;
            display: inline-block;
        }
        .menu-content {
            display: none;
            position: absolute;
            background-color: #2a2e39;
            min-width: 220px;
            box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.5);
            z-index: 1000;
            border-radius: 4px;
            border: 1px solid #4a4e59;
            max-height: 450px;
            overflow-y: auto;
        }
        .menu-content a {
            color: #d1d4dc;
            padding: 10px 16px;
            text-decoration: none;
            display: block;
            font-size: 13px;
        }
        .menu-content a:hover {
            background-color: #3a3e49;
        }
        .menu-dropdown:hover .menu-content {
            display: block;
        }
        .menu-category {
            color: #888;
            padding: 8px 16px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
            border-top: 1px solid #363c4e;
        }
        .menu-category:first-child {
            border-top: none;
        }
        .plugin-badge {
            display: inline-block;
            background: #2962FF;
            color: white;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 10px;
            margin-left: 8px;
        }"""

# Insert the CSS
new_content = content[:insertion_point] + dropdown_css + content[insertion_point:]

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("✅ Added dropdown menu CSS")
print("✅ Styles include: .menu-dropdown, .menu-content, .menu-category, .plugin-badge")
