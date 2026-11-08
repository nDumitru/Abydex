"""Print-settings advisor.

1. Starts from universal material values.
2. Adapts them to the printer (limits, enclosure, extruder) and to the part geometry.
3. Learns from past prints of similar parts on the same printer + material:
   successful prints pull the settings toward what worked, failed prints are
   first corrected (rules per issue) and then used as evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import catalog
from .memory import Memory

# ------------------------------------------------------------------ issues
ISSUES = {
    "fdm": {
        "stringing":       ("Fire / stringing",                 {"nozzle_temp": -5, "retraction_mm": "*1.15"}),
        "warping":         ("Colturi ridicate / warping",       {"bed_temp": +5, "fan_max": -10, "fan_min": -10, "brim_mm": +3}),
        "adhesion":        ("S-a dezlipit de pe placa",         {"bed_temp": +5, "brim_mm": +3}),
        "layer_split":     ("Crapaturi intre straturi",         {"nozzle_temp": +5, "fan_max": -15, "fan_min": -10}),
        "sagging":         ("Consolele au cazut / s-au curbat", {"overhang_fan": +15, "fan_max": +10, "nozzle_temp": -5}),
        "under_extrusion": ("Sub-extrudare / goluri",           {"flow_ratio": +0.02, "nozzle_temp": +5, "max_volumetric_speed": "*0.85"}),
        "over_extrusion":  ("Supra-extrudare / bavuri",         {"flow_ratio": -0.02}),
        "elephant_foot":   ("Picior de elefant (baza lata)",    {"bed_temp": -5}),
        "rough_top":       ("Suprafata de sus urata",           {"fan_max": +10}),
        "clog":            ("Duza s-a infundat",                {"nozzle_temp": -5, "max_volumetric_speed": "*0.85"}),
    },
    "resin": {
        "no_adhesion":     ("Nu s-a lipit de platforma",        {"bottom_exposure_s": "*1.2", "bottom_layers": +1}),
        "layer_split":     ("Straturi separate / delaminare",   {"exposure_s": "*1.1", "lift_speed_mm_min": "*0.8"}),
        "supports_failed": ("Suporturile au cedat",             {"exposure_s": "*1.08", "lift_speed_mm_min": "*0.85"}),
        "overcured":       ("Detalii pierdute / prea expus",    {"exposure_s": "*0.9"}),
        "stuck_fep":       ("Lipit de folia FEP",               {"exposure_s": "*0.92", "lift_speed_mm_min": "*0.8"}),
    },
    "sls": {},
}

LIMITS = {
    "fan_min": (0, 100), "fan_max": (0, 100), "overhang_fan": (0, 100),
    "retraction_mm": (0.1, 8.0), "flow_ratio": (0.85, 1.10), "max_volumetric_speed": (1.0, 40.0),
    "brim_mm": (0.0, 15.0), "exposure_s": (0.5, 20.0), "bottom_exposure_s": (5.0, 120.0),
    "bottom_layers": (2, 12), "lift_speed_mm_min": (10, 300),
}
ROUND = {"flow_ratio": 3, "retraction_mm": 2, "max_volumetric_speed": 1, "exposure_s": 2,
         "bottom_exposure_s": 1}
CHANGE_THRESHOLD = {"nozzle_temp": 1, "bed_temp": 1, "fan_min": 2, "fan_max": 2, "overhang_fan": 2,
                    "retraction_mm": 0.05, "flow_ratio": 0.005, "max_volumetric_speed": 0.3,
                    "brim_mm": 1, "exposure_s": 0.05, "bottom_exposure_s": 0.5, "bottom_layers": 1,
                    "lift_speed_mm_min": 2}
LEARNABLE = {
    "fdm": ["nozzle_temp", "bed_temp", "fan_min", "fan_max", "overhang_fan", "retraction_mm",
            "flow_ratio", "max_volumetric_speed", "brim_mm"],
    "resin": ["exposure_s", "bottom_exposure_s", "bottom_layers", "lift_speed_mm_min"],
    "sls": [],
}
LABELS = {
    "nozzle_temp": ("Temperatura duza", "°C"), "nozzle_temp_first": ("Temp. duza strat 1", "°C"),
    "bed_temp": ("Temperatura pat", "°C"), "bed_temp_first": ("Temp. pat strat 1", "°C"),
    "fan_min": ("Ventilator minim", "%"), "fan_max": ("Ventilator maxim", "%"),
    "overhang_fan": ("Ventilator la console", "%"), "no_fan_first_layers": ("Fara ventilator primele", "straturi"),
    "retraction_mm": ("Retractie", "mm"), "flow_ratio": ("Flow ratio", ""),
    "max_volumetric_speed": ("Debit volumetric maxim", "mm³/s"), "brim_mm": ("Brim", "mm"),
    "supports": ("Suporturi", ""), "draft_shield": ("Draft shield (paravan)", ""),
    "layer_height": ("Inaltime strat", "mm"),
    "exposure_s": ("Expunere", "s"), "bottom_exposure_s": ("Expunere straturi baza", "s"),
    "bottom_layers": ("Straturi de baza", ""), "lift_mm": ("Ridicare", "mm"),
    "lift_speed_mm_min": ("Viteza ridicare", "mm/min"), "retract_speed_mm_min": ("Viteza coborare", "mm/min"),
    "hollow": ("Golire (hollow)", ""), "drain_hole_mm": ("Gauri de drenaj", "mm"),
}


@dataclass
class Recommendation:
    printer: dict
    material: dict
    settings: dict
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    learned_from: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"printer": self.printer["id"], "material": self.material["id"],
                "settings": self.settings, "reasons": self.reasons, "warnings": self.warnings,
                "learned_from": self.learned_from}


# ------------------------------------------------------------------ helpers
def _apply(settings: dict, deltas: dict) -> dict:
    s = dict(settings)
    for k, d in deltas.items():
        if k not in s or isinstance(s[k], bool):
            continue
        if isinstance(d, str) and d.startswith("*"):
            s[k] = s[k] * float(d[1:])
        else:
            s[k] = s[k] + d
    return s


def apply_issue_corrections(tech: str, settings: dict, issues: list[str]) -> dict:
    s = dict(settings)
    for iss in issues:
        if iss in ISSUES.get(tech, {}):
            s = _apply(s, ISSUES[tech][iss][1])
    return s


def _clamp(s: dict, material: dict, printer: dict) -> dict:
    s = dict(s)
    if "nozzle_temp" in s:
        lo, _, hi = material["nozzle_temp"]
        hi = min(hi, printer.get("nozzle_max", hi))
        s["nozzle_temp"] = max(lo, min(hi, s["nozzle_temp"]))
    if "bed_temp" in s:
        lo, _, hi = material["bed_temp"]
        hi = min(hi, printer.get("bed_max", hi))
        s["bed_temp"] = max(min(lo, hi), min(hi, s["bed_temp"]))
    for k, (lo, hi) in LIMITS.items():
        if k in s and not isinstance(s[k], bool):
            s[k] = max(lo, min(hi, s[k]))
    for k, v in list(s.items()):
        if isinstance(v, float) and not isinstance(v, bool):
            s[k] = round(v, ROUND[k]) if k in ROUND else (v if k in ("layer_height", "nozzle") else round(v))
    if "fan_min" in s and "fan_max" in s:
        s["fan_min"] = min(s["fan_min"], s["fan_max"])
    return s


# ------------------------------------------------------------------ base values
def _base_fdm(p: dict, m: dict, layer: float, nozzle: float, a: dict | None, r: Recommendation) -> dict:
    s = {
        "layer_height": layer, "nozzle": nozzle,
        "nozzle_temp": m["nozzle_temp"][1], "bed_temp": m["bed_temp"][1],
        "fan_min": m["fan_min"], "fan_max": m["fan_max"], "overhang_fan": m["overhang_fan"],
        "no_fan_first_layers": m["no_fan_first_layers"],
        "retraction_mm": p.get("retraction_mm", 0.8) * m["retraction_factor"],
        "flow_ratio": m["flow_ratio"], "max_volumetric_speed": m["max_volumetric_speed"],
        "brim_mm": 0.0, "supports": False, "draft_shield": False,
    }
    if p.get("bed_max", 999) < m["bed_temp"][1]:
        r.warnings.append(f"Patul imprimantei ajunge doar la {p['bed_max']}°C, iar {m['name']} "
                          f"prefera {m['bed_temp'][1]}°C. Folosesc maximul imprimantei.")
    if p.get("nozzle_max", 999) < m["nozzle_temp"][0]:
        r.warnings.append(f"Duza imprimantei ({p['nozzle_max']}°C) nu ajunge la temperatura minima "
                          f"pentru {m['name']} ({m['nozzle_temp'][0]}°C). Nu e recomandat.")
    if m.get("needs_enclosure") and not p.get("enclosed"):
        s["fan_max"] = min(s["fan_max"], 15)
        s["fan_min"] = 0
        s["draft_shield"] = True
        s["brim_mm"] = max(s["brim_mm"], 5.0)
        r.warnings.append(f"{m['name']} pe imprimanta deschisa: risc mare de warping si crapaturi. "
                          "Printeaza departe de curent/geam, ideal sub o cutie sau o incinta improvizata. "
                          "Am redus ventilatorul, am pus brim si draft shield.")
    if m.get("enclosure_bad") and p.get("enclosed"):
        r.reasons.append(f"{m['name']} in imprimanta inchisa: deschide capacul/usa ca sa eviti infundarea duzei.")
    if m.get("direct_drive_only") and p.get("extruder") == "bowden":
        r.warnings.append(f"{m['name']} se printeaza greu pe bowden: viteza foarte mica, retractie minima.")
        s["max_volumetric_speed"] = min(s["max_volumetric_speed"], 2.0)
    if m.get("hardened_nozzle"):
        r.warnings.append("Material abraziv: foloseste duza din otel calit.")
    if m.get("fumes"):
        r.reasons.append("Materialul emana vapori: aeriseste incaperea.")
    if layer <= 0.12:
        r.reasons.append("Strat fin: straturile se racesc mai greu, timpul de printare creste mult.")
    if nozzle != 0.4:
        s["max_volumetric_speed"] *= (nozzle / 0.4) ** 1.5

    if a:
        dims = a["dims_mm"]
        footprint = max(dims[0], dims[1])
        if a["overhang_frac"] > 0.03:
            s["supports"] = True
            r.reasons.append(f"{a['overhang_frac']*100:.0f}% din suprafata e in consola (>{45}°): "
                             "activez suporturi tree.")
        if m["warp_risk"] >= 2 and footprint > 60:
            s["brim_mm"] = max(s["brim_mm"], 8.0)
            r.reasons.append(f"Piesa mare ({footprint:.0f} mm) dintr-un material care se strange: brim 8 mm.")
        if a["contact_frac"] < 0.02 and dims[2] > 2 * max(min(dims[0], dims[1]), 1):
            s["brim_mm"] = max(s["brim_mm"], 5.0)
            r.reasons.append("Piesa inalta cu baza mica: brim pentru stabilitate.")
        wall = a.get("min_wall_mm")
        if wall and wall < max(m.get("min_wall_mm", 0.8), 2 * nozzle):
            r.warnings.append(f"Pereti foarte subtiri detectati (~{wall:.2f} mm). Minimul recomandat "
                              f"pentru duza de {nozzle} mm este {max(m.get('min_wall_mm', 0.8), 2*nozzle):.1f} mm.")
    return s


def _base_resin(p: dict, m: dict, layer: float, a: dict | None, r: Recommendation) -> dict:
    f = p.get("exposure_factor", 1.0) * (layer / 0.05) ** 0.8
    s = {
        "layer_height": layer,
        "exposure_s": m["exposure_s"] * f, "bottom_exposure_s": m["bottom_exposure_s"] * p.get("exposure_factor", 1.0),
        "bottom_layers": m["bottom_layers"], "lift_mm": m["lift_mm"],
        "lift_speed_mm_min": m["lift_speed_mm_min"], "retract_speed_mm_min": m["retract_speed_mm_min"],
        "supports": True, "hollow": False, "drain_hole_mm": m["drain_hole_mm"],
    }
    r.reasons.append("Rasina: inclina piesa 30-45° fata de platforma ca sa reduci forta de dezlipire.")
    r.warnings.append("Timpii de expunere sunt de pornire - fa o calibrare pentru rasina ta.")
    if a and a.get("volume_cm3") and a["volume_cm3"] > 20:
        s["hollow"] = True
        r.reasons.append(f"Volum mare ({a['volume_cm3']:.0f} cm³): goleste piesa (perete 2-3 mm) si "
                         f"fa 2 gauri de drenaj de {m['drain_hole_mm']} mm.")
    if a and a.get("min_wall_mm") and a["min_wall_mm"] < m["min_wall_mm"]:
        r.warnings.append(f"Pereti sub {m['min_wall_mm']} mm (~{a['min_wall_mm']:.2f} mm) - risc de rupere.")
    return s


def _base_sls(p: dict, m: dict, a: dict | None, r: Recommendation) -> dict:
    r.reasons.append("SLS/MJF: nu sunt necesare suporturi.")
    r.reasons.append(f"Golurile inchise au nevoie de gauri de evacuare de minim {m['escape_hole_mm']} mm.")
    if a and a.get("min_wall_mm") and a["min_wall_mm"] < m["min_wall_mm"]:
        r.warnings.append(f"Pereti sub {m['min_wall_mm']} mm detectati.")
    return {"min_wall_mm": m["min_wall_mm"], "shrink_xy_pct": m["shrink_xy_pct"],
            "shrink_z_pct": m["shrink_z_pct"], "supports": False}


# ------------------------------------------------------------------ main entry
def recommend(printer_id: str, material_id: str, analysis: dict | None = None,
              layer_height: float | None = None, nozzle: float = 0.4,
              memory: Memory | None = None) -> Recommendation:
    p = catalog.get_printer(printer_id)
    m = catalog.get_material(material_id)
    if p["technology"] != m["technology"]:
        raise ValueError(f"{m['name']} ({m['technology']}) nu se poate folosi pe {p['name']} ({p['technology']}).")
    tech = p["technology"]
    r = Recommendation(p, m, {})

    if analysis:
        vol = p.get("volume_mm")
        if vol and any(d > v for d, v in zip(sorted(analysis["dims_mm"]), sorted(vol))):
            r.warnings.append(f"Piesa ({' x '.join(f'{d:.0f}' for d in analysis['dims_mm'])} mm) nu incape "
                              f"in volumul imprimantei ({' x '.join(map(str, vol))} mm). Scaleaz-o sau imparte-o.")
        if not analysis.get("watertight", True):
            r.warnings.append("Mesh-ul nu e complet inchis - verifica previzualizarea din slicer.")

    if tech == "fdm":
        base = _base_fdm(p, m, layer_height or 0.2, nozzle, analysis, r)
    elif tech == "resin":
        base = _base_resin(p, m, layer_height or m["layer_height_mm"], analysis, r)
    else:
        base = _base_sls(p, m, analysis, r)
    base = _clamp(base, m, p) if tech == "fdm" else _clamp_generic(base)

    settings = dict(base)
    if memory is not None and LEARNABLE[tech]:
        settings = _learn(tech, base, p, m, analysis, memory, r)
    r.settings = settings
    if tech == "fdm":
        r.settings["nozzle_temp_first"] = r.settings["nozzle_temp"] + (5 if m["warp_risk"] >= 2 else 0)
        r.settings["nozzle_temp_first"] = min(r.settings["nozzle_temp_first"], p.get("nozzle_max", 999),
                                              m["nozzle_temp"][2])
        r.settings["bed_temp_first"] = r.settings["bed_temp"]
    return r


def _clamp_generic(s: dict) -> dict:
    out = dict(s)
    for k, (lo, hi) in LIMITS.items():
        if k in out and not isinstance(out[k], bool):
            out[k] = max(lo, min(hi, out[k]))
    for k, v in out.items():
        if isinstance(v, float) and k in ROUND:
            out[k] = round(v, ROUND[k])
    return out


def _learn(tech, base, p, m, analysis, memory: Memory, r: Recommendation) -> dict:
    features = (analysis or {}).get("features") or []
    history = memory.similar_jobs(p["id"], m["id"], features)
    if not history:
        r.reasons.append("Nu am inca istoric pentru aceasta combinatie imprimanta + material. "
                         "Dupa print, da feedback ca sa invat.")
        return base

    keys = [k for k in LEARNABLE[tech] if k in base]
    acc = {k: 0.0 for k in keys}
    wsum = 0.0
    W0 = 0.6  # weight of the textbook defaults
    for j in history:
        target = j["settings"]
        if j["outcome"] in ("fail", "partial") or j["issues"]:
            target = apply_issue_corrections(tech, target, j["issues"])
        w = j["similarity"] * (0.85 ** j["age_rank"])
        if j["outcome"] == "ok":
            w *= 1.0 + 0.1 * ((j.get("rating") or 4) - 3)
        elif j["outcome"] == "fail" and not j["issues"]:
            continue  # failed without saying why: nothing to learn from
        else:
            w *= 0.8
        if w < 0.02:
            continue
        for k in keys:
            if k in target and not isinstance(target[k], bool):
                acc[k] += w * float(target[k])
        wsum += w
        r.learned_from.append({"job": j["id"], "project": j["project_name"], "outcome": j["outcome"],
                               "issues": j["issues"], "similarity": round(j["similarity"], 2),
                               "weight": round(w, 3)})
    if wsum == 0:
        return base

    s = dict(base)
    for k in keys:
        s[k] = (W0 * base[k] + acc[k]) / (W0 + wsum)
    if tech == "fdm":
        s = _clamp(s, m, p)
        if s.get("brim_mm", 0) >= 1:
            s["brim_mm"] = float(round(s["brim_mm"]))
    else:
        s = _clamp_generic(s)
        s["bottom_layers"] = int(round(s["bottom_layers"]))
        s["lift_speed_mm_min"] = int(round(s["lift_speed_mm_min"]))

    n = len(r.learned_from)
    for k in keys:
        if abs(s[k] - base[k]) >= CHANGE_THRESHOLD.get(k, 0.5):
            name, unit = LABELS.get(k, (k, ""))
            r.reasons.append(f"{name}: {s[k]}{unit} (valoare de baza {base[k]}{unit}) - invatat din {n} "
                             f"print(uri) similare.")
    return s


def describe_issues(tech: str) -> dict:
    return {k: v[0] for k, v in ISSUES.get(tech, {}).items()}
