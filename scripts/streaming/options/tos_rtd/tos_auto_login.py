"""
tos_auto_login.py
=================
Automates launching Thinkorswim (ToS) desktop application and logging in using
credentials stored securely in credentials_manager.
"""
import os
import sys
import time
import logging
import subprocess
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

log = logging.getLogger("ToSAutoLogin")

# Try win32 imports on Windows
_WIN32_AVAILABLE = False
if sys.platform == "win32":
    try:
        import win32gui
        import win32api
        import win32con
        import win32process
        _WIN32_AVAILABLE = True
    except ImportError:
        pass


def is_tos_running() -> bool:
    """Check if thinkorswim.exe process is currently running."""
    if sys.platform != "win32":
        return False
    try:
        res = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq thinkorswim.exe", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        return "thinkorswim.exe" in res.stdout.lower()
    except Exception:
        return False


def find_tos_executable() -> Path | None:
    """Locate thinkorswim.exe on standard Windows installation paths."""
    from scripts.streaming.credentials_manager import get_secret
    
    # 1. Custom path override from config/secrets
    custom_path = get_secret("tos_path")
    if custom_path and Path(custom_path).exists():
        return Path(custom_path)

    # 2. Standard candidate paths
    user_appdata = os.getenv("LOCALAPPDATA", "")
    candidates = [
        Path(user_appdata) / "thinkorswim" / "thinkorswim.exe",
        Path("C:/Program Files/thinkorswim/thinkorswim.exe"),
        Path("C:/Program Files (x86)/thinkorswim/thinkorswim.exe"),
        Path("C:/thinkorswim/thinkorswim.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p

    return None


def bring_window_to_front(hwnd):
    """Safely restore and bring a window to the foreground."""
    if not _WIN32_AVAILABLE:
        return
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.BringWindowToTop(hwnd)
    except Exception:
        pass
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        log.debug("SetForegroundWindow soft warning: %s", e)


import ctypes
from ctypes import wintypes

INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]
    _anonymous_ = ("_input",)
    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]


def type_unicode_text(text: str):
    """Types text directly using Windows SendInput KEYEVENTF_UNICODE (native Chromium/Java support)."""
    if sys.platform != "win32":
        return
    for char in text:
        code_point = ord(char)
        # Key down
        inp_down = INPUT(type=INPUT_KEYBOARD)
        inp_down.ki.wScan = code_point
        inp_down.ki.dwFlags = KEYEVENTF_UNICODE
        
        # Key up
        inp_up = INPUT(type=INPUT_KEYBOARD)
        inp_up.ki.wScan = code_point
        inp_up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
        time.sleep(0.02)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
        time.sleep(0.02)


try:
    import win32clipboard
except ImportError:
    win32clipboard = None


def set_clipboard_text(text: str):
    """Set text onto Windows Clipboard."""
    if not win32clipboard:
        return
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except Exception as e:
        log.debug("Clipboard set error: %s", e)


