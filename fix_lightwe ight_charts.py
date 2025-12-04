import re

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find and replace the old script tag with the new module version
old_pattern = r'\s*<!-- Lightweight Charts v5\.0 -->\r?\n\s*<script src="https://unpkg\.com/lightweight-charts/dist/lightweight-charts\.standalone\.production\.js"></script>'

new_script = '''
    <!-- Lightweight Charts v5.0 - ES Module with global exposure -->
    <script type="module">
        import * as LightweightCharts from 'lightweight-charts';
        window.LightweightCharts = LightweightCharts;
    </script>'''

new_content = re.sub(old_pattern, new_script, content, count=1)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Replaced duplicate script with ES module version")
