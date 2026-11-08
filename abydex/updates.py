"""Check GitHub Releases for a newer Abydex version, and install it from inside the app.

Only the public release list is requested (no personal data is sent). Results are cached
for 24h. Disable the check with the environment variable ABYDEX_NO_UPDATE_CHECK=1.

Installing: the new installer (Windows) or wheel (Linux) is downloaded from the GitHub release,
its SHA-256 is checked against SHA256SUMS.txt from the same release, then it is applied.
Nothing is installed if the checksum is missing or does not match.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
import urllib.error
import urllib.request

from . import __version__
from .catalog import user_dir

REPO = "nDumitru/abydex"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"
CACHE_SECONDS = 24 * 3600


def parse_version(v: str) -> tuple:
    """'v1.2.3' / '1.2.3-beta.1' -> comparable tuple. Pre-releases sort before the final version."""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)(?:[-.]?([0-9A-Za-z.]+))?", v.strip())
    if not m:
        return (0, 0, 0, 0, "")
    major, minor, patch, pre = m.groups()
    return (int(major), int(minor), int(patch), 0 if pre else 1, pre or "")


def is_newer(latest: str, current: str = __version__) -> bool:
    return parse_version(latest) > parse_version(current)


def check(force: bool = False, timeout: float = 4.0) -> dict:
    """Returns {"current", "latest", "update_available", "url", "notes"} or {"disabled": True}."""
    if os.environ.get("ABYDEX_NO_UPDATE_CHECK"):
        return {"current": __version__, "disabled": True, "update_available": False}
    cache = user_dir() / "update_check.json"
    data = None
    if not force and cache.exists():
        try:
            c = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - c.get("checked", 0) < CACHE_SECONDS:
                data = c
        except Exception:
            data = None
    if data is None:
        try:
            req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": f"Abydex/{__version__}"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                rel = json.load(r)
            data = {"checked": time.time(), "latest": rel.get("tag_name", ""),
                    "url": rel.get("html_url") or RELEASES_URL, "notes": (rel.get("body") or "")[:2000],
                    "assets": {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])
                               if a.get("name") and a.get("browser_download_url")}}
            cache.write_text(json.dumps(data), encoding="utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:  # repository has no published release yet
                return {"current": __version__, "update_available": False, "latest": None}
            return {"current": __version__, "update_available": False, "error": str(e)}
        except Exception as e:  # offline, timeout...
            return {"current": __version__, "update_available": False, "error": str(e)}
    kind = install_kind()
    newer = is_newer(data["latest"])
    can = bool(newer and kind != "source" and _asset_name(kind, data["latest"]) in data.get("assets", {})
               and SUMS in data.get("assets", {}))
    return {"current": __version__, "latest": data["latest"], "url": data["url"], "notes": data.get("notes", ""),
            "update_available": newer, "can_install": can, "install_kind": kind}


# ----------------------------------------------------------------------------- install
SUMS = "SHA256SUMS.txt"
ALLOWED_HOSTS = ("https://github.com/", "https://objects.githubusercontent.com/",
                 "https://release-assets.githubusercontent.com/")
STATE: dict = {"stage": "idle", "progress": 0, "message": ""}
_lock = threading.Lock()


def install_kind() -> str:
    """windows   - installed with Abydex-Setup.exe (embedded Python in the app folder)
       linux     - installed with packaging/linux/install.sh (own virtualenv)
       source    - developer checkout / pip: updates are done by the user"""
    exe = Path(sys.executable).resolve()
    if sys.platform == "win32" and exe.parent.name.lower() == "python" and (exe.parent.parent / "Abydex.cmd").exists():
        return "windows"
    if sys.platform.startswith("linux"):
        data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "abydex" / "app"
        if Path(sys.prefix).resolve() == data.resolve():
            return "linux"
    return "source"


def _asset_name(kind: str, tag: str) -> str:
    v = tag.lstrip("v")
    return {"windows": f"Abydex-Setup-{v}.exe", "linux": f"abydex-{v}-py3-none-any.whl"}.get(kind, "")


def _fetch(url: str, dest: Path | None = None, progress=None) -> bytes | Path:
    if not url.startswith(ALLOWED_HOSTS):
        raise RuntimeError(f"Adresa de descarcare nu e de pe GitHub: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": f"Abydex/{__version__}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        if dest is None:
            return r.read()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(int(done * 100 / total))
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_sum(sums_text: str, name: str) -> str | None:
    for line in sums_text.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            return parts[0].lower()
    return None


def download_update(info: dict, progress=None) -> Path:
    """Downloads and verifies the update for this install. Returns the verified file."""
    kind = install_kind()
    name = _asset_name(kind, info["latest"])
    assets = info.get("assets") or {}
    if kind == "source":
        raise RuntimeError("Instalarea din sursa se actualizeaza cu git pull / pip.")
    if name not in assets or SUMS not in assets:
        raise RuntimeError("Release-ul nu are fisierul de update sau suma de control. Descarca-l manual.")
    sums = _fetch(assets[SUMS]).decode("utf-8", "replace")
    want = expected_sum(sums, name)
    if not want:
        raise RuntimeError(f"{name} lipseste din {SUMS}.")
    folder = Path(tempfile.mkdtemp(prefix="abydex-update-"))
    path = _fetch(assets[name], folder / name, progress)
    got = sha256(path)
    if got != want:
        path.unlink(missing_ok=True)
        raise RuntimeError("Fisierul descarcat nu corespunde sumei de control. Update anulat.")
    return path


def apply_update(path: Path, exit_app=None) -> None:
    """Starts the installer (Windows) or pip (Linux), then restarts the app."""
    kind = install_kind()
    exit_app = exit_app or (lambda: os._exit(0))
    if kind == "windows":
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
                          "/AUTOSTART=1"], creationflags=flags, close_fds=True)
        # leave so the installer can replace the files; it starts the new version when done
        threading.Timer(1.5, exit_app).start()
    elif kind == "linux":
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check",
                        str(path)], check=True)
        threading.Timer(1.0, lambda: os.execv(sys.executable, [sys.executable, "-m", "abydex", "app"])).start()
    else:
        raise RuntimeError("Instalarea din sursa se actualizeaza cu git pull / pip.")


def start_install(info: dict, exit_app=None) -> dict:
    """Background download + verify + apply. Progress is in STATE."""
    with _lock:
        if STATE["stage"] in ("downloading", "installing"):
            return dict(STATE)
        STATE.update(stage="downloading", progress=0, message=f"Descarc {info['latest']}...")

    def work():
        try:
            path = download_update(info, progress=lambda p: STATE.update(progress=p))
            STATE.update(stage="installing", progress=100,
                         message="Instalez... aplicatia se inchide si porneste din nou singura.")
            apply_update(path, exit_app)
        except Exception as e:
            STATE.update(stage="error", message=str(e))

    threading.Thread(target=work, daemon=True).start()
    return dict(STATE)
