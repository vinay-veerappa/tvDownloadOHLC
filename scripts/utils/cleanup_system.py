import os
import subprocess
import time

def kill_process_by_port(port):
    try:
        # Find PIDs using the port in LISTENING state
        cmd = f'netstat -ano | findstr LISTENING | findstr :{port}'
        output = subprocess.check_output(cmd, shell=True).decode()
        pids = set()
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[1].endswith(f":{port}"):
                pids.add(parts[-1])
        
        for pid in pids:
            print(f"  ➜ Killing process {pid} on port {port}...")
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass # Port not in use

def kill_python_scripts(script_names):
    try:
        # Get all python processes with their command lines
        cmd = 'wmic process where "name=\'python.exe\'" get commandline,processid'
        output = subprocess.check_output(cmd, shell=True).decode()
        for line in output.strip().split('\n'):
            for script in script_names:
                if script in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        # Only kill if PID is a number
                        if pid.isdigit():
                            print(f"  ➜ Killing stray script: {script} (PID: {pid})")
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except Exception as e:
        print(f"  ⚠️ Error during script cleanup: {e}")

def main():
    print("===================================================")
    print("🧹 SYSTEM SANITY CHECK & CLEANUP")
    print("===================================================")
    
    # 1. Clear ports
    print("Checking active ports (Hub:8080, API:8000, Web:3000)...")
    for port in [8080, 8000, 3000]:
        kill_process_by_port(port)
    
    # 2. Clear stray processes
    print("Checking for stray services...")
    scripts = [
        "schwab_hub", 
        "l2_processor_engine", 
        "stream_chart", 
        "api.main", 
        "run_options_levels"
    ]
    kill_python_scripts(scripts)
    
    # Small grace period for OS to release sockets
    time.sleep(1)
    print("===================================================")
    print("✅ System Cleaned and Ready.")
    print("===================================================\n")

if __name__ == "__main__":
    main()
