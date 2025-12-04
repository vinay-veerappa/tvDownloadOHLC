import re

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the line with "const series = chart.addSeries" and add the global assignment after it
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    # Look for the closing of the series creation
    if "const series = chart.addSeries(window.LightweightCharts.CandlestickSeries" in line:
        # Find the closing of this statement (next line with });)
        for j in range(i+1, min(i+10, len(lines))):
            new_lines.append(lines[j])
            if '});' in lines[j]:
                # Add the global assignment
                new_lines.append('\r\n')
                new_lines.append('        // Expose series globally for plugin access\r\n')
                new_lines.append('        window.chartSeries = series;\r\n')
                # Skip the lines we just added
                for k in range(i+1, j+1):
                    lines[k] = ''  # Mark as processed
                break
        break

# Continue with remaining lines
for line in lines[i+1:]:
    if line:  # Only add non-empty (non-processed) lines
        new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Added global series exposure")
