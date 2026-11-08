"""Runs TripoSR in its own process: image -> mesh.

TripoSR normally needs `torchmcubes`, which must be compiled (hard on Windows).
We replace it with scikit-image's marching cubes, so no compiler is needed.
"""
from __future__ import annotations

import argparse
import sys
import time
import types
from pathlib import Path


def _install_mcubes_shim() -> None:
    import numpy as np
    import torch
    from skimage.measure import marching_cubes as sk_mc

    def marching_cubes(vol, thresh):
        v = vol.detach().cpu().float().numpy()
        if v.min() > thresh or v.max() < thresh:  # empty surface
            return torch.zeros((0, 3)), torch.zeros((0, 3), dtype=torch.long)
        verts, faces, _, _ = sk_mc(v, level=thresh)
        # torchmcubes returns (x, y, z) = reversed array axes; TripoSR flips them back
        verts = np.ascontiguousarray(verts[:, ::-1])
        faces = np.ascontiguousarray(faces)  # winding verified: outward normals after TripoSR axis swap
        return torch.from_numpy(verts.copy()).float(), torch.from_numpy(faces.astype(np.int64))

    mod = types.ModuleType("torchmcubes")
    mod.marching_cubes = marching_cubes
    sys.modules["torchmcubes"] = mod


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("output")
    ap.add_argument("--engine-dir", required=True)
    ap.add_argument("--resolution", type=int, default=256)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--keep-bg", action="store_true")
    ap.add_argument("--foreground-ratio", type=float, default=0.85)
    a = ap.parse_args(argv)

    sys.path.insert(0, a.engine_dir)
    _install_mcubes_shim()
    import numpy as np
    import torch
    from PIL import Image
    from tsr.system import TSR
    from tsr.utils import remove_background, resize_foreground

    device = a.device
    if device == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    print(f"[forja3d] Incarc modelul TripoSR pe {device}...", flush=True)
    model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
    model.renderer.set_chunk_size(8192)
    model.to(device)

    img = Image.open(a.image)
    if a.keep_bg:
        img = img.convert("RGB")
    else:
        import rembg
        img = remove_background(img, rembg.new_session())
        img = resize_foreground(img, a.foreground_ratio)
        arr = np.array(img).astype(np.float32) / 255.0
        arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5
        img = Image.fromarray((arr * 255.0).astype(np.uint8))

    print("[forja3d] Generez forma 3D...", flush=True)
    with torch.no_grad():
        codes = model([img], device=device)
        meshes = model.extract_mesh(codes, False, resolution=a.resolution)
    mesh = meshes[0]
    # TripoSR is Y-up; printers are Z-up
    mesh.apply_transform([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    mesh.export(a.output)
    print(f"[forja3d] Gata in {time.time() - t0:.0f}s: {a.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
