"""Parametric part templates -> CSG specs (see csg.py). Dimensions in mm.

Each template: label, description, params {name: (label, default, min, max)} and a builder.
"""
from __future__ import annotations

from typing import Callable

# clearance hole diameters for metric screws (normal fit, slightly loose for FDM)
SCREW_HOLE = {2: 2.4, 2.5: 2.9, 3: 3.4, 4: 4.5, 5: 5.5, 6: 6.6, 8: 9.0, 10: 11.0}

TEMPLATES: dict[str, dict] = {}


def template(name: str, label: str, description: str, params: dict):
    def deco(fn: Callable[[dict], dict]):
        TEMPLATES[name] = {"label": label, "description": description, "params": params, "build": fn}
        return fn
    return deco


def _holes(d: float, h: float, nx: int, ny: int, dx: float, dy: float, z: float = -1.0) -> dict:
    return {"grid": {"node": {"cylinder": {"d": d, "h": h}}, "count": [nx, ny], "step": [dx, dy]}, "move": [0, 0, z]}


@template("box", "Cutie / carcasa", "Cutie cu pereti, colturi rotunjite si capac optional.", {
    "length": ("Lungime exterioara", 80, 10, 400), "width": ("Latime exterioara", 50, 10, 400),
    "height": ("Inaltime", 30, 5, 400), "wall": ("Grosime perete", 2.0, 0.8, 10),
    "radius": ("Raza colturi", 4, 0, 50), "lid": ("Capac (1 = da)", 1, 0, 1),
})
def _box(p):
    L, W, H, t, r = p["length"], p["width"], p["height"], p["wall"], p["radius"]
    body = {"difference": [
        {"box": [L, W, H], "r": r},
        {"box": [L - 2 * t, W - 2 * t, H], "r": max(r - t, 0), "move": [0, 0, t]},
    ]}
    if not p["lid"]:
        return body
    gap = 0.2  # fit clearance
    lip_h = min(6.0, H / 3)
    lid = {"union": [
        {"box": [L, W, t], "r": r},
        {"difference": [
            {"box": [L - 2 * t - 2 * gap, W - 2 * t - 2 * gap, lip_h + t], "r": max(r - t - gap, 0)},
            {"box": [L - 4 * t - 2 * gap, W - 4 * t - 2 * gap, lip_h + t], "r": max(r - 2 * t, 0), "move": [0, 0, t]},
        ]},
    ], "move": [0, W + 10, 0]}
    return {"union": [body, lid]}


@template("l_bracket", "Suport L / coltar", "Coltar in L cu gauri pe ambele aripi. Se printeaza culcat, pentru rezistenta la indoire.", {
    "length": ("Lungime aripa orizontala", 40, 10, 300), "height": ("Inaltime aripa verticala", 40, 10, 300),
    "width": ("Latime", 20, 5, 200), "thickness": ("Grosime", 4, 1.5, 20),
    "hole": ("Diametru gaura", 4.5, 0, 20), "holes": ("Gauri pe aripa", 1, 0, 6),
})
def _l_bracket(p):
    L, H, W, t, d, n = p["length"], p["height"], p["width"], p["thickness"], p["hole"], int(p["holes"])
    fil = min(t * 1.5, L - t, H - t)
    # printed lying on its side: the L profile is in XY, the width is the Z height,
    # so layers follow the bend (much stronger than printing it standing up)
    profile = [[0, 0], [L, 0], [L, t], [t + fil, t], [t, t + fil], [t, H], [0, H]]
    solid = {"polygon": profile, "h": W}
    if not n or not d:
        return solid
    cuts = [solid]
    for i in range(n):
        x = t + fil + (L - t - fil) * (i + 0.5) / n
        cuts.append({"cylinder": {"d": d, "h": t + 2}, "rotate": [-90, 0, 0], "move": [x, -1, W / 2]})
        y = t + fil + (H - t - fil) * (i + 0.5) / n
        cuts.append({"cylinder": {"d": d, "h": t + 2}, "rotate": [0, 90, 0], "move": [-1, y, W / 2]})
    return {"difference": cuts}


@template("spacer", "Distantier / saiba / bucsa", "Cilindru cu gaura (distantier, saiba, bucsa).", {
    "outer": ("Diametru exterior", 12, 2, 300), "inner": ("Diametru interior", 5.5, 0, 290),
    "height": ("Inaltime", 10, 0.4, 300),
})
def _spacer(p):
    D, d, H = p["outer"], min(p["inner"], p["outer"] - 0.8), p["height"]
    outer = {"cylinder": {"d": D, "h": H}}
    if d <= 0:
        return outer
    return {"difference": [outer, {"cylinder": {"d": d, "h": H + 2}, "move": [0, 0, -1]}]}


