"""
Fix global function exposure issue in chart_ui.html - Second attempt
"""

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.split('\n')

# Fix: Add global exposure for chart and series after the series is created
for i, line in enumerate(lines):
    if "wickDownColor: '#ef5350'" in line:
        # Look ahead for the closing });
        for j in range(i, min(i+5, len(lines))):
            if '});' in lines[j] and 'addSeries' in content[max(0, content.find('wickDownColor')-500):content.find('wickDownColor')]:
                # Found it! Add exposure right after
                insert_pos = j + 1
                if insert_pos < len(lines):
                    # Check if already added
                    if 'window.chart' not in '\n'.join(lines[insert_pos:insert_pos+5]):
                        lines.insert(insert_pos, '')
                        lines.insert(insert_pos+1, '            // Expose globally forplugins and console access')
                        lines.insert(insert_pos+2, '            window.chart = chart;')
                        lines.insert(insert_pos+3, '            window.chartSeries = series;')
                        print(f"✅ Added chart/series exposure after line {j+1}")
                        break
        break

# Write back
new_content = '\n'.join(lines)
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("✅ Complete!")
