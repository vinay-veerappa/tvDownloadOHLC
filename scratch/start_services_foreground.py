import subprocess
import time
import sys
import os

def kill_port(port):
    try:
        cmd = f'netstat -ano | findstr LISTENING | findstr :{port}'
        output = subprocess.check_output(cmd, shell=True).decode()
        for line in output.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[1].endswith(f":{port}"):
                pid = parts[-1]
                print(f"Killing port {port} (PID: {pid})...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True)
    except Exception:
        pass

def kill_scripts(names):
    try:
        output = subprocess.check_output('wmic process where "name=\'python.exe\'" get commandline,processid', shell=True).decode()
        for line in output.strip().split('\n'):
            for name in names:
                if name in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit() and int(pid) != os.getpid():
                            print(f"Killing script {name} (PID: {pid})...")
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True)
    except Exception as e:
        print(f"Error: {e}")

def main():
    print("Stopping Schwab Hub and Stream Chart...")
    kill_port(8080)
    kill_port(8001)
    kill_scripts(["schwab_hub", "stream_chart"])
    
    time.sleep(2)
    
    # Run the services using python -u without CREATE_NEW_CONSOLE
    # So they run as standard background processes and write logs to files in logs/
    os.makedirs("logs", exist_ok=True)
    
    # Force UTF-8 environment
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    print("Starting Schwab Hub in background, logging to logs/hub_service.log...")
    with open("logs/hub_service.log", "w", encoding="utf-8") as out:
        hub_proc = subprocess.Popen([sys.executable, "-u", "-m", "scripts.streaming.schwab_hub", "--port", "8080"],
                                    env=env,
                                    stdout=out,
                                    stderr=out)
                                    
    time.sleep(5)
    
    print("Starting Stream Chart in background, logging to logs/spoke_service.log...")
    with open("logs/spoke_service.log", "w", encoding="utf-8") as out:
        spoke_proc = subprocess.Popen([sys.executable, "-u", "-m", "scripts.streaming.stream_chart"],
                                      env=env,
                                      stdout=out,
                                      stderr=out)
                                      
    print(f"Services started! Hub PID: {hub_proc.pid}, Spoke PID: {spoke_proc.pid}")

if __name__ == "__main__":
    main()
