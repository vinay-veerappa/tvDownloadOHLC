import re

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find the position to insert the import map (before the lightweight-charts script)
pattern = r'(\s*<!-- Lightweight Charts v5\.0 -->\r?\n\s*<script src="https://unpkg\.com/lightweight-charts/dist/lightweight-charts\.standalone\.production\.js"></script>)'

import_map = '''    <!-- Import Map for ES6 Modules -->
    <script type="importmap">
    {
        "imports": {
            "lightweight-charts": "https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.mjs"
        }
    }
    </script>
'''

# Insert the import map before the lightweight-charts script
new_content = re.sub(pattern, import_map + r'\1', content, count=1)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Import map added successfully")
