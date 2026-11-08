"""Cloud text -> 3D (Meshy, Tripo) for decorative objects. Optional: needs the user's API key.

Useful on computers without a strong graphics card, where local generation is slow.
The text prompt is sent to the chosen provider; the generated model is downloaded locally.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import settings

POLL_SECONDS = 4
MAX_WAIT = 15 * 60


class Cloud3DError(RuntimeError):
    pass


def _req(method: str, url: str, key: str, body: dict | None = None, timeout: float = 60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "Abydex"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            raise Cloud3DError(f"Cheia API e invalida ({e.code}). {detail}")
        if e.code in (402, 429):
            raise Cloud3DError(f"Credit epuizat sau prea multe cereri ({e.code}). {detail}")
        raise Cloud3DError(f"Eroare {e.code} de la serviciul 3D: {detail}")
    except urllib.error.URLError as e:
        raise Cloud3DError(f"Nu pot contacta serviciul 3D: {e.reason}")


def _download(url: str, out: Path) -> Path:
    with urllib.request.urlopen(url, timeout=300) as r:
        out.write_bytes(r.read())
    return out


def _wait(poll, log, label: str):
    t0 = time.time()
    last = -1
    while time.time() - t0 < MAX_WAIT:
        done, progress, result = poll()
        if done:
            return result
        if progress is not None and progress != last:
            log(f"{label}: {progress}%")
            last = progress
        time.sleep(POLL_SECONDS)
    raise Cloud3DError("Generarea in cloud dureaza prea mult (peste 15 minute).")


def meshy(prompt: str, out: Path, key: str, model: str = "latest", log=print) -> Path:
    base = "https://api.meshy.ai/openapi/v2/text-to-3d"
    body = {"mode": "preview", "prompt": prompt[:800], "target_formats": ["glb"]}
    if model and model != "latest":
        body["ai_model"] = model
    task = _req("POST", base, key, body)["result"]

    def poll():
        t = _req("GET", f"{base}/{task}", key)
        st = t.get("status")
        if st == "SUCCEEDED":
            url = (t.get("model_urls") or {}).get("glb")
            if not url:
                raise Cloud3DError("Meshy nu a returnat fisierul GLB.")
            return True, 100, url
        if st in ("FAILED", "CANCELED"):
            raise Cloud3DError(f"Meshy: generarea a esuat ({(t.get('task_error') or {}).get('message', st)}).")
        return False, t.get("progress"), None

    return _download(_wait(poll, log, "Meshy"), out)


def tripo(prompt: str, out: Path, key: str, model: str = "v3.1-20260211", log=print) -> Path:
    base = "https://openapi.tripo3d.ai/v3"
    r = _req("POST", f"{base}/generation/text-to-model", key,
             {"prompt": prompt, "model": model, "texture": False})
    task = (r.get("data") or {}).get("task_id")
    if not task:
        raise Cloud3DError(f"Tripo nu a pornit generarea: {r}")

    def poll():
        d = _req("GET", f"{base}/tasks/{task}", key).get("data") or {}
        st = d.get("status")
        if st == "success":
            url = (d.get("output") or {}).get("model_url")
            if not url:
                raise Cloud3DError("Tripo nu a returnat modelul.")
            return True, 100, url
        if st in ("failed", "cancelled", "banned", "expired"):
            raise Cloud3DError(f"Tripo: generarea a esuat ({st}).")
        return False, d.get("progress"), None

    # Tripo download links expire after a few minutes: download right away
    return _download(_wait(poll, log, "Tripo"), out)


PROVIDERS = {"meshy": meshy, "tripo": tripo}


def text_to_3d(prompt: str, out: str | Path, cfg: dict | None = None, log=print) -> Path:
    cfg = cfg or settings.cloud3d_config()
    if not cfg:
        raise Cloud3DError("Nu e ales niciun serviciu 3D in cloud (Setari AI).")
    if not cfg.get("key"):
        raise Cloud3DError(f"Lipseste cheia API pentru {cfg['provider']} (Setari AI).")
    out = Path(out).with_suffix(".glb")
    out.parent.mkdir(parents=True, exist_ok=True)
    log(f"Trimit descrierea la {cfg['provider']}...")
    return PROVIDERS[cfg["provider"]](prompt, out, cfg["key"], cfg["model"], log)
