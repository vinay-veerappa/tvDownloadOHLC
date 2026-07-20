"""
windows_notifier.py
===================
Native Windows Desktop Toast Notification Engine, Popup Dialog Manager, and System Audio Alerts.

Provides desktop toast popups, top-most modal dialog boxes, and audio chimes for:
  1. Schwab OAuth Token Expiration / Re-Auth Prompts
  2. Thinkorswim Auto-Launch & Auto-Login Events
  3. Gap Fill & Pipeline Status Updates
"""
import sys
import os
import logging
import subprocess
import winsound

log = logging.getLogger("WindowsNotifier")

# Windows MessageBox flags
MB_OK = 0x0
MB_ICONINFORMATION = 0x40
MB_ICONWARNING = 0x30
MB_ICONERROR = 0x10
MB_TOPMOST = 0x00040000  # Ensures window pops up on top of ALL desktop applications


import threading

def show_popup_dialog(title: str, message: str, level: str = "info"):
    """
    Pops up a native, top-most Windows modal dialog window in a non-blocking background thread.
    Guaranteed to be visible regardless of Windows Action Center / Focus Assist settings without hanging.
    """
    if sys.platform != "win32":
        log.info("[Popup Dialog] %s: %s", title, message)
        return

    def _display():
        icon = MB_ICONINFORMATION
        if level == "warning":
            icon = MB_ICONWARNING
        elif level == "error":
            icon = MB_ICONERROR

        try:
            import ctypes
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass

            ctypes.windll.user32.MessageBoxW(0, message, title, icon | MB_TOPMOST | MB_OK)
        except Exception as e:
            log.warning("Failed to display Windows popup dialog: %s", e)

    threading.Thread(target=_display, daemon=True).start()


def notify_windows_toast(title: str, message: str, sound: bool = True):
    """
    Sends a native Windows Toast notification to the desktop using WinRT/PowerShell.
    """
    if sys.platform != "win32":
        log.info("[Notification] %s: %s", title, message)
        return

    if sound:
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    # Escape quotes for PowerShell
    safe_title = title.replace('"', '`"').replace("'", "''")
    safe_message = message.replace('"', '`"').replace("'", "''")

    ps_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

    $template = @"
    <toast>
        <visual>
            <binding template="ToastGeneric">
                <text>{safe_title}</text>
                <text>{safe_message}</text>
            </binding>
        </visual>
    </toast>
"@

    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("tvDownloadOHLC Pipeline").Show($toast)
    """

    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps_script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception as e:
        log.warning("Failed to send Windows Toast notification: %s", e)


def notify_tos_launching():
    notify_windows_toast("🟡 Thinkorswim Auto-Launch", "Launching Thinkorswim desktop application...")


def notify_tos_connected():
    notify_windows_toast("🟢 Thinkorswim Connected", "Thinkorswim RTD streaming is now ACTIVE.")


def notify_schwab_token_expired():
    show_popup_dialog(
        "🔴 Schwab Auth Required",
        "Schwab API token has expired.\n\nClick OK to launch browser re-authentication.",
        level="warning"
    )


def notify_schwab_token_refreshed():
    show_popup_dialog(
        "🟢 Schwab Auth Successful",
        "Schwab API token has been refreshed successfully!\n\nAll data pipelines are active.",
        level="info"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Windows Popup Dialog & Notification...")
    show_popup_dialog("🚀 Pipeline System Test", "Windows top-most popup dialog window is working!")
