"""Materials and printers catalog (built-in data + user overrides)."""
from __future__ import annotations

import json
import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def _default_dir(app: str) -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / app
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / app.lower()


def user_dir() -> Path:
    """Per-user data folder (database, models, custom printers).

    Data of versions before v0.3.0 (see legacy.py) is copied over once, so the learned memory,
    custom profiles and AI engines are kept."""
    from . import legacy
    env = os.environ.get("ABYDEX_HOME") or os.environ.get(legacy.OLD_HOME_ENV)
    p = Path(env) if env else _default_dir("Abydex")
    if not env and not p.exists():
        old = _default_dir(legacy.OLD_APP)
        if old.is_dir():
            shutil.copytree(old, p, dirs_exist_ok=True)
            (p / "DATE_COPIATE_DIN_VERSIUNEA_VECHE.txt").write_text(
                f"Datele au fost copiate din {old} la prima pornire a Abydex.\n"
                "Dupa ce verifici ca totul e in regula, poti sterge folderul vechi.\n", encoding="utf-8")
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
        raise KeyError(f"Imprimanta necunoscuta: '{pid}'. Vezi lista cu: abydex printers")
    return {**p, "id": pid}


def get_material(mid: str) -> dict:
    m = materials().get(mid)
    if m is None:
        raise KeyError(f"Material necunoscut: '{mid}'. Vezi lista cu: abydex materials")
    return m


def materials_for(printer: dict) -> list[dict]:
    return [m for m in materials().values() if m["technology"] == printer["technology"]]
