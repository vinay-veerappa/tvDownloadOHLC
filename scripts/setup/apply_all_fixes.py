import subprocess
import sys

scripts = [
    'python', '"fix_lightwe ight_charts.py"',
    'python', 'add_ready_event.py',
    'python', 'wrap_main_script.py',
    'python', 'fix_plugin_scope.py',
    'python', 'add_global_series.py',
    'python', 'add_global_chart.py'
]

# Run in pairs (command and script name)
for i in range(0, len(scripts), 2):
    cmd = f"{scripts[i]} {scripts[i+1]}"
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)

print("\nAll scripts completed successfully!")
