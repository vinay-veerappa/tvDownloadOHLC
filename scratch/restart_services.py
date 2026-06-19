import subprocess
import time
import sys

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
                        if pid.isdigit():
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
    
    import os
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    
    print("Starting Schwab Hub...")
    hub_proc = subprocess.Popen([sys.executable, "-m", "scripts.streaming.schwab_hub", "--port", "8080"], 
                                env=env,
                                creationflags=subprocess.CREATE_NEW_CONSOLE)
    
    time.sleep(5)
    
    print("Starting Stream Chart...")
    spoke_proc = subprocess.Popen([sys.executable, "-m", "scripts.streaming.stream_chart"], 
                                  env=env,
                                  creationflags=subprocess.CREATE_NEW_CONSOLE)
                                  
    print("Services restarted successfully in new console windows!")

if __name__ == "__main__":
    main()
