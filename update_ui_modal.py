"""
Phase 2: Update chart_ui.html for Indicators Modal
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Modal CSS Link
if '<link rel="stylesheet" href="css/modal.css">' not in content:
    content = content.replace(
        '<link rel="stylesheet" href="css/sidebar.css">',
        '<link rel="stylesheet" href="css/sidebar.css">\n    <link rel="stylesheet" href="css/modal.css">'
    )

# 2. Add Modal HTML
modal_html = """
    <!-- Indicators Modal -->
    <div id="indicators-modal" class="modal-overlay">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">Indicators & Plugins</div>
                <button class="modal-close" onclick="closeIndicatorsModal()">×</button>
            </div>
            <div class="modal-body">
                <div class="modal-sidebar" id="modal-categories">
                    <!-- Categories populated by JS -->
                </div>
                <div class="modal-main">
                    <div class="search-container">
                        <input type="text" id="indicator-search" class="search-input" placeholder="Search indicators...">
                    </div>
                    <div class="items-grid" id="modal-items">
                        <!-- Items populated by JS -->
                    </div>
                </div>
            </div>
        </div>
    </div>
"""

# Insert modal before script tag
if '<div id="indicators-modal"' not in content:
    content = content.replace('<!-- Main Application Module -->', modal_html + '\n    <!-- Main Application Module -->')

# 3. Replace Toolbar Buttons
# Remove "Enhanced Plugins Menu" block
import re

# Remove Plugins Menu
content = re.sub(r'<!-- Enhanced Plugins Menu -->.*?</div>\s*</div>', '', content, flags=re.DOTALL)

# Remove Indicators Menu
content = re.sub(r'<!-- Enhanced Indicators Menu -->.*?</div>\s*</div>', '', content, flags=re.DOTALL)

# Replace "Indicators & Strategy" block
# Old block:
#             <!-- Indicators & Strategy -->
#             <select id="indicatorSelect" onchange="addIndicatorFromMenu(this)">
#                 ...
#             </select>
#             <button id="strategyBtn" onclick="toggleStrategy()">⚡ Strategy</button>

new_toolbar_buttons = """
            <!-- Indicators & Strategy -->
            <button onclick="openIndicatorsModal()">📊 Indicators</button>
            <button id="strategyBtn" onclick="toggleStrategy()">⚡ Strategy</button>
"""

content = re.sub(r'<!-- Indicators & Strategy -->.*?<button id="strategyBtn".*?</button>', new_toolbar_buttons, content, flags=re.DOTALL)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Updated chart_ui.html for Indicators Modal")
