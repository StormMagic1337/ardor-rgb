"""Windows integration: global hotkeys, lock-screen / fullscreen detection, autostart."""
import ctypes, sys, threading, winreg
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN, VK_END, VK_HOME = 0x25, 0x26, 0x27, 0x28, 0x23, 0x24
WM_HOTKEY = 0x0312

HOTKEYS = {                     # id -> (vk, action)
    1: (VK_RIGHT, "next"),
    2: (VK_LEFT, "prev"),
    3: (VK_UP, "brighter"),
    4: (VK_DOWN, "dimmer"),
    5: (VK_END, "toggle_off"),
    6: (VK_HOME, "toggle_calm"),
}


def start_hotkeys(callback):
    """Registers Ctrl+Alt+<key> hotkeys on a private thread; callback(action) runs on that thread.
    Returns the list of actions that could not be registered (taken by another program)."""
    failed = []
    ready = threading.Event()

    def loop():
        for hid, (vk, action) in HOTKEYS.items():
            if not user32.RegisterHotKey(None, hid, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, vk):
                failed.append(action)
        ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in HOTKEYS:
                callback(HOTKEYS[msg.wParam][1])

    threading.Thread(target=loop, name="ardor-hotkeys", daemon=True).start()
    ready.wait(2)
    return failed


def is_locked():
    """True while the lock screen (or UAC secure desktop) is shown."""
    h = user32.OpenInputDesktop(0, False, 0x0100)      # DESKTOP_SWITCHDESKTOP
    if not h:
        return True
    try:
        return not user32.SwitchDesktop(h)
    finally:
        user32.CloseDesktop(h)


def fullscreen_app():
    """True when a fullscreen app (game, exclusive D3D, borderless fullscreen, video) is in front."""
    state = ctypes.c_int(0)
    if shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
        return False
    return state.value in (2, 3)          # QUNS_BUSY (fullscreen app), QUNS_RUNNING_D3D_FULL_SCREEN


# --- autostart (HKCU Run key) ---------------------------------------------------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "ArdorRGB"


def autostart_command():
    if getattr(sys, "frozen", False):                  # PyInstaller build: the exe itself
        return f'"{sys.executable}" --tray'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    app = Path(__file__).resolve().parent.parent / "app.py"
    return f'"{pyw}" "{app}" --tray'


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except OSError:
                pass
