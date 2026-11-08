"""Safe, declarative CSG: a JSON tree -> watertight mesh (manifold3d).

No code is ever executed: text/LLM output is only *data* validated here. Units are mm.
All solids sit with their base on z=0 and are centered in XY unless moved.

Nodes (any node also accepts "move": [x,y,z], "rotate": [rx,ry,rz] in degrees):
  {"box": [x, y, z], "r": 3}                   rounded vertical edges if r > 0
  {"cylinder": {"d": 10, "h": 5, "d2": 6}}      d2 optional -> cone
  {"sphere": {"d": 10}}                         centered at origin
  {"polygon": [[x, y], ...], "h": 5}            extruded outline
  {"union": [n, ...]}  {"difference": [base, cut, ...]}  {"intersection": [n, ...]}  {"hull": [n, ...]}
  {"grid": {"node": n, "count": [nx, ny], "step": [dx, dy]}}    centered pattern
  {"ring": {"node": n, "count": 6, "radius": 20}}               circular pattern
"""
from __future__ import annotations

import math

import numpy as np
import trimesh
from manifold3d import CrossSection, JoinType, Manifold

MAX_NODES = 600
MAX_DIM = 1000.0
MIN_DIM = 0.05


class CSGError(ValueError):
    pass


def _num(v, name, lo=MIN_DIM, hi=MAX_DIM) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise CSGError(f"'{name}' trebuie sa fie un numar")
    if not math.isfinite(x) or x < lo or x > hi:
        raise CSGError(f"'{name}' = {v} e in afara limitelor [{lo}, {hi}]")
    return x


def _vec(v, n, name, lo=-MAX_DIM, hi=MAX_DIM) -> list[float]:
    if not isinstance(v, (list, tuple)) or len(v) != n:
        raise CSGError(f"'{name}' trebuie sa aiba {n} valori")
    return [_num(x, name, lo, hi) for x in v]


def _segments(d: float) -> int:
    return int(max(24, min(160, d * 3)))


class _Builder:
    def __init__(self):
        self.count = 0

    def build(self, node) -> Manifold:
        self.count += 1
        if self.count > MAX_NODES:
            raise CSGError(f"Model prea complex (> {MAX_NODES} elemente)")
        if not isinstance(node, dict):
            raise CSGError("Fiecare element trebuie sa fie un obiect JSON")
        m = self._shape(node)
        if "rotate" in node:
            m = m.rotate(_vec(node["rotate"], 3, "rotate", -360, 360))
        if "move" in node:
            m = m.translate(_vec(node["move"], 3, "move"))
        return m

    def _children(self, node, key, min_n=1) -> list[Manifold]:
        items = node[key]
        if not isinstance(items, list) or len(items) < min_n:
            raise CSGError(f"'{key}' trebuie sa contina cel putin {min_n} elemente")
        return [self.build(c) for c in items]

    def _shape(self, n: dict) -> Manifold:
        if "box" in n:
            x, y, z = _vec(n["box"], 3, "box", MIN_DIM, MAX_DIM)
            r = _num(n.get("r", 0), "r", 0, MAX_DIM)
            r = min(r, x / 2 - 0.01, y / 2 - 0.01)
            if r > 0.05:
                cs = CrossSection.square([x - 2 * r, y - 2 * r], center=True).offset(
                    r, JoinType.Round, circular_segments=_segments(2 * r * 4))
                return cs.extrude(z)
            return Manifold.cube([x, y, z], center=False).translate([-x / 2, -y / 2, 0])
        if "cylinder" in n:
            c = n["cylinder"]
            if not isinstance(c, dict):
                raise CSGError("'cylinder' trebuie sa fie {d, h}")
            d, h = _num(c.get("d"), "d"), _num(c.get("h"), "h")
            d2 = _num(c["d2"], "d2", 0, MAX_DIM) if "d2" in c else d
            return Manifold.cylinder(h, d / 2, d2 / 2, _segments(max(d, d2)))
        if "sphere" in n:
            d = _num((n["sphere"] or {}).get("d"), "d")
            return Manifold.sphere(d / 2, _segments(d))
        if "polygon" in n:
            pts = n["polygon"]
            if not isinstance(pts, list) or not 3 <= len(pts) <= 500:
                raise CSGError("'polygon' are nevoie de 3-500 puncte")
            poly = [_vec(p, 2, "polygon") for p in pts]
            cs = CrossSection([poly])
            if cs.area() < 1e-6:
                raise CSGError("Poligonul are arie zero")
            return cs.extrude(_num(n.get("h"), "h"))
        if "union" in n:
            return Manifold.batch_boolean(self._children(n, "union"), _op("Add"))
        if "difference" in n:
            parts = self._children(n, "difference", 1)
            base = parts[0]
            if len(parts) > 1:
                base = base - Manifold.batch_boolean(parts[1:], _op("Add"))
            return base
        if "intersection" in n:
            parts = self._children(n, "intersection", 2)
            return Manifold.batch_boolean(parts, _op("Intersect"))
        if "hull" in n:
            return Manifold.batch_hull(self._children(n, "hull"))
        if "grid" in n:
            g = n["grid"]
            nx, ny = [int(_num(v, "count", 1, 100)) for v in _vec(g.get("count"), 2, "count", 1, 100)]
            dx, dy = _vec(g.get("step", [0, 0]), 2, "step", 0, MAX_DIM)
            base = self.build(g.get("node"))
            items = [base.translate([(i - (nx - 1) / 2) * dx, (j - (ny - 1) / 2) * dy, 0])
                     for i in range(nx) for j in range(ny)]
            return Manifold.batch_boolean(items, _op("Add"))
        if "ring" in n:
            g = n["ring"]
            cnt = int(_num(g.get("count"), "count", 1, 360))
            rad = _num(g.get("radius"), "radius", 0, MAX_DIM)
            base = self.build(g.get("node"))
            items = []
            for k in range(cnt):
                a = 360.0 * k / cnt
                items.append(base.translate([rad, 0, 0]).rotate([0, 0, a]))
            return Manifold.batch_boolean(items, _op("Add"))
        raise CSGError(f"Element necunoscut: {sorted(k for k in n if k not in ('move', 'rotate'))}")


def _op(name: str):
    from manifold3d import OpType
    return getattr(OpType, name)


def build(spec: dict) -> trimesh.Trimesh:
    """Validate + build a CSG spec. Raises CSGError with a readable (Romanian) message."""
    m = _Builder().build(spec)
    if m.is_empty():
        raise CSGError("Rezultatul e gol (verifica dimensiunile si operatiile).")
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3]
    faces = np.asarray(mesh.tri_verts)
    tm = trimesh.Trimesh(verts, faces, process=True)
    if float(tm.extents.max()) > MAX_DIM:
        raise CSGError("Piesa depaseste 1 metru.")
    return tm
