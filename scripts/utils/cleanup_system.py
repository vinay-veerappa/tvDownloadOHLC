import os
import subprocess
import time
import sys
import io

# Force standard output and error to use utf-8 on Windows to prevent emoji encoding crashes
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)

try:
    import psutil
except ImportError:
    psutil = None


def _kill_pid_tree(pid_str: str):
    """
    Kill the process AND its parent shell window (cmd.exe / powershell.exe)
    using taskkill /F /T /PID or psutil parent tree termination.
    """
    try:
        pid = int(pid_str)
        if psutil:
            try:
                proc = psutil.Process(pid)
                parent = proc.parent()
                # If parent is cmd.exe / powershell.exe (the window shell spawned by START_QUANT_SYSTEM.bat)
                if parent and parent.name().lower() in ("cmd.exe", "powershell.exe", "conhost.exe"):
                    print(f"  ➜ Closing shell window & process tree for PID {pid} (Parent CMD PID {parent.pid})...")
                    subprocess.run(f"taskkill /F /T /PID {parent.pid}", shell=True, capture_output=True)
                    return
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Fallback taskkill /F /T /PID to kill child tree
        print(f"  ➜ Terminating process tree for PID {pid}...")
        subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
    except Exception as e:
        print(f"  ⚠️ Error killing process {pid_str}: {e}")


def kill_by_window_titles(titles: list[str]):
    """Terminate cmd.exe shell windows matching Quant system window titles."""
    for title in titles:
        try:
            cmd = f'taskkill /F /FI "WINDOWTITLE eq {title}*"'
            subprocess.run(cmd, shell=True, capture_output=True)
        except Exception:
            pass


def kill_process_by_port(port: int):
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
            if pid.isdigit():
                print(f"  ➜ Found listener on port {port} (PID: {pid})...")
                _kill_pid_tree(pid)
    except subprocess.CalledProcessError:
        pass  # Port not in use


def kill_python_scripts(script_names: list[str]):
    try:
        if psutil:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline_str = " ".join(proc.info['cmdline'] or [])
                    # Do not kill current cleanup script
                    if "cleanup_system.py" in cmdline_str or proc.info['pid'] == os.getpid():
                        continue
                    for script in script_names:
                        if script in cmdline_str:
                            print(f"  ➜ Found stray target service '{script}' (PID: {proc.info['pid']})...")
                            _kill_pid_tree(str(proc.info['pid']))
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        else:
            cmd = 'wmic process where "name=\'python.exe\'" get commandline,processid'
            output = subprocess.check_output(cmd, shell=True).decode()
            for line in output.strip().split('\n'):
                if "cleanup_system.py" in line:
                    continue
                for script in script_names:
                    if script in line:
                        parts = line.strip().split()
                        if parts and parts[-1].isdigit():
                            _kill_pid_tree(parts[-1])
    except Exception as e:
        print(f"  ⚠️ Error during script cleanup: {e}")


def main():
    print("===================================================")
    print("🧹 SYSTEM SANITY CHECK & CLEANUP")
    print("===================================================")
    
    # 1. Close lingering shell windows by title
    window_titles = [
        "SCHWAB_HUB",
        "QUANT_API",
        "SPOKE_CHART",
        "WEB_DASHBOARD",
        "OPTIONS_GEX",
        "QUANT_SCHEDULER",
        "STRATEGY_ENGINE",
        "KB_BRIDGE",
    ]
    kill_by_window_titles(window_titles)

    # 2. Clear active port listeners & shell windows
    print("Checking active ports (Hub:8080, API:8000, Chart:8001, Web:3000, KB:8900)...")
    for port in [8080, 8000, 8001, 3000, 8900]:
        kill_process_by_port(port)
    
    # 3. Clear stray target services
    print("Checking for stray services...")
    scripts = [
        "schwab_hub", 
        "l2_processor_engine", 
        "stream_chart", 
        "api.main", 
        "run_options_levels",
        "news_calendar_fetcher",
        "strategy_engine",
        "knowledge_ingest.serve",
    ]
    kill_python_scripts(scripts)
    
    # Small grace period for OS to release sockets
    time.sleep(1)
    print("===================================================")
    print("✅ System Cleaned and Ready.")
    print("===================================================\n")


if __name__ == "__main__":
    main()
