"""AI image -> 3D generation.

Engines are optional and installed on demand (`abydex engine install triposr`), so the
base app stays small. They run in a separate process to keep RAM usage contained.

TripoSR (MIT, by Tripo AI + Stability AI) works on CPU (~1-3 min per model, ~6-8 GB RAM)
and is much faster on an NVIDIA GPU.
"""
from __future__ import annotations

import importlib.util
import io
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from .catalog import user_dir

TRANSFORMERS = "transformers>=4.35,<4.46"  # TripoSR is not compatible with newer releases
T2I_MODEL = os.environ.get("ABYDEX_T2I_MODEL", "stabilityai/sd-turbo")

ENGINES = {
    "triposr": {
        "name": "TripoSR",
        "kind": "image-to-3d",
        "license": "MIT",
        "source_zip": "https://codeload.github.com/VAST-AI-Research/TripoSR/zip/refs/heads/main",
        "packages": ["omegaconf", "einops", TRANSFORMERS, "huggingface-hub",
                     "rembg[cpu]", "imageio", "pillow", "scikit-image"],
        "modules": ["torch", "omegaconf", "einops", "transformers", "rembg", "skimage"],
        "info": "Poza -> 3D. Merge si pe procesor (1-3 min), mult mai rapid pe placa NVIDIA.",
    },
    "sdturbo": {
        "name": "SD-Turbo (text -> imagine)",
        "kind": "text-to-image",
        "license": "Stability AI (gratuit pentru uz personal, vezi pagina modelului)",
        "packages": ["diffusers>=0.27", TRANSFORMERS, "huggingface-hub", "pillow", "safetensors"],
        "modules": ["torch", "diffusers", "transformers"],
        "info": "Descriere -> imagine (pasul 1 pentru obiecte decorative), apoi TripoSR o face 3D. "
                "~20-60 s pe procesor, model ~2.5 GB. Scrie descrierea in engleza pentru rezultate mai bune.",
    },
}


def engine_dir(name: str) -> Path:
    return user_dir() / "engines" / name


def has_nvidia() -> bool:
    return shutil.which("nvidia-smi") is not None


def is_installed(name: str) -> bool:
    """Cheap check (does not import torch)."""
    e = ENGINES.get(name)
    if not e:
        return False
    if name == "triposr" and not (engine_dir(name) / "tsr" / "system.py").exists():
        return False
    return all(importlib.util.find_spec(m) is not None for m in e["modules"])


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

    if "source_zip" in e and not (d / "tsr" / "system.py").exists():
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
    log("Gata. La prima folosire se descarca modelul de pe Hugging Face (cateva GB, o singura data).")


def generate(image: str | Path, out_path: str | Path, engine: str = "triposr",
             resolution: int = 256, device: str = "auto", remove_bg: bool = True) -> Path:
    """Run the engine in a subprocess. Returns the path of the generated mesh."""
    if not is_installed(engine):
        raise RuntimeError(f"Motorul '{engine}' nu e instalat. Ruleaza: abydex engine install {engine}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "abydex.engines.triposr_runner", str(image), str(out_path),
           "--engine-dir", str(engine_dir(engine)), "--resolution", str(resolution),
           "--device", device]
    if not remove_bg:
        cmd.append("--keep-bg")
    subprocess.run(cmd, check=True)
    if not out_path.exists():
        raise RuntimeError("Generarea nu a produs niciun fisier.")
    return out_path


def text_to_image(prompt: str, out_path: str | Path, steps: int = 2, seed: int | None = None,
                  device: str = "auto") -> Path:
    """Text -> product-style image (plain background), ready for image -> 3D."""
    if not is_installed("sdturbo"):
        raise RuntimeError("Motorul text -> imagine nu e instalat. Instaleaza-l din tab-ul 'Motoare AI' "
                           "sau: abydex engine install sdturbo")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    full = (f"{prompt}, single object, whole object visible, centered, plain white background, "
            "studio product photo, soft light, high detail")
    cmd = [sys.executable, "-m", "abydex.engines.sdturbo_runner", full, str(out_path),
           "--model", T2I_MODEL, "--steps", str(steps), "--device", device]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    subprocess.run(cmd, check=True)
    if not out_path.exists():
        raise RuntimeError("Generarea imaginii nu a produs niciun fisier.")
    return out_path