def send_keys_to_window(hwnd, text: str):
    """Send text to a window accurately using SendInput Unicode + Clipboard paste fallback."""
    if not _WIN32_AVAILABLE:
        return
    bring_window_to_front(hwnd)
    time.sleep(0.3)
    
    # 1. Type using native Windows SendInput KEYEVENTF_UNICODE (Chromium/Java web-view standard)
    try:
        type_unicode_text(text)
        time.sleep(0.2)
    except Exception as e:
        log.warning("SendInput unicode typing error: %s", e)

    # 2. Also execute Ctrl+V with hardware scan codes as backup
    if win32clipboard:
        try:
            set_clipboard_text(text)
            time.sleep(0.1)
            ctrl_vk = win32con.VK_CONTROL
            v_vk = 0x56  # 'V'
            ctrl_scan = win32api.MapVirtualKey(ctrl_vk, 0)
            v_scan = win32api.MapVirtualKey(v_vk, 0)
            
            win32api.keybd_event(ctrl_vk, ctrl_scan, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(v_vk, v_scan, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(v_vk, v_scan, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)
            win32api.keybd_event(ctrl_vk, ctrl_scan, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.2)
            set_clipboard_text("")
        except Exception as e:
            log.debug("Ctrl+V fallback warning: %s", e)


def press_key(hwnd, vk_code: int):
    """Press a single key (e.g., Return, Tab)."""
    if not _WIN32_AVAILABLE:
        return
    bring_window_to_front(hwnd)
    time.sleep(0.1)
    win32api.keybd_event(vk_code, 0, 0, 0)
    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)


def click_window_relative(hwnd, x_pct: float = 0.5, y_pct: float = 0.49):
    """Click at a relative position inside a window."""
    if not _WIN32_AVAILABLE:
        return
    bring_window_to_front(hwnd)
    time.sleep(0.2)
    try:
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        
        target_x = left + int(width * x_pct)
        target_y = top + int(height * y_pct)
        
        win32api.SetCursorPos((target_x, target_y))
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, target_x, target_y, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, target_x, target_y, 0, 0)
        time.sleep(0.2)
    except Exception as e:
        log.debug("click_window_relative warning: %s", e)


def is_window_in_update_phase(hwnd) -> bool:
    """Check if Thinkorswim launcher window is currently installing/checking for updates."""
    if not _WIN32_AVAILABLE:
        return False
    try:
        title = win32gui.GetWindowText(hwnd).lower()
        if any(kw in title for kw in ["installing", "updating", "checking", "downloading", "patch"]):
            return True
        
        # Check child window text if any
        child_texts = []
        def enum_child_cb(child_hwnd, _):
            txt = win32gui.GetWindowText(child_hwnd).lower()
            if txt:
                child_texts.append(txt)
        win32gui.EnumChildWindows(hwnd, enum_child_cb, None)
        all_text = " ".join(child_texts)
        if any(kw in all_text for kw in ["installing", "updating", "checking", "downloading", "patch"]):
            return True
    except Exception:
        pass
    return False


def wait_for_login_form_ready(hwnd, timeout_seconds: int = 90) -> bool:
    """
    Waits for Thinkorswim to finish installing updates and for the login form to settle.
    """
    log.info("Waiting for Thinkorswim to finish updates and render the login form (timeout: %ds)...", timeout_seconds)
    start_time = time.time()
    last_rect = None
    stable_count = 0

    while time.time() - start_time < timeout_seconds:
        if is_window_in_update_phase(hwnd):
            log.info("⏳ Thinkorswim is installing/checking updates... waiting...")
            time.sleep(2.0)
            stable_count = 0
            continue

        # Check window rect stability (window size/position doesn't change)
        try:
            rect = win32gui.GetWindowRect(hwnd)
            if rect == last_rect and rect[2] - rect[0] > 200: # Valid non-zero width
                stable_count += 1
                if stable_count >= 4: # Stable for ~4 seconds
                    log.info("✅ Thinkorswim updates complete. Waiting 7 seconds for login UI to fully render...")
                    time.sleep(7.0) # Additional 7s grace for JavaFX / Chromium web view to render Continue button
                    return True
            else:
                last_rect = rect
                stable_count = 0
        except Exception:
            pass

        time.sleep(1.0)

    log.warning("Timed out waiting for ToS login window to settle.")
    return False


try:
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = False
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False


