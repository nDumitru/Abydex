"""High level actions shared by the CLI and the web UI."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from . import advisor, exporters, mesh_tools
from .catalog import user_dir
from .memory import Memory


def prepare_job(model_path: str | Path, printer_id: str, material_id: str,
                layer_height: float | None = None, nozzle: float = 0.4,
                size_mm: float | None = None, name: str | None = None,
                out_dir: str | Path | None = None, orient: bool = True,
                memory: Memory | None = None) -> dict:
    """Repair + orient + analyze a model, recommend settings (learning from history),
    export slicer presets, and remember the job so feedback can be attached later."""
    model_path = Path(model_path)
    name = name or model_path.stem
    own_mem = memory is None
    mem = memory or Memory()
    try:
        mesh, rep, analysis = mesh_tools.prepare(model_path, size_mm, orient=orient)
        a = analysis.to_dict()
        rec = advisor.recommend(printer_id, material_id, a, layer_height, nozzle, memory=mem)

        stamp = time.strftime("%Y%m%d-%H%M%S")
        store = user_dir() / "projects" / f"{stamp}_{exporters._slug(name)}"
        store.mkdir(parents=True, exist_ok=True)
        stored_mesh = store / f"{exporters._slug(name)}_pregatit.stl"
        mesh.export(stored_mesh)
        shutil.copy2(model_path, store / f"original{model_path.suffix.lower()}")

        project_id = mem.add_project(name, mesh_tools.file_hash(model_path), model_path, stored_mesh, a)
        job_id = mem.add_job(project_id, printer_id, material_id, rec.settings.get("layer_height"),
                             nozzle, rec.settings)

        out = Path(out_dir) if out_dir else store
        out.mkdir(parents=True, exist_ok=True)
        if out != store:
            shutil.copy2(stored_mesh, out / stored_mesh.name)
        files = [out / stored_mesh.name]
        files += exporters.export_slicer(rec, out, name)
        sheet = out / f"{exporters._slug(name)}_setari.md"
        sheet.write_text(exporters.settings_sheet(rec, a, name, job_id), encoding="utf-8")
        files.append(sheet)
        result = {
            "job_id": job_id, "project_id": project_id, "name": name,
            "repair": rep.__dict__, "analysis": a, "recommendation": rec.to_dict(),
            "files": [str(f) for f in files], "output_dir": str(out),
        }
        (store / "job.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result
    finally:
        if own_mem:
            mem.close()
