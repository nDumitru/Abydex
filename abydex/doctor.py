"""`abydex doctor`: checks everything the app needs and prints a report to paste in a GitHub issue."""
from __future__ import annotations

import importlib
import platform
import socket
import sys
import tempfile

from . import __version__


def _check(name, fn):
    try:
        info = fn()
        return True, f"OK  {name}" + (f": {info}" if info else "")
    except Exception as e:  # noqa: BLE001 - report everything
        return False, f"EROARE  {name}: {type(e).__name__}: {e}"


def run() -> tuple[bool, list[str]]:
    lines = [f"Abydex {__version__} | Python {sys.version.split()[0]} | {platform.platform()}",
             f"Executabil: {sys.executable}"]
    ok_all = True

    def mod(m):
        return lambda: getattr(importlib.import_module(m), "__version__", "")

    checks = [(m, mod(m)) for m in ("numpy", "scipy", "trimesh", "networkx", "lxml.etree", "manifold3d", "rtree", "anthropic")]

    def data_dir():
        from .catalog import user_dir
        d = user_dir()
        with tempfile.NamedTemporaryFile(dir=d):
            pass
        return str(d)

    def database():
        from .memory import Memory
        m = Memory()
        v = m.db.execute("PRAGMA user_version").fetchone()[0]
        m.close()
        return f"schema {v}"

    def mesh_pipeline():
        from . import csg, mesh_tools, templates
        m = csg.build(templates.spec_for("box", {}))
        mesh_tools.repair(m)
        return f"{len(m.faces)} triunghiuri"

    def ray():  # uses rtree (needs the Microsoft C++ runtime on Windows)
        import trimesh
        b = trimesh.creation.box([10, 10, 10])
        return f"perete {mesh_tools_wall(b)} mm"

    def mesh_tools_wall(b):
        from .mesh_tools import min_wall_thickness
        return min_wall_thickness(b)

    def port():
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", 8765))
            return "8765 liber"
        finally:
            s.close()

    def engines():
        from . import generate
        return ", ".join(f"{k}: {'instalat' if generate.is_installed(k) else 'nu'}" for k in generate.ENGINES)

    def llm():  # no request is sent to paid APIs here
        from . import llm as llm_mod, settings
        cfg = settings.llm_config()
        ready = llm_mod.available(cfg)
        cloud = settings.cloud3d_config()
        extra = f"; 3D cloud: {cloud['provider']} ({'cheie setata' if cloud.get('key') else 'fara cheie'})" if cloud else ""
        return (f"{cfg['label']} / {cfg['model']}: "
                + ("pregatit" if ready else ("nu ruleaza (optional)" if cfg["kind"] == "ollama" else "fara cheie API"))
                + extra)

    checks += [("folder date", data_dir), ("baza de date", database), ("geometrie", mesh_pipeline),
               ("analiza pereti (rtree)", ray), ("port interfata", port), ("motoare AI", engines),
               ("AI text", llm)]
    for name, fn in checks:
        ok, line = _check(name, fn)
        if not ok and name not in ("port interfata",):
            ok_all = False
        lines.append(line)
    return ok_all, lines
