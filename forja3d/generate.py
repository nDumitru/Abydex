"""AI image -> 3D generation.

Engines are optional and installed on demand (`forja3d engine install triposr`), so the
base app stays small. They run in a separate process to keep RAM usage contained.

TripoSR (MIT, by Tripo AI + Stability AI) works on CPU (~1-3 min per model, ~6-8 GB RAM)
and is much faster on an NVIDIA GPU.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from .catalog import user_dir

ENGINES = {
    "triposr": {
        "name": "TripoSR",
        "license": "MIT",
        "source_zip": "https://codeload.github.com/VAST-AI-Research/TripoSR/zip/refs/heads/main",
        "packages": ["omegaconf", "einops", "transformers>=4.35,<4.46", "huggingface-hub",
                     "rembg[cpu]", "imageio", "pillow", "scikit-image"],
        "info": "Poza -> 3D. Merge si pe procesor (1-3 min), mult mai rapid pe placa NVIDIA.",
    },
}


def engine_dir(name: str) -> Path:
    return user_dir() / "engines" / name


def has_nvidia() -> bool:
    return shutil.which("nvidia-smi") is not None


def is_installed(name: str) -> bool:
    d = engine_dir(name)
    if name == "triposr":
        if not (d / "tsr" / "system.py").exists():
            return False
        try:
            import torch, omegaconf, einops, transformers, rembg, skimage  # noqa: F401
        except Exception:
            return False
        return True
    return False


def _pip(args: list[str], log) -> None:
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check"] + args
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def install(name: str, log=print) -> None:
    if name not in ENGINES:
        raise KeyError(f"Motor necunoscut: {name}. Disponibile: {', '.join(ENGINES)}")
    if getattr(sys, "frozen", False):
        raise RuntimeError("Versiunea 'frozen' nu poate instala pachete. Foloseste installerul complet.")
    e = ENGINES[name]
    d = engine_dir(name)
    d.mkdir(parents=True, exist_ok=True)

    if not (d / "tsr" / "system.py").exists():
        log(f"Descarc codul {e['name']}...")
        with urllib.request.urlopen(e["source_zip"], timeout=120) as r:
            data = r.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                parts = Path(member).parts
                if len(parts) > 1 and parts[1] in ("tsr", "LICENSE") and not member.endswith("/"):
                    target = d.joinpath(*parts[1:])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(member))

    log("Instalez PyTorch " + ("(NVIDIA CUDA)..." if has_nvidia() else "(doar procesor)..."))
    try:
        import torch  # noqa: F401
        log("PyTorch e deja instalat.")
    except ImportError:
        index = "https://download.pytorch.org/whl/cu124" if has_nvidia() else "https://download.pytorch.org/whl/cpu"
        _pip(["torch", "--index-url", index], log)
    log("Instalez restul dependintelor...")
    _pip(e["packages"], log)
    log("Gata. La prima generare se descarca modelul (~1.7 GB) de pe Hugging Face.")


def generate(image: str | Path, out_path: str | Path, engine: str = "triposr",
             resolution: int = 256, device: str = "auto", remove_bg: bool = True) -> Path:
    """Run the engine in a subprocess. Returns the path of the generated mesh."""
    if not is_installed(engine):
        raise RuntimeError(f"Motorul '{engine}' nu e instalat. Ruleaza: forja3d engine install {engine}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "forja3d.engines.triposr_runner", str(image), str(out_path),
           "--engine-dir", str(engine_dir(engine)), "--resolution", str(resolution),
           "--device", device]
    if not remove_bg:
        cmd.append("--keep-bg")
    subprocess.run(cmd, check=True)
    if not out_path.exists():
        raise RuntimeError("Generarea nu a produs niciun fisier.")
    return out_path
