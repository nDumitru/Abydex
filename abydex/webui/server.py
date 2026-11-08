"""Tiny local web UI (standard library only). Listens on 127.0.0.1 only."""
from __future__ import annotations

import json
import mimetypes
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .. import __version__, advisor, catalog, generate, logs, templates, workflow
from ..memory import Memory

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 300 * 1024 * 1024
MESH_EXT = {".stl", ".obj", ".ply", ".3mf", ".glb", ".off"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def _uploads() -> Path:
    p = catalog.user_dir() / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


class Handler(BaseHTTPRequestHandler):
    server_version = f"Abydex/{__version__}"

    def log_message(self, fmt, *args):  # quieter console
        pass

    # ------------------------------------------------------------ helpers
    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, download: bool = False):
        if not path.is_file():
            return self._json({"error": "fisier inexistent"}, 404)
        data = path.read_bytes()
        self.send_response(200)
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            ctype = "text/javascript"
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length", 0))
        if n > MAX_UPLOAD:
            raise ValueError("Fisier prea mare")
        return self.rfile.read(n)

    def _save_upload(self, filename: str, allowed: set[str]) -> Path:
        name = Path(unquote(filename or "model.stl")).name
        ext = Path(name).suffix.lower()
        if ext not in allowed:
            raise ValueError(f"Tip de fisier nesuportat: {ext}")
        dest = _uploads() / f"{time.strftime('%Y%m%d-%H%M%S')}_{name}"
        dest.write_bytes(self._body())
        return dest

    def _job_file(self, job_id: int, name: str | None) -> Path | None:
        mem = Memory()
        try:
            r = mem.db.execute("SELECT p.stored_path FROM jobs j JOIN projects p ON p.id=j.project_id "
                               "WHERE j.id=?", (job_id,)).fetchone()
        finally:
            mem.close()
        if not r:
            return None
        stored = Path(r[0])
        folder = stored.parent
        if not name:
            return stored
        target = (folder / Path(name).name).resolve()
        return target if target.parent == folder.resolve() else None

    # ------------------------------------------------------------ routes
    def do_GET(self):
        try:
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if u.path in ("/", "/index.html"):
                return self._file(STATIC / "index.html")
            if u.path.startswith("/static/"):
                target = (STATIC / u.path[len("/static/"):]).resolve()
                if STATIC.resolve() not in target.parents:
                    return self._json({"error": "interzis"}, 403)
                return self._file(target)
            if u.path == "/api/catalog":
                return self._json({
                    "version": __version__,
                    "printers": catalog.printers(),
                    "materials": catalog.materials(),
                    "issues": {t: advisor.describe_issues(t) for t in ("fdm", "resin", "sls")},
                    "labels": advisor.LABELS,
                    "engines": {k: {**e, "installed": generate.is_installed(k)} for k, e in generate.ENGINES.items()},
                    "data_dir": str(catalog.user_dir()),
                    "templates": templates.describe(),
                })
            if u.path == "/api/llm":
                from .. import llm, settings
                cfg = settings.llm_config()
                cloud = settings.cloud3d_config()
                return self._json({"provider": cfg["provider"], "label": cfg["label"], "model": cfg["model"],
                                   "local": cfg["local"] or cfg["kind"] == "ollama", "ready": llm.available(cfg),
                                   "cloud3d": cloud["provider"] if cloud and cloud.get("key") else None})
            if u.path == "/api/settings":
                from .. import settings
                return self._json(settings.public_view())
            if u.path == "/api/update":
                from .. import updates
                return self._json(updates.check())
            if u.path == "/api/history":
                mem = Memory()
                try:
                    return self._json({"stats": mem.stats(), "jobs": mem.recent_jobs(int(q.get("limit", 50)))})
                finally:
                    mem.close()
            if u.path == "/api/file":
                f = self._job_file(int(q["job"]), q.get("name"))
                if not f:
                    return self._json({"error": "nu exista"}, 404)
                return self._file(f, download=q.get("download") == "1")
            return self._json({"error": "nu exista"}, 404)
        except Exception as e:  # pragma: no cover
            traceback.print_exc()
            logs.setup().exception("GET %s", self.path)
            return self._json({"error": str(e)}, 500)

    def do_POST(self):
        try:
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            num = lambda k: float(q[k]) if q.get(k) else None
            if u.path == "/api/prepare":
                path = self._save_upload(q.get("filename"), MESH_EXT)
                r = workflow.prepare_job(path, q["printer"], q["material"], num("layer"),
                                         num("nozzle") or 0.4, num("size"),
                                         q.get("name") or Path(unquote(q.get("filename", "model"))).stem)
                return self._json(r)
            if u.path == "/api/generate":
                img = self._save_upload(q.get("filename"), IMG_EXT)
                mesh = generate.generate(img, img.with_suffix(".obj"), q.get("engine", "triposr"))
                r = workflow.prepare_job(mesh, q["printer"], q["material"], num("layer"),
                                         num("nozzle") or 0.4, num("size") or 50.0,
                                         q.get("name") or Path(unquote(q.get("filename", "model"))).stem)
                return self._json(r)
            if u.path in ("/api/text/parse", "/api/text3d"):
                from .. import textcad
                d = json.loads(self._body() or b"{}")
                if u.path == "/api/text/parse":
                    mem = Memory()
                    try:
                        past = mem.good_text_designs()
                    finally:
                        mem.close()
                    return self._json(textcad.understand(d.get("text", ""), d.get("mode", "auto"),
                                                         use_llm=d.get("use_llm", True), past=past))
                r = workflow.text_to_3d(d.get("text", ""), d["printer"], d["material"],
                                        float(d["layer"]) if d.get("layer") else None,
                                        float(d.get("nozzle") or 0.4), d.get("name") or None,
                                        d.get("mode", "auto"), d.get("design"),
                                        float(d["size"]) if d.get("size") else None, d.get("use_llm", True),
                                        log=lambda m: None)
                return self._json(r)
            if u.path == "/api/settings":
                from .. import settings
                return self._json(settings.update(json.loads(self._body() or b"{}")))
            if u.path == "/api/settings/test":
                from .. import llm, settings, textcad
                cfg = settings.llm_config()
                if not llm.available(cfg):
                    raise ValueError(f"{cfg['label']}: " + (
                        f"serverul local nu raspunde la {cfg['base_url']} (e pornit?)."
                        if cfg["local"] or cfg["kind"] == "ollama" else "lipseste cheia API."))
                d = textcad.parse_llm("cutie 60x40x25 cu capac", cfg=cfg)
                return self._json({"ok": True, "provider": cfg["label"], "model": cfg["model"], "answer": d})
            if u.path == "/api/feedback":
                d = json.loads(self._body() or b"{}")
                mem = Memory()
                try:
                    mem.add_feedback(int(d["job_id"]), d["outcome"], d.get("rating"), d.get("issues") or [],
                                     d.get("notes", ""), d.get("actual") or None)
                finally:
                    mem.close()
                return self._json({"ok": True})
            if u.path == "/api/engine/install":
                log: list[str] = []
                generate.install(q.get("name", "triposr"), log=log.append)
                return self._json({"ok": True, "log": log})
            return self._json({"error": "nu exista"}, 404)
        except (KeyError, ValueError, RuntimeError) as e:  # includes LLMError / Cloud3DError
            msg = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
            logs.setup().warning("%s: %s", self.path, msg)
            return self._json({"error": str(msg)}, 400)
        except Exception as e:  # pragma: no cover
            traceback.print_exc()
            logs.setup().exception("POST %s", self.path)
            return self._json({"error": f"{type(e).__name__}: {e} (detalii in {logs.log_path()})"}, 500)


def make_server(port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port: int = 8765, open_browser: bool = True) -> None:
    log = logs.setup()
    srv = None
    for p in range(port, port + 20):  # another program (or a second Abydex) may use the port
        try:
            srv = make_server(p)
            break
        except OSError:
            continue
    if srv is None:
        raise RuntimeError(f"Nu gasesc niciun port liber intre {port} si {port + 19}.")
    log.info("UI pornit pe portul %s", srv.server_address[1])
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Abydex ruleaza la {url}  (Ctrl+C pentru oprire)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
