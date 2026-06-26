import subprocess
import time
import sys
import os

print("Running stream_chart synchronously for 15 seconds...")
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"

proc = subprocess.Popen([sys.executable, "-u", "-m", "scripts.streaming.stream_chart"],
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8")

start_time = time.time()
lines = []
while time.time() - start_time < 15:
    # Read whatever is available
    if proc.poll() is not None:
        break
    time.sleep(0.5)

# Read remaining output
output, _ = proc.communicate()
print("Process Output:")
for line in output.splitlines():
    safe_line = line.strip().encode('ascii', errors='replace').decode('ascii')
    print(safe_line)
print(f"Process exited with code: {proc.returncode}")

# Clean up
if proc.poll() is None:
    print("Terminating process...")
    proc.terminate()
    proc.wait()
    print("Process terminated.")