def automate_tos_login(username: str | None = None, password: str | None = None, timeout_seconds: int = 120) -> bool:
    """
    Finds the Thinkorswim login window, waits for updates to finish, and enters credentials automatically.
    """
    if not _WIN32_AVAILABLE:
        log.warning("Win32 API unavailable — cannot automate GUI login.")
        return False

    if not username or not password:
        from scripts.streaming.credentials_manager import get_tos_credentials
        u, p = get_tos_credentials()
        username = username or u
        password = password or p

    if not username or not password:
        log.warning("No Thinkorswim credentials found in credentials_manager / secrets.json.")
        return False

    log.info("Monitoring for Thinkorswim launcher window (timeout: %ds)...", timeout_seconds)
    start_time = time.time()
    login_hwnd = None

    def enum_windows_callback(hwnd, extra):
        nonlocal login_hwnd
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if "thinkorswim" in title or "log in" in title or "welcome" in title:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                login_hwnd = hwnd

    while time.time() - start_time < timeout_seconds:
        win32gui.EnumWindows(enum_windows_callback, None)
        if login_hwnd:
            log.info("Detected Thinkorswim window handle: 0x%X (%s)", login_hwnd, win32gui.GetWindowText(login_hwnd))
            break
        time.sleep(1.0)

    if not login_hwnd:
        log.warning("Thinkorswim launcher window not found within timeout.")
        return False

    # Wait for update installation phase to complete and form to render
    if not wait_for_login_form_ready(login_hwnd, timeout_seconds=timeout_seconds):
        log.warning("Proceeding with login attempt despite form stability timeout...")

    try:
        # Focus window safely
        bring_window_to_front(login_hwnd)
        time.sleep(1.0)

        log.info("Processing Step 1: Submitting 'Continue' button on Welcome screen...")
        # Step 1: Click Continue / Press Enter on pre-filled Welcome screen
        if _PYAUTOGUI_AVAILABLE:
            pyautogui.press('enter')
        else:
            click_window_relative(login_hwnd, x_pct=0.5, y_pct=0.49)
            press_key(login_hwnd, win32con.VK_RETURN)
            
        time.sleep(3.5) # Wait for Password screen transition animation

        log.info("Processing Step 2: Pasting password into auto-focused field...")
        # Step 2: On Step 2, the Password field is auto-focused by default.
        # Use pyautogui + pyperclip to paste into focused input without off-target clicking
        if _PYAUTOGUI_AVAILABLE:
            pyperclip.copy(password)
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.4)
            pyautogui.press('enter')
            time.sleep(0.1)
            pyperclip.copy("") # Clear clipboard for security
        else:
            send_keys_to_window(login_hwnd, password)
            time.sleep(0.5)
            press_key(login_hwnd, win32con.VK_RETURN)
        
        log.info("✅ Thinkorswim login credentials submitted successfully.")
        return True
    except Exception as e:
        log.error("Failed during ToS GUI login automation: %s", e)
        return False


def is_tos_gui_visible() -> bool:
    """Check if Thinkorswim desktop GUI window is currently open and visible."""
    if sys.platform != "win32" or not _WIN32_AVAILABLE:
        return is_tos_running()

    found = False
    def enum_windows_cb(hwnd, extra):
        nonlocal found
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if "thinkorswim" in title or "log in" in title:
                found = True

    try:
        win32gui.EnumWindows(enum_windows_cb, None)
    except Exception:
        pass
    return found


def launch_and_login_tos() -> bool:
    """
    Main entry point: Checks if ToS is running, launches it if missing, and automates login.
    """
    if is_tos_gui_visible():
        log.info("Thinkorswim GUI window is already active and visible.")
        return True

    exe_path = find_tos_executable()
    if not exe_path:
        log.error("Thinkorswim executable (thinkorswim.exe) not found on standard paths.")
        return False

    log.info("🚀 Launching Thinkorswim interactively from: %s", exe_path)
    try:
        if sys.platform == "win32":
            # Use PowerShell Start-Process to force interactive user desktop session execution
            ps_cmd = f"Start-Process '{exe_path}'"
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd])
        else:
            subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
    except Exception as e:
        log.error("Failed to launch Thinkorswim executable: %s", e)
        return False

    # Automate login
    return automate_tos_login()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Thinkorswim Auto-Launch and GUI Auto-Login...")
    res = launch_and_login_tos()
    print(f"ToS Launch & Login Result: {res}")
