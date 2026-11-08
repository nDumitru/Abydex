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


def text_to_3d(text: str, printer_id: str, material_id: str, layer_height: float | None = None,
               nozzle: float = 0.4, name: str | None = None, mode: str = "auto",
               design: dict | None = None, size_mm: float | None = None, use_llm: bool = True,
               out_dir: str | Path | None = None, log=print) -> dict:
    """Text -> design -> mesh -> print-ready job. `design` lets the user override the interpretation
    (e.g. edited template parameters from the UI)."""
    from . import generate, templates, textcad

    mem = Memory()
    try:
        if design is None:
            design = textcad.understand(text, mode, use_llm=use_llm, past=mem.good_text_designs())
        elif "template" in design:
            design = {**design, "params": templates.clean_params(design["template"], design.get("params") or {})}
        stamp = time.strftime("%Y%m%d-%H%M%S")
        work = user_dir() / "uploads"
        work.mkdir(parents=True, exist_ok=True)
        base = exporters._slug(name or text[:40])

        image = None
        if design.get("organic"):
            from . import cloud3d, settings
            cloud = settings.cloud3d_config()
            if cloud and cloud.get("key"):  # the user chose a cloud 3D service
                mesh_path = cloud3d.text_to_3d(text, work / f"{stamp}_{base}.glb", cloud, log=log)
                design = {**design, "source": f"cloud ({cloud['provider']})"}
            else:
                missing = [k for k in ("sdturbo", "triposr") if not generate.is_installed(k)]
                if missing:
                    raise RuntimeError(
                        "Pentru obiecte decorative instaleaza motoarele AI din tab-ul 'Motoare AI' "
                        f"(sau: {' si '.join('abydex engine install ' + m for m in missing)}), "
                        "sau alege un serviciu 3D in cloud (Meshy / Tripo) in 'Setari AI'. "
                        "Piesele tehnice (cutii, suporturi, placi...) merg si fara ele.")
                log("Generez imaginea din descriere...")
                image = generate.text_to_image(text, work / f"{stamp}_{base}.png")
                log("Transform imaginea in model 3D...")
                mesh_path = generate.generate(image, work / f"{stamp}_{base}.obj")
            r = prepare_job(mesh_path, printer_id, material_id, layer_height, nozzle, size_mm or 60.0,
                            name or text[:40], out_dir, orient=True, memory=mem)
        else:
            mesh = textcad.build_design(design)
            if size_mm:
                mesh.apply_scale(size_mm / float(mesh.extents.max()))
            mesh_path = work / f"{stamp}_{base}.stl"
            mesh.export(mesh_path)
            # templates are designed print-ready; free CSG gets auto-oriented
            r = prepare_job(mesh_path, printer_id, material_id, layer_height, nozzle, None,
                            name or text[:40], out_dir, orient="csg" in design, memory=mem)
        if design.get("template") == "box" and design.get("params", {}).get("lid"):
            r["repair"]["notes"] = [n for n in r["repair"]["notes"] if "corpuri" not in n] + [
                "Cutia si capacul sunt doua piese separate, puse una langa alta pe pat."]
        mem.add_text_design(r["job_id"], text, design, design.get("source", ""))
        r["design"] = design
        r["prompt"] = text
        if image:
            img_copy = Path(r["output_dir"]) / f"{base}_imagine.png"
            shutil.copy2(image, img_copy)
            r["files"].append(str(img_copy))
            r["image"] = str(img_copy)
        return r
    finally:
        mem.close()
