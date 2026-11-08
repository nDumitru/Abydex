"""Check GitHub Releases for a newer Abydex version.

Only the public release list is requested (no personal data is sent). Results are cached
for 24h. Disable with the environment variable ABYDEX_NO_UPDATE_CHECK=1.
"""
from __future__ import annotations

import json
import os
import re
import time
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
                    "url": rel.get("html_url") or RELEASES_URL, "notes": (rel.get("body") or "")[:2000]}
            cache.write_text(json.dumps(data), encoding="utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:  # repository has no published release yet
                return {"current": __version__, "update_available": False, "latest": None}
            return {"current": __version__, "update_available": False, "error": str(e)}
        except Exception as e:  # offline, timeout...
            return {"current": __version__, "update_available": False, "error": str(e)}
    return {"current": __version__, "latest": data["latest"], "url": data["url"], "notes": data.get("notes", ""),
            "update_available": is_newer(data["latest"])}
