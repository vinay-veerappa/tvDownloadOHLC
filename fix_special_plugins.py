file_path = r"c:\Users\vinay\tvDownloadOHLC\chart_ui\chart_ui.html"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find and replace the volume-profile and session-highlighting initialization
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if we're at the volume-profile elif
    if "} else if (moduleName === 'volume-profile') {" in line:
        new_lines.append(line)
        # Skip the old code until the closing }
        i += 1
        depth = 1
        while i < len(lines) and depth > 0:
            if '{' in lines[i]:
                depth += 1
            if '}' in lines[i]:
                depth -= 1
            i += 1
        # Add new code
        new_lines.append("                         // VolumeProfile needs (chart, series, vpData)\r\n")
        new_lines.append("                         // Create sample profile data\r\n")
        new_lines.append("                         const vpData = {\r\n")
        new_lines.append("                             time: Date.now() / 1000,\r\n")
        new_lines.append("                             width: 15,\r\n")
        new_lines.append("                             profile: Array.from({length: 20}, (_, i) => ({\r\n")
        new_lines.append("                                 price: 4500 + i * 10,\r\n")
        new_lines.append("                                 vol: Math.random() * 100\r\n")
        new_lines.append("                             }))\r\n")
        new_lines.append("                         };\r\n")
        new_lines.append("                         primitive = new PrimitiveClass(window.chart, series, vpData);\r\n")
        continue
        
    # Check if we're at the session-highlighting elif
    elif "} else if (moduleName === 'session-highlighting') {" in line:
        new_lines.append(line)
        # Skip the old code until the closing }
        i += 1
        depth = 1
        while i < len(lines) and depth > 0:
            if '{' in lines[i]:
                depth += 1
            if '}' in lines[i]:
                depth -= 1
            i += 1
        # Add new code
        new_lines.append("                         // SessionHighlighting needs (highlighter, options)\r\n")
        new_lines.append("                         const highlighter = (timestamp) => {\r\n")
        new_lines.append("                             // Highlight weekends\r\n")
        new_lines.append("                             const date = new Date(timestamp * 1000);\r\n")
        new_lines.append("                             const day = date.getUTCDay();\r\n")
        new_lines.append("                             if (day === 0 || day === 6) {\r\n")
        new_lines.append("                                 return 'rgba(68,138,255,0.1)';  // Blue for weekends\r\n")
        new_lines.append("                             }\r\n")
        new_lines.append("                             return null;\r\n")
        new_lines.append("                         };\r\n")
        new_lines.append("                         primitive = new PrimitiveClass(highlighter, {});\r\n")
        continue
    else:
        new_lines.append(line)
        i += 1

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Fixed volume-profile and session-highlighting initialization")