@template("plate", "Placa cu gauri", "Placa de montaj cu gauri in grila.", {
    "length": ("Lungime", 100, 5, 400), "width": ("Latime", 60, 5, 400), "thickness": ("Grosime", 3, 0.6, 30),
    "hole": ("Diametru gaura", 3.4, 0, 30), "holes_x": ("Gauri pe lungime", 2, 0, 30),
    "holes_y": ("Gauri pe latime", 2, 0, 30), "margin": ("Distanta gaura-margine", 6, 1, 100),
    "radius": ("Raza colturi", 3, 0, 50),
})
def _plate(p):
    L, W, t = p["length"], p["width"], p["thickness"]
    plate = {"box": [L, W, t], "r": p["radius"]}
    nx, ny, d, m = int(p["holes_x"]), int(p["holes_y"]), p["hole"], p["margin"]
    if not nx or not ny or not d:
        return plate
    dx = (L - 2 * m) / (nx - 1) if nx > 1 else 0
    dy = (W - 2 * m) / (ny - 1) if ny > 1 else 0
    return {"difference": [plate, _holes(d, t + 2, nx, ny, dx, dy)]}


@template("hook", "Carlig de perete", "Carlig cu placa de prindere si 2 gauri cu cap ingropat. Se printeaza culcat (rezistent).", {
    "width": ("Latime", 20, 8, 100), "height": ("Inaltime placa", 60, 20, 200),
    "depth": ("Adancime carlig", 30, 10, 150), "thickness": ("Grosime", 5, 2, 20),
    "hole": ("Diametru gaura", 4.5, 0, 12),
})
def _hook(p):
    W, H, D, t, d = p["width"], p["height"], p["depth"], p["thickness"], p["hole"]
    lip = min(15.0, H / 3)
    # printed lying flat: the side profile is the XY outline, the width is the Z height
    profile = [[0, 0], [D + t, 0], [D + t, lip], [D, lip], [D, t], [t, t], [t, H], [0, H]]
    body = {"polygon": profile, "h": W}
    if not d:
        return body
    cuts = [body]
    for y in (H * 0.45, H * 0.85):
        # screw hole through the back plate (along X) + countersink on the front
        cuts.append({"cylinder": {"d": d, "h": t + 2}, "rotate": [0, 90, 0], "move": [-1, y, W / 2]})
        cuts.append({"cylinder": {"d": d * 2, "d2": d, "h": d / 2}, "rotate": [0, -90, 0],
                     "move": [t + 0.01, y, W / 2]})
    return {"difference": cuts}


@template("tray", "Organizator cu compartimente", "Tava cu grila de compartimente.", {
    "length": ("Lungime", 120, 20, 400), "width": ("Latime", 80, 20, 400), "height": ("Inaltime", 30, 5, 200),
    "cells_x": ("Compartimente pe lungime", 3, 1, 20), "cells_y": ("Compartimente pe latime", 2, 1, 20),
    "wall": ("Grosime pereti", 1.6, 0.8, 6), "radius": ("Raza colturi", 4, 0, 30),
})
def _tray(p):
    L, W, H, t = p["length"], p["width"], p["height"], p["wall"]
    nx, ny = int(p["cells_x"]), int(p["cells_y"])
    cw = (L - (nx + 1) * t) / nx
    ch = (W - (ny + 1) * t) / ny
    if cw < 2 or ch < 2:
        raise ValueError("Prea multe compartimente pentru dimensiunea asta.")
    cell = {"box": [cw, ch, H], "r": min(2.0, cw / 3, ch / 3), "move": [0, 0, t]}
    return {"difference": [{"box": [L, W, H], "r": p["radius"]},
                           {"grid": {"node": cell, "count": [nx, ny], "step": [cw + t, ch + t]}}]}


def defaults(name: str) -> dict:
    return {k: v[1] for k, v in TEMPLATES[name]["params"].items()}


def clean_params(name: str, params: dict) -> dict:
    """Fill defaults, clamp to limits, drop unknown keys."""
    if name not in TEMPLATES:
        raise KeyError(f"Sablon necunoscut: {name}")
    out = defaults(name)
    for k, (label, default, lo, hi) in TEMPLATES[name]["params"].items():
        if k in params and params[k] is not None:
            try:
                v = float(params[k])
            except (TypeError, ValueError):
                continue
            out[k] = round(max(lo, min(hi, v)), 3)
    return out


def spec_for(name: str, params: dict) -> dict:
    return TEMPLATES[name]["build"](clean_params(name, params))


def describe() -> dict:
    """JSON-friendly description (for the UI / LLM prompt)."""
    return {n: {"label": t["label"], "description": t["description"],
                "params": {k: {"label": v[0], "default": v[1], "min": v[2], "max": v[3]}
                           for k, v in t["params"].items()}}
            for n, t in TEMPLATES.items()}
