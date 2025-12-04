import re

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Wrap the main script content in an event listener
pattern = r'(<script>\r?\n\s+// --- Configuration ---)'

replacement = r'''<script>
        // Wait for LightweightCharts to be ready
        function initChart() {
        // --- Configuration ---'''

content = re.sub(pattern, replacement, content, count=1)

# Find the end of the script and close the function
# Look for the last occurrence of loadData before </script>
pattern2 = r"(loadTickers\(\);\s+loadData\('1h'\);)\s+(</script>)"

replacement2 = r'''\1
        }
        
        // Check if LightweightCharts is already loaded (in case this script runs after the module)
        if (window.LightweightCharts) {
            initChart();
        } else {
            window.addEventListener('lightweightChartsReady', initChart);
        }
    \2'''

content = re.sub(pattern2, replacement2, content, count=1, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Wrapped main script in initialization function")
