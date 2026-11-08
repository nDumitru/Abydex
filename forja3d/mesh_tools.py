"""Mesh loading, repair, analysis and print orientation. CPU only (trimesh + numpy)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import trimesh

OVERHANG_DEG = 45.0  # faces steeper than this (measured from vertical) need support


def load(path: str | Path) -> trimesh.Trimesh:
    m = trimesh.load(str(path), force="mesh", process=False)
    if not isinstance(m, trimesh.Trimesh) or len(m.faces) == 0:
        raise ValueError(f"Nu am putut citi un mesh valid din {path}")
    return m


def file_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


@dataclass
class RepairReport:
    watertight_before: bool
    watertight_after: bool
    faces_before: int
    faces_after: int
    removed_fragments: int
    holes_filled: bool
    scaled_by: float = 1.0
    notes: list[str] = field(default_factory=list)


def repair(mesh: trimesh.Trimesh, target_size_mm: float | None = None,
           min_fragment_ratio: float = 0.002) -> tuple[trimesh.Trimesh, RepairReport]:
    """Clean a mesh for printing. AI-generated meshes often have floaters and holes."""
    m = mesh.copy()
    rep = RepairReport(m.is_watertight, False, len(m.faces), 0, 0, False)

    m.merge_vertices()
    m.update_faces(m.nondegenerate_faces())
    m.update_faces(m.unique_faces())
    m.remove_unreferenced_vertices()

    # drop small floating fragments
    parts = m.split(only_watertight=False)
    if len(parts) > 1:
        areas = np.array([p.area for p in parts])
        keep = [p for p, a in zip(parts, areas) if a >= areas.max() * min_fragment_ratio]
        rep.removed_fragments = len(parts) - len(keep)
        m = trimesh.util.concatenate(keep)
        if len(keep) > 1 and all(p.is_watertight for p in keep):
            try:  # merge overlapping bodies into one solid
                u = trimesh.boolean.union(keep, engine="manifold")
                if isinstance(u, trimesh.Trimesh) and len(u.faces):
                    m = u
            except Exception:
                pass
        n_bodies = len(m.split(only_watertight=False))
        if n_bodies > 1:
            rep.notes.append(f"Modelul are {n_bodies} corpuri separate.")

    trimesh.repair.fix_normals(m)
    if not m.is_watertight:
        rep.holes_filled = bool(trimesh.repair.fill_holes(m))
        trimesh.repair.fix_normals(m)

    if target_size_mm:
        ext = float(m.extents.max())
        if ext > 0:
            rep.scaled_by = target_size_mm / ext
            m.apply_scale(rep.scaled_by)
    elif m.extents.max() < 5:
        rep.notes.append("Modelul e foarte mic (< 5 mm). Probabil nu e in milimetri - foloseste --size.")

    rep.watertight_after = m.is_watertight
    rep.faces_after = len(m.faces)
    if not m.is_watertight:
        rep.notes.append("Mesh-ul tot nu e inchis complet (watertight). Slicer-ul il poate repara, "
                         "dar verifica previzualizarea.")
    return m, rep


# ---------------------------------------------------------------- analysis
def _overhang_mask(m: trimesh.Trimesh, angle_deg: float = OVERHANG_DEG) -> np.ndarray:
    nz = m.face_normals[:, 2]
    limit = -np.sin(np.radians(90 - angle_deg))  # normal pointing down more than angle
    zmin = m.bounds[0, 2]
    face_z = m.triangles_center[:, 2]
    on_bed = face_z < zmin + 0.2
    return (nz < limit) & ~on_bed


def _bed_contact_area(m: trimesh.Trimesh) -> float:
    zmin = m.bounds[0, 2]
    mask = (m.triangles[:, :, 2].max(axis=1) < zmin + 0.2) & (m.face_normals[:, 2] < -0.9)
    return float(m.area_faces[mask].sum())


def _rotation_to_down(normal: np.ndarray) -> np.ndarray:
    return trimesh.geometry.align_vectors(normal, [0, 0, -1])


def best_orientation(m: trimesh.Trimesh, candidates: int = 12) -> tuple[np.ndarray, dict]:
    """Try axis directions + largest convex-hull facets as the face placed on the bed.
    Score: little overhang, big bed contact, not too tall."""
    normals = [np.array(v, float) for v in
               ([0, 0, -1], [0, 0, 1], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0])]
    try:
        hull = m.convex_hull
        order = np.argsort(hull.facets_area)[::-1][:candidates]
        normals += [hull.facets_normal[i] for i in order]
    except Exception:  # pragma: no cover - hull can fail on degenerate meshes
        pass

    best = None
    scale = max(float(m.area), 1e-9)
    for n in normals:
        T = _rotation_to_down(n)
        r = m.copy()
        r.apply_transform(T)
        overhang = float(r.area_faces[_overhang_mask(r)].sum()) / scale
        contact = _bed_contact_area(r) / scale
        height = float(r.extents[2] / max(r.extents.max(), 1e-9))
        score = overhang - 1.5 * contact + 0.15 * height
        if best is None or score < best[0] - 1e-9:
            best = (score, T, {"overhang_frac": overhang, "contact_frac": contact})
    return best[1], best[2]


def place_on_bed(m: trimesh.Trimesh) -> None:
    b = m.bounds
    m.apply_translation([-(b[0, 0] + b[1, 0]) / 2, -(b[0, 1] + b[1, 1]) / 2, -b[0, 2]])


def min_wall_thickness(m: trimesh.Trimesh, samples: int = 400, seed: int = 0) -> float | None:
    """Approximate thin-wall check: cast rays inward from surface points (5th percentile)."""
    if not m.is_watertight:
        return None
    pts, fidx = trimesh.sample.sample_surface(m, samples, seed=seed)
    dirs = -m.face_normals[fidx]
    origins = pts + dirs * 1e-4
    try:
        locs, ray_idx, _ = m.ray.intersects_location(origins, dirs, multiple_hits=False)
    except Exception:
        return None
    if len(ray_idx) == 0:
        return None
    d = np.linalg.norm(locs - origins[ray_idx], axis=1)
    d = d[d > 1e-3]
    return float(np.percentile(d, 5)) if len(d) else None


@dataclass
class Analysis:
    dims_mm: list[float]
    volume_cm3: float | None
    area_cm2: float
    watertight: bool
    overhang_frac: float
    contact_frac: float
    min_wall_mm: float | None
    bodies: int
    features: list[float]

    def to_dict(self) -> dict:
        return asdict(self)


def analyze(m: trimesh.Trimesh) -> Analysis:
    """Analyze a mesh that is already oriented & placed on the bed."""
    ext = m.extents
    vol = float(abs(m.volume)) / 1000 if m.is_watertight else None
    overhang = float(m.area_faces[_overhang_mask(m)].sum()) / max(m.area, 1e-9)
    contact = _bed_contact_area(m) / max(m.area, 1e-9)
    wall = min_wall_thickness(m)
    a = Analysis(
        dims_mm=[round(float(x), 2) for x in ext],
        volume_cm3=round(vol, 3) if vol is not None else None,
        area_cm2=round(float(m.area) / 100, 2),
        watertight=bool(m.is_watertight),
        overhang_frac=round(overhang, 4),
        contact_frac=round(contact, 4),
        min_wall_mm=round(wall, 2) if wall else None,
        bodies=len(m.split(only_watertight=False)),
        features=[],
    )
    a.features = shape_features(m, a)
    return a


def shape_features(m: trimesh.Trimesh, a: Analysis) -> list[float]:
    """Small descriptor used to find 'similar' past projects. Scale-aware but cheap."""
    ext = np.sort(np.asarray(m.extents, float))[::-1]
    big = max(ext[0], 1e-9)
    bbox_vol = float(np.prod(m.extents))
    fill = (abs(m.volume) / bbox_vol) if (m.is_watertight and bbox_vol > 0) else 0.5
    footprint = float(m.extents[0] * m.extents[1])
    slender = float(m.extents[2] / np.sqrt(max(footprint, 1e-9)))
    return [
        round(ext[1] / big, 4),
        round(ext[2] / big, 4),
        round(float(fill), 4),
        round(a.overhang_frac * 4, 4),            # weighted: overhangs matter a lot
        round(min(slender, 5.0) / 2, 4),
        round(np.log10(max(big, 1.0)) / 2.5, 4),   # size: 1mm..300mm -> 0..1
        round(min(a.contact_frac * 10, 1.0), 4),
    ]


def prepare(path: str | Path, target_size_mm: float | None = None, orient: bool = True):
    """Load -> repair -> orient -> place -> analyze. Returns (mesh, repair_report, analysis)."""
    m, rep = repair(load(path), target_size_mm)
    if orient:
        T, _ = best_orientation(m)
        m.apply_transform(T)
    place_on_bed(m)
    return m, rep, analyze(m)
