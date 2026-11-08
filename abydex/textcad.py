"""Text -> 3D design.

Three ways to understand a request, tried in this order:
  1. memory  - a very similar request that printed well before is reused (learning)
  2. LLM     - optional local model via Ollama (http://127.0.0.1:11434), answers JSON only
  3. rules   - built-in Romanian/English parser for the parametric templates (always works, offline)

The result is always *data* (template + params, or a CSG tree) validated by csg.py,
never executable code.
"""
from __future__ import annotations

import json
import re
import unicodedata

from . import csg, templates



def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.replace("×", "x").replace("*", " x ")).strip()


# ----------------------------------------------------------------------------- rules
KEYWORDS = [  # order matters: more specific first
    ("tray", ["organizator", "compartiment", "tava", "tray", "organizer", "sertar", "divider"]),
    ("hook", ["carlig", "cuier", "agatatoare", "hook", "hanger"]),
    ("l_bracket", ["suport l", "suport in l", "coltar", "colt ", "l bracket", "l-bracket", "bracket",
                   "extensie l", "echer", "unghi"]),
    ("spacer", ["distantier", "saiba", "bucsa", "spacer", "washer", "standoff", "inel", "ring", "rondela"]),
    ("plate", ["placa", "plate", "panou", "panel", "capac plat", "flansa", "flange"]),
    ("box", ["cutie", "carcasa", "box", "enclosure", "case", "container", "recipient", "husa"]),
]
NUM = r"(\d+(?:[.,]\d+)?)"


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def _unit_scale(text_after: str) -> float:
    m = re.match(r"\s*(mm|cm|m)\b", text_after)
    if not m:
        return 1.0
    return {"mm": 1.0, "cm": 10.0, "m": 1000.0}[m.group(1)]


def _find(pattern: str, t: str):
    m = re.search(pattern, t)
    if not m:
        return None
    return _f(m.group(1)) * _unit_scale(t[m.end():])


