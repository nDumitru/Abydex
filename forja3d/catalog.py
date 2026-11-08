"""Materials and printers catalog (built-in data + user overrides)."""
from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def user_dir() -> Path:
    """Per-user data folder (database, models, custom printers)."""
    env = os.environ.get("FORJA3D_HOME")
    if env:
        p = Path(env)
    elif sys.platform == "win32":
        p = Path(os.environ.get("APPDATA", Path.home())) / "Forja3D"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "forja3d"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load(name: str) -> dict:
    data = json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
    custom = user_dir() / name
    if custom.exists():
        extra = json.loads(custom.read_text(encoding="utf-8"))
        for k, v in extra.items():
            if isinstance(v, dict) and isinstance(data.get(k), dict):
                data[k] = {**data[k], **v}
            else:
                data[k] = v
    data.pop("_info", None)
    return data


@lru_cache(maxsize=None)
def printers() -> dict:
    return _load("printers.json")


@lru_cache(maxsize=None)
def materials() -> dict:
    """Flat dict: material_id -> material (with 'technology' added)."""
    out = {}
    for tech, items in _load("materials.json").items():
        for mid, m in items.items():
            out[mid] = {**m, "id": mid, "technology": tech}
    return out


def get_printer(pid: str) -> dict:
    p = printers().get(pid)
    if p is None:
        raise KeyError(f"Imprimanta necunoscuta: '{pid}'. Vezi lista cu: forja3d printers")
    return {**p, "id": pid}


def get_material(mid: str) -> dict:
    m = materials().get(mid)
    if m is None:
        raise KeyError(f"Material necunoscut: '{mid}'. Vezi lista cu: forja3d materials")
    return m


def materials_for(printer: dict) -> list[dict]:
    return [m for m in materials().values() if m["technology"] == printer["technology"]]
