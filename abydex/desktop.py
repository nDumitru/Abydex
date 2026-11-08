"""Abydex as a desktop application: its own window, no browser and no console.

Order of attempts:
  1. pywebview (Windows: Edge WebView2, included in Windows 10/11; Linux: GTK/Qt if installed)
  2. Edge / Chrome / Chromium in "app" mode (a window without tabs or address bar)
  3. the default browser
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from . import __version__, logs

ICON = Path(__file__).parent / "webui" / "static" / "abydex.ico"
TITLE = "Abydex"


def _start_server(port: int):
    from .webui.server import make_server
    for p in range(port, port + 20):
        try:
            srv = make_server(p)
            break
        except OSError:
            continue
    else:
        raise RuntimeError(f"Nu gasesc niciun port liber intre {port} si {port + 19}.")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def _windows_app_id() -> None:
    """Own taskbar entry (and icon) instead of being grouped with Python."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Abydex.Desktop")
        except Exception:
            pass


def _windows_set_icon() -> None:
    """pywebview on Windows shows the icon of python.exe: replace it with ours."""
    if sys.platform != "win32" or not ICON.exists():
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, TITLE)
        if not hwnd:
            return
        IMAGE_ICON, LR_LOADFROMFILE, WM_SETICON = 1, 0x10, 0x80
        for size, which in ((16, 0), (32, 1)):
            h = user32.LoadImageW(None, str(ICON), IMAGE_ICON, size, size, LR_LOADFROMFILE)
            if h:
                user32.SendMessageW(hwnd, WM_SETICON, which, h)
    except Exception:
        pass


def _app_mode_browser() -> list[str] | None:
    names = ["msedge", "chrome", "chromium", "chromium-browser", "google-chrome", "brave"]
    if sys.platform == "win32":
        pf = [os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        cands = [Path(p) / sub for p in pf if p for sub in (
            r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe")]
        for c in cands:
            if c.exists():
                return [str(c)]
    for n in names:
        exe = shutil.which(n)
        if exe:
            return [exe]
    return None


def error_box(message: str) -> None:
    """Shows an error even when there is no console (pythonw)."""
    logs.setup().error(message)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "Abydex - eroare", 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def run(port: int = 8765, mode: str = "auto") -> None:
    """mode: auto | window | browser"""
    log = logs.setup()
    _windows_app_id()
    srv, url = _start_server(port)
    log.info("Abydex %s pornit pe %s (mod %s)", __version__, url, mode)

    if mode in ("auto", "window"):
        try:
            import webview  # pywebview
            win = webview.create_window(TITLE, url, width=1440, height=920, min_size=(1000, 640),
                                        background_color="#121417", text_select=True)
            win.events.shown += _windows_set_icon
            webview.start(icon=str(ICON) if ICON.exists() else None, private_mode=False)
            srv.shutdown()  # window closed -> app closes
            return
        except Exception as e:  # no WebView2 / GTK: try the next option
            log.warning("Fereastra nativa nu a pornit (%s), folosesc alta varianta.", e)
            if mode == "window":
                raise

    browser = _app_mode_browser()
    if browser:
        profile = Path(logs.log_path()).parent / "browser-profile"
        proc = subprocess.Popen(browser + [f"--app={url}", f"--user-data-dir={profile}",
                                           "--window-size=1440,920", "--no-first-run"])
        proc.wait()  # the app window was closed
        srv.shutdown()
        return

    import webbrowser
    webbrowser.open(url)
    print(f"Abydex ruleaza la {url}  (Ctrl+C pentru oprire)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
