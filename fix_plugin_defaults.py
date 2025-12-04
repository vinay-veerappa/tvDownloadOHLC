import re

file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find and replace the primitive initialization block
old_code = r'''let primitive;
                    if \(moduleName === 'tooltip' \|\| moduleName === 'delta-tooltip'\) \{
                         primitive = new PrimitiveClass\(\{
                            lineColor: 'rgba\(0, 0, 0, 0\.5\)',
                            labelBackgroundColor: 'rgba\(255, 255, 255, 0\.9\)',
                            labelTextColor: '#000'
                         \}\);
                    \} else \{
                         primitive = new PrimitiveClass\(\);
                    \}'''

new_code = '''let primitive;
                    if (moduleName === 'tooltip' || moduleName === 'delta-tooltip') {
                         primitive = new PrimitiveClass({
                            lineColor: 'rgba(0, 0, 0, 0.5)',
                            labelBackgroundColor: 'rgba(255, 255, 255, 0.9)',
                            labelTextColor: '#000'
                         });
                    } else if (moduleName === 'volume-profile') {
                         primitive = new PrimitiveClass({
                            profile: {
                                rowSize: 10,
                                width: 15,
                                showValueArea: true
                            }
                         });
                    } else if (moduleName === 'session-highlighting') {
                         primitive = new PrimitiveClass({
                            highlighter: (timestamp) => {
                                // Simple example: highlight weekends
                                const date = new Date(timestamp * 1000);
                                const day = date.getUTCDay();
                                return day === 0 || day === 6;  // Sunday or Saturday
                            }
                         });
                    } else {
                         primitive = new PrimitiveClass();
                    }'''

content = re.sub(old_code, new_code, content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated plugin initialization with better defaults")
