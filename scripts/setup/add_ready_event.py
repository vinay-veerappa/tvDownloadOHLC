import re

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the module script and add the event dispatch
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    # Add event dispatch after window.LightweightCharts assignment
    if "window.LightweightCharts = LightweightCharts;" in line:
        indent = "        "  # Match the indentation
        new_lines.append(f"{indent}// Dispatch event to signal library is ready\n")
        new_lines.append(f"{indent}window.dispatchEvent(new Event('lightweightChartsReady'));\n")

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Added event dispatch")