def parse_rules(text: str) -> dict | None:
    """Returns {"template", "params", "notes"} or None if no technical part is recognized."""
    t = normalize(text)
    name = None
    for tpl, words in KEYWORDS:
        if any(w in t for w in words):
            name = tpl
            break
    if name is None:
        return None
    p: dict = {}
    notes: list[str] = []

    # cells "3x2 compartimente" before generic dimensions
    m = re.search(rf"{NUM}\s*x\s*{NUM}\s*(?:de\s*)?(?:compartimente|celule|cells|compartments)", t)
    if m:
        p["cells_x"], p["cells_y"] = _f(m.group(1)), _f(m.group(2))
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(rf"{NUM}\s*(?:de\s*)?(?:compartimente|celule|cells|compartments)", t)
    if m and "cells_x" not in p:
        p["cells_x"], p["cells_y"] = _f(m.group(1)), 1

    # dimensions 80x50x30 (optionally with units)
    m = re.search(rf"{NUM}\s*(?:mm|cm)?\s*x\s*{NUM}\s*(?:mm|cm)?(?:\s*x\s*{NUM})?", t)
    dims = None
    if m:
        scale = _unit_scale(t[m.end():]) if not re.search(r"\d\s*(mm)", m.group(0)) else 1.0
        if "cm" in m.group(0):
            scale = 10.0
        dims = [_f(g) * scale for g in m.groups() if g]

    # screws: M3 / surub m4
    screw = re.search(r"\bm\s?(\d+(?:[.,]5)?)\b", t)
    hole = None
    if screw:
        size = _f(screw.group(1))
        hole = templates.SCREW_HOLE.get(size, size + 0.4)
        notes.append(f"Gauri pentru surub M{screw.group(1)}: {hole} mm (cu joc pentru print).")
    hd = _find(rf"(?:gaura|gauri|orificiu|hole|holes)\s*(?:de|cu diametrul|diametru|o|of|d)?\s*{NUM}", t)
    if hd and not hole:
        hole = hd
    hcount = re.search(rf"{NUM}\s*(?:gauri|gaura|orificii|holes)", t)
    if re.search(r"fara gauri|no holes|without holes", t):
        hole, hcount = 0, None

    diam = _find(rf"(?:diametru(?:l)?(?: exterior)?|diameter|o\.?d\.?|ø|⌀|\bd)\s*(?:de|=|:)?\s*{NUM}", t)
    inner = _find(rf"(?:interior|inner|i\.?d\.?|gaura de|orificiu de)\s*(?:de|=|:)?\s*{NUM}", t)
    height = _find(rf"(?:inaltime(?:a)?|inalt(?:a)?|height|tall|high|h)\s*(?:de|=|:)?\s*{NUM}", t)
    wall = _find(rf"(?:perete|pereti|peretii|wall|walls)\s*(?:de|=|:)?\s*{NUM}", t)
    thick = _find(rf"(?:grosime(?:a)?|gros(?:a)?|thickness|thick)\s*(?:de|=|:)?\s*{NUM}", t)
    radius = _find(rf"(?:raza|radius|rotunjire)\s*(?:de|=|:)?\s*{NUM}", t)
    length = _find(rf"(?:lungime(?:a)?|lung(?:a)?|length|long)\s*(?:de|=|:)?\s*{NUM}", t)
    width = _find(rf"(?:latime(?:a)?|lat(?:a)?|width|wide)\s*(?:de|=|:)?\s*{NUM}", t)
    depth = _find(rf"(?:adancime(?:a)?|depth|deep)\s*(?:de|=|:)?\s*{NUM}", t)

    def setp(k, v):
        if v is not None and k in templates.TEMPLATES[name]["params"]:
            p[k] = v

    if name in ("box", "tray", "plate"):
        if dims:
            setp("length", dims[0]); setp("width", dims[1] if len(dims) > 1 else None)
            setp("height" if name != "plate" else "thickness", dims[2] if len(dims) > 2 else None)
        setp("length", length); setp("width", width); setp("height", height)
        setp("wall", wall or (thick if name != "plate" else None)); setp("thickness", thick)
        setp("radius", radius)
        if re.search(r"colturi (?:drepte|ascutite)|sharp corners|square corners", t):
            p["radius"] = 0
        if name == "box":
            if re.search(r"fara capac|without lid|no lid|deschisa", t):
                p["lid"] = 0
            elif re.search(r"capac|lid", t):
                p["lid"] = 1
        if name == "plate":
            if hole is not None:
                p["hole"] = hole
            if hcount:
                n = int(_f(hcount.group(1)))
                p["holes_x"], p["holes_y"] = {1: (1, 1), 2: (2, 1), 3: (3, 1), 4: (2, 2), 6: (3, 2),
                                              8: (4, 2), 9: (3, 3)}.get(n, (n, 1))
    elif name == "l_bracket":
        if dims:
            setp("length", dims[0]); setp("height", dims[1] if len(dims) > 1 else None)
            setp("width", dims[2] if len(dims) > 2 else None)
        setp("length", length); setp("height", height); setp("width", width); setp("thickness", thick)
        if hole is not None:
            p["hole"] = hole
        if hcount:
            p["holes"] = max(1, int(_f(hcount.group(1))) // 2)
    elif name == "spacer":
        if dims and len(dims) >= 2:  # "20x10" -> outer x height
            p["outer"], p["height"] = dims[0], dims[1]
        setp("outer", diam)
        if inner is not None:
            p["inner"] = inner
        elif hole is not None:
            p["inner"] = hole
        setp("height", height or thick)
        if re.search(r"plin|fara gaura|solid", t):
            p["inner"] = 0
        if "outer" not in p and p.get("inner"):  # e.g. "saiba M8": outer ~ 2x the hole
            p["outer"] = max(templates.defaults("spacer")["outer"], round(p["inner"] * 2, 1))
    elif name == "hook":
        setp("width", width); setp("height", height); setp("depth", depth); setp("thickness", thick)
        if hole is not None:
            p["hole"] = hole
    return {"template": name, "params": templates.clean_params(name, p), "notes": notes, "source": "reguli"}


# ----------------------------------------------------------------------------- LLM
def ollama_models(timeout: float = 1.5) -> list[str] | None:
    """Installed Ollama models, or None if Ollama is not running."""
    from . import llm, settings
    return llm.ollama_models(settings.llm_config()["base_url"] if settings.llm_config()["kind"] == "ollama"
                             else settings.LLM_PROVIDERS["ollama"]["base_url"], timeout)


def system_prompt() -> str:
    tdesc = {n: {"description": d["description"], "params": {k: v["label"] for k, v in d["params"].items()}}
             for n, d in templates.describe().items()}
    return f"""Esti un proiectant CAD pentru printare 3D. Transformi cererea utilizatorului (romana sau
engleza) intr-un obiect JSON, unitati mm. Raspunzi DOAR cu JSON, in una din formele:
1) {{"template": "<nume>", "params": {{...}}}} - daca cererea se potriveste unui sablon:
{json.dumps(tdesc, ensure_ascii=False)}
2) {{"csg": <arbore>}} - pentru alte piese tehnice. Elemente permise:
 {{"box":[x,y,z],"r":raza}}, {{"cylinder":{{"d":D,"h":H,"d2":D2}}}}, {{"sphere":{{"d":D}}}},
 {{"polygon":[[x,y],...],"h":H}}, {{"union":[...]}}, {{"difference":[baza, taiere, ...]}},
 {{"intersection":[...]}}, {{"hull":[...]}}, {{"grid":{{"node":N,"count":[nx,ny],"step":[dx,dy]}}}},
 {{"ring":{{"node":N,"count":n,"radius":R}}}}; orice element poate avea "move":[x,y,z] si "rotate":[rx,ry,rz].
 Solidele stau pe z=0, centrate in XY. Gauri pentru surub M3 = 3.4 mm, M4 = 4.5, M5 = 5.5.
 Proiecteaza piesa printabila: pereti de minim 1.2 mm, fara console mari daca se poate evita.
3) {{"organic": true}} - daca cererea e un obiect artistic/organic (figurina, animal, vaza decorativa)."""


def _user_prompt(text: str, examples: list[dict]) -> str:
    ex = "\n".join(f"Cerere: {e['prompt']}\nJSON: {json.dumps(e['design'], ensure_ascii=False)}"
                   for e in examples[:4])
    return (("Exemple care au iesit bine la print:\n" + ex + "\n\n") if ex else "") + f"Cerere: {text}"


def parse_llm(text: str, examples: list[dict] | None = None, cfg: dict | None = None) -> dict | None:
    from . import llm, settings
    cfg = cfg or settings.llm_config()
    data = llm.complete_json(system_prompt(), _user_prompt(text, examples or []), cfg)
    if not isinstance(data, dict):
        return None
    source = "llm" if cfg["kind"] == "ollama" else f"llm ({cfg['label']})"
    if data.get("organic"):
        return {"organic": True, "source": source}
    if "template" in data and data["template"] in templates.TEMPLATES:
        return {"template": data["template"],
                "params": templates.clean_params(data["template"], data.get("params") or {}),
                "notes": [], "source": source}
    if "csg" in data and isinstance(data["csg"], dict):
        csg.build(data["csg"])  # validate now; raises CSGError if invalid
        return {"csg": data["csg"], "notes": [], "source": source}
    return None


# ----------------------------------------------------------------------------- main
def _tokens(t: str) -> set[str]:
    return set(re.findall(r"[a-z]+|\d+(?:[.,]\d+)?", normalize(t)))


def similar_prompt(text: str, past: list[dict], threshold: float = 0.85) -> dict | None:
    """Reuse a past design whose request is almost identical (same words and numbers)."""
    a = _tokens(text)
    best, score = None, 0.0
    for e in past:
        b = _tokens(e["prompt"])
        if not a or not b:
            continue
        j = len(a & b) / len(a | b)
        if j > score:
            best, score = e, j
    return best if best and score >= threshold else None


def understand(text: str, mode: str = "auto", use_llm: bool = True, past: list[dict] | None = None,
               llm_cfg: dict | None = None) -> dict:
    """Decide what to build. Returns one of:
       {"template", "params", ...} | {"csg", ...} | {"organic": True, ...}"""
    text = (text or "").strip()
    if not text:
        raise ValueError("Scrie ce piesa vrei.")
    past = past or []
    notes: list[str] = []
    if mode in ("auto", "technical"):
        hit = similar_prompt(text, past)
        if hit:
            d = dict(hit["design"])
            d["source"] = "memorie"
            d.setdefault("notes", []).append(f"Am refolosit designul care a iesit bine la: \"{hit['prompt']}\".")
            return d
        if use_llm:
            from . import llm, settings
            cfg = llm_cfg or settings.llm_config()
            if llm.available(cfg):
                try:
                    d = parse_llm(text, examples=past, cfg=cfg)
                    if d and not (d.get("organic") and mode == "technical"):
                        return d
                except Exception as e:  # LLM unreachable / invalid output: fall back to rules
                    notes.append(f"AI-ul ({cfg['label']}) nu a dat un raspuns valid ({e}); am folosit regulile.")
        d = parse_rules(text)
        if d:
            d["notes"] = notes + d["notes"]
            return d
        if mode == "technical":
            raise ValueError("Nu am recunoscut tipul piesei. Incearca: cutie, suport L, distantier, placa cu "
                             "gauri, carlig, organizator - sau alege un furnizor AI in Setari AI pentru piese libere.")
    return {"organic": True, "notes": notes, "source": "imagine"}


def build_design(design: dict):
    """design -> trimesh mesh (technical designs only)."""
    if "template" in design:
        return csg.build(templates.spec_for(design["template"], design.get("params") or {}))
    if "csg" in design:
        return csg.build(design["csg"])
    raise ValueError("Designul nu e o piesa tehnica.")
