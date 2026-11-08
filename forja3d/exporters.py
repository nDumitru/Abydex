"""Export recommendations to slicer presets and a readable settings sheet."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .advisor import LABELS, Recommendation


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "piesa"


def _bambu_orca_filament(rec: Recommendation, preset_name: str, inherits: str) -> dict:
    s = rec.settings
    a = lambda v: [str(int(round(v))) if float(v).is_integer() or isinstance(v, int) else str(v)]
    bed, bed1 = s["bed_temp"], s["bed_temp_first"]
    out = {
        "type": "filament",
        "name": preset_name,
        "inherits": inherits,
        "from": "User",
        "instantiation": "true",
        "filament_settings_id": [preset_name],
        "nozzle_temperature": a(s["nozzle_temp"]),
        "nozzle_temperature_initial_layer": a(s["nozzle_temp_first"]),
        "fan_min_speed": a(s["fan_min"]),
        "fan_max_speed": a(s["fan_max"]),
        "overhang_fan_speed": a(s["overhang_fan"]),
        "close_fan_the_first_x_layers": a(s["no_fan_first_layers"]),
        "filament_retraction_length": [f"{s['retraction_mm']:.2f}"],
        "filament_flow_ratio": [f"{s['flow_ratio']:.3f}"],
        "filament_max_volumetric_speed": [f"{s['max_volumetric_speed']:.1f}"],
    }
    for plate in ("hot_plate_temp", "textured_plate_temp", "eng_plate_temp"):
        out[plate] = a(bed)
        out[plate + "_initial_layer"] = a(bed1)
    return out


def _bambu_orca_process(rec: Recommendation, preset_name: str, inherits: str) -> dict:
    s = rec.settings
    out = {
        "type": "process", "name": preset_name, "inherits": inherits, "from": "User",
        "instantiation": "true", "print_settings_id": preset_name,
        "enable_support": "1" if s.get("supports") else "0",
        "brim_type": "outer_only" if s.get("brim_mm", 0) >= 1 else "no_brim",
        "brim_width": str(int(s.get("brim_mm", 0))),
        "draft_shield": "enabled" if s.get("draft_shield") else "disabled",
    }
    if s.get("supports"):
        out["support_type"] = "tree(auto)"
    return out


def bambu_process_base(rec: Recommendation) -> str | None:
    p, s = rec.printer, rec.settings
    if p.get("slicer") != "bambu":
        return None
    lh = s["layer_height"]
    names = {0.08: "Extra Fine", 0.12: "Fine", 0.16: "Optimal", 0.2: "Standard", 0.24: "Draft", 0.28: "Extra Draft"}
    label = names.get(round(lh, 2))
    if not label or s.get("nozzle", 0.4) != 0.4:
        return None
    suffix = p["bambu_suffix"].strip() or "@BBL X1C"
    return f"{lh:.2f}mm {label} {suffix}"


def export_slicer(rec: Recommendation, out_dir: Path, part_name: str) -> list[Path]:
    """Write slicer presets. Returns written files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    p, m = rec.printer, rec.material
    files: list[Path] = []
    if p["technology"] != "fdm":
        return files
    tag = f"Forja3D {m['name']} - {part_name}"
    slicer = p.get("slicer", "orca")
    if slicer == "bambu":
        fam = m["family"]
        if fam in p.get("bambu_generic", []):
            inherits = f"Generic {fam}{p['bambu_suffix']}"
            name = f"{tag}{p['bambu_suffix']}"
            fp = out_dir / f"{_slug(name)}.filament.json"
            fp.write_text(json.dumps(_bambu_orca_filament(rec, name, inherits), indent=2), encoding="utf-8")
            files.append(fp)
            proc_base = bambu_process_base(rec)
            if proc_base:
                pname = f"Forja3D {part_name} {proc_base}"
                pp = out_dir / f"{_slug(pname)}.process.json"
                pp.write_text(json.dumps(_bambu_orca_process(rec, pname, proc_base), indent=2), encoding="utf-8")
                files.append(pp)
    if slicer in ("orca", "bambu"):
        name = f"{tag} (Orca)"
        fp = out_dir / f"{_slug(name)}.orca.filament.json"
        fp.write_text(json.dumps(_bambu_orca_filament(rec, name, f"Generic {m['family']} @System"), indent=2),
                      encoding="utf-8")
        files.append(fp)
    # an .ini is always useful for PrusaSlicer/SuperSlicer users
    files.append(_prusa_ini(rec, out_dir / f"{_slug(tag)}.prusaslicer.ini"))
    return files


def _prusa_ini(rec: Recommendation, path: Path) -> Path:
    s = rec.settings
    lines = [
        "# Forja3D - profil filament PrusaSlicer (File > Import > Import Config)",
        f"filament_type = {rec.material['family']}",
        f"temperature = {s['nozzle_temp']}",
        f"first_layer_temperature = {s['nozzle_temp_first']}",
        f"bed_temperature = {s['bed_temp']}",
        f"first_layer_bed_temperature = {s['bed_temp_first']}",
        f"min_fan_speed = {s['fan_min']}",
        f"max_fan_speed = {s['fan_max']}",
        f"bridge_fan_speed = {s['overhang_fan']}",
        f"disable_fan_first_layers = {s['no_fan_first_layers']}",
        f"cooling = {1 if s['fan_max'] > 0 else 0}",
        f"filament_retract_length = {s['retraction_mm']:.2f}",
        f"extrusion_multiplier = {s['flow_ratio']:.3f}",
        f"filament_max_volumetric_speed = {s['max_volumetric_speed']:.1f}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _fmt(k, v) -> str:
    if isinstance(v, bool):
        return "da" if v else "nu"
    return f"{v}"


def settings_sheet(rec: Recommendation, analysis: dict | None, part_name: str, job_id: int | None) -> str:
    p, m = rec.printer, rec.material
    out = [f"# Forja3D - {part_name}", "",
           f"**Imprimanta:** {p['name']}  ", f"**Material:** {m['name']}  "]
    if job_id:
        out.append(f"**Job:** #{job_id} (dupa print: `forja3d feedback {job_id} ...`)  ")
    if analysis:
        d = analysis["dims_mm"]
        out += ["", "## Piesa", f"- Dimensiuni: {d[0]} x {d[1]} x {d[2]} mm"]
        if analysis.get("volume_cm3") is not None:
            out.append(f"- Volum: {analysis['volume_cm3']} cm³")
        out.append(f"- Suprafata in consola: {analysis['overhang_frac']*100:.1f}%")
        if analysis.get("min_wall_mm"):
            out.append(f"- Perete minim estimat: {analysis['min_wall_mm']} mm")
        out.append(f"- Mesh inchis (watertight): {'da' if analysis['watertight'] else 'nu'}")
    out += ["", "## Setari recomandate", "", "| Setare | Valoare |", "|---|---|"]
    for k, v in rec.settings.items():
        if k == "nozzle":
            continue
        name, unit = LABELS.get(k, (k, ""))
        out.append(f"| {name} | {_fmt(k, v)} {unit if not isinstance(v, bool) else ''} |")
    if rec.warnings:
        out += ["", "## ⚠️ Atentie"] + [f"- {w}" for w in rec.warnings]
    if rec.reasons:
        out += ["", "## De ce"] + [f"- {r}" for r in rec.reasons]
    if m.get("dry"):
        out += ["", f"_Uscare filament: {m['dry'][0]}°C, {m['dry'][1]} ore._"]
    if m.get("notes"):
        out += [f"_{m['notes']}_"]
    return "\n".join(out) + "\n"
