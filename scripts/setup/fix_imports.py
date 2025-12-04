import os
import re
import glob

def fix_plugin_imports(directory):
    # Pattern to match: const { ... } = window.LightweightCharts;
    # We want to capture the content inside { }
    pattern = re.compile(r'const\s*\{(.*?)\}\s*=\s*window\.LightweightCharts;')
    
    files = glob.glob(os.path.join(directory, "*.js"))
    print(f"Found {len(files)} JS files in {directory}")
    
    count = 0
    for filepath in files:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if file has the import
        if pattern.search(content):
            def replace_import(match):
                imports = match.group(1)
                # Replace ' as ' with ': ' for destructuring
                imports = imports.replace(' as ', ': ')
                return f'const {{{imports}}} = window.LightweightCharts;'
            
            # Replace with const { ... } = window.LightweightCharts;
            new_content = pattern.sub(replace_import, content)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"Fixed: {os.path.basename(filepath)}")
            count += 1
            
    print(f"Total files fixed: {count}")

if __name__ == "__main__":
    fix_plugin_imports("chart_ui")
