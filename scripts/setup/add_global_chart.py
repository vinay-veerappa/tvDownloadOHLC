file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the line with "window.chartSeries = series;" and add chart exposure
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if "window.chartSeries = series;" in line:
        # Add chart exposure right after
        new_lines.append("        window.chart = chart;\r\n")

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Added global chart exposure")
