"""Text -> image with a fast distilled diffusion model (default: SD-Turbo), in its own process."""
from __future__ import annotations

import argparse
import os
import time


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("output")
    ap.add_argument("--model", default="stabilityai/sd-turbo")
    ap.add_argument("--steps", type=int, default=2)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--device", default="auto")
    a = ap.parse_args(argv)

    import torch
    from diffusers import AutoPipelineForText2Image

    device = a.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(max(1, os.cpu_count() or 1))
    dtype = torch.float16 if device == "cuda" else torch.float32
    t0 = time.time()
    print(f"[forja3d] Incarc {a.model} pe {device}...", flush=True)
    pipe = AutoPipelineForText2Image.from_pretrained(a.model, torch_dtype=dtype)
    pipe.to(device)
    pipe.set_progress_bar_config(disable=True)
    gen = torch.Generator(device=device).manual_seed(a.seed) if a.seed is not None else None
    print("[forja3d] Generez imaginea...", flush=True)
    img = pipe(prompt=a.prompt, num_inference_steps=a.steps, guidance_scale=0.0,
               width=a.size, height=a.size, generator=gen).images[0]
    img.save(a.output)
    print(f"[forja3d] Imagine gata in {time.time() - t0:.0f}s: {a.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
