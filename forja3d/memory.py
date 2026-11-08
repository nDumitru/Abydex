"""Local project memory (SQLite). Every prepared job and every print feedback is stored here,
so the next recommendation can learn from it."""
from __future__ import annotations

import json
import math
import shutil
import sqlite3
import time
from pathlib import Path

from .catalog import user_dir
from .mesh_tools import FEATURES_VERSION

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_hash TEXT,
    source_path TEXT,
    stored_path TEXT,
    dims_json TEXT,
    features_json TEXT,
    analysis_json TEXT,
    created REAL NOT NULL,
    features_version INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    printer_id TEXT NOT NULL,
    material_id TEXT NOT NULL,
    layer_height REAL,
    nozzle REAL,
    settings_json TEXT NOT NULL,
    created REAL NOT NULL,
    outcome TEXT,           -- ok | partial | fail | NULL (no feedback yet)
    rating INTEGER,         -- 1..5
    issues_json TEXT,
    notes TEXT,
    feedback_at REAL
);
CREATE INDEX IF NOT EXISTS jobs_pm ON jobs(printer_id, material_id);
"""

# Database migrations. NEVER edit an entry that was released - only append new ones.
# Index i upgrades the database from user_version i to i+1. A backup is made before upgrading,
# so what the app has learned survives every update.
MIGRATIONS: list[str] = [
    SCHEMA,  # schema 1 (v0.1.0)
    # schema 2 (v0.2.0): text -> 3D requests and the designs built from them
    """CREATE TABLE IF NOT EXISTS text_designs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER REFERENCES jobs(id),
        prompt TEXT NOT NULL,
        design_json TEXT NOT NULL,
        source TEXT,
        created REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS text_designs_job ON text_designs(job_id);""",
]
SCHEMA_VERSION = len(MIGRATIONS)


class Memory:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else user_dir() / "forja3d.db"
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        current = self.db.execute("PRAGMA user_version").fetchone()[0]
        target = len(MIGRATIONS)
        if current > target:
            raise RuntimeError("Baza de date e dintr-o versiune mai noua de Forja3D. Actualizeaza aplicatia.")
        if current == target:
            return
        if current > 0 and self.path.exists():
            shutil.copy2(self.path, self.path.with_suffix(f".db.bak-v{current}"))
        for i in range(current, target):
            self.db.executescript(MIGRATIONS[i])
            self.db.execute(f"PRAGMA user_version = {i + 1}")
        self.db.commit()

    def close(self):
        self.db.close()

    # ------------------------------------------------------------ writes
    def add_project(self, name, file_hash, source_path, stored_path, analysis: dict) -> int:
        fv = analysis.get("features_version", FEATURES_VERSION)
        row = self.db.execute("SELECT id FROM projects WHERE file_hash=? AND file_hash IS NOT NULL",
                              (file_hash,)).fetchone()
        if row:
            self.db.execute(
                "UPDATE projects SET name=?, stored_path=?, analysis_json=?, features_json=?, dims_json=?, "
                "features_version=? WHERE id=?",
                (name, str(stored_path), json.dumps(analysis), json.dumps(analysis["features"]),
                 json.dumps(analysis["dims_mm"]), fv, row["id"]))
            self.db.commit()
            return row["id"]
        cur = self.db.execute(
            "INSERT INTO projects(name,file_hash,source_path,stored_path,dims_json,features_json,"
            "analysis_json,created,features_version) VALUES (?,?,?,?,?,?,?,?,?)",
            (name, file_hash, str(source_path), str(stored_path), json.dumps(analysis["dims_mm"]),
             json.dumps(analysis["features"]), json.dumps(analysis), time.time(), fv))
        self.db.commit()
        return cur.lastrowid

    def add_job(self, project_id, printer_id, material_id, layer_height, nozzle, settings: dict) -> int:
        cur = self.db.execute(
            "INSERT INTO jobs(project_id,printer_id,material_id,layer_height,nozzle,settings_json,created) "
            "VALUES (?,?,?,?,?,?,?)",
            (project_id, printer_id, material_id, layer_height, nozzle, json.dumps(settings), time.time()))
        self.db.commit()
        return cur.lastrowid

    def add_feedback(self, job_id: int, outcome: str, rating: int | None = None,
                     issues: list[str] | None = None, notes: str = "",
                     actual_settings: dict | None = None) -> None:
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(f"Nu exista job-ul #{job_id}")
        if outcome not in ("ok", "partial", "fail"):
            raise ValueError("outcome trebuie sa fie ok / partial / fail")
        settings = job["settings"]
        if actual_settings:  # user changed values in the slicer: learn from what was really printed
            settings = {**settings, **actual_settings}
        self.db.execute(
            "UPDATE jobs SET outcome=?, rating=?, issues_json=?, notes=?, feedback_at=?, settings_json=? "
            "WHERE id=?",
            (outcome, rating, json.dumps(issues or []), notes, time.time(), json.dumps(settings), job_id))
        self.db.commit()

    def add_text_design(self, job_id: int | None, prompt: str, design: dict, source: str = "") -> int:
        keep = {k: v for k, v in design.items() if k in ("template", "params", "csg", "organic")}
        cur = self.db.execute("INSERT INTO text_designs(job_id,prompt,design_json,source,created) VALUES (?,?,?,?,?)",
                              (job_id, prompt, json.dumps(keep), source, time.time()))
        self.db.commit()
        return cur.lastrowid

    def good_text_designs(self, limit: int = 50) -> list[dict]:
        """Requests whose printed result was rated good - used as examples / for reuse."""
        rows = self.db.execute(
            "SELECT t.prompt, t.design_json FROM text_designs t JOIN jobs j ON j.id=t.job_id "
            "WHERE j.outcome='ok' AND COALESCE(j.rating, 4) >= 4 ORDER BY j.feedback_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [{"prompt": r["prompt"], "design": json.loads(r["design_json"])} for r in rows]

    # ------------------------------------------------------------ reads
    def _job(self, r: sqlite3.Row) -> dict:
        d = dict(r)
        d["settings"] = json.loads(d.pop("settings_json"))
        d["issues"] = json.loads(d.pop("issues_json") or "[]")
        if "features_json" in d:
            d["features"] = json.loads(d.pop("features_json") or "[]")
        return d

    def get_job(self, job_id: int) -> dict | None:
        r = self.db.execute("SELECT j.*, p.name AS project_name, p.features_json FROM jobs j "
                            "JOIN projects p ON p.id=j.project_id WHERE j.id=?", (job_id,)).fetchone()
        return self._job(r) if r else None

    def recent_jobs(self, limit: int = 20) -> list[dict]:
        rows = self.db.execute("SELECT j.*, p.name AS project_name, p.features_json FROM jobs j "
                               "JOIN projects p ON p.id=j.project_id ORDER BY j.id DESC LIMIT ?",
                               (limit,)).fetchall()
        return [self._job(r) for r in rows]

    def similar_jobs(self, printer_id: str, material_id: str, features: list[float],
                     limit: int = 15) -> list[dict]:
        """Jobs with feedback for the same printer+material, sorted by shape similarity.
        Each result gets 'similarity' (0..1) and 'age_rank' (0 = newest)."""
        rows = self.db.execute(
            "SELECT j.*, p.name AS project_name, p.features_json, p.features_version FROM jobs j "
            "JOIN projects p ON p.id=j.project_id "
            "WHERE j.printer_id=? AND j.material_id=? AND j.outcome IS NOT NULL "
            "ORDER BY j.feedback_at DESC LIMIT 200", (printer_id, material_id)).fetchall()
        out = []
        for age, r in enumerate(rows):
            j = self._job(r)
            fv = j.pop("features_version", None)
            same = (1 if fv is None else fv) == FEATURES_VERSION
            j["similarity"] = similarity(features, j.get("features") if same else [])
            j["age_rank"] = age
            out.append(j)
        out.sort(key=lambda j: j["similarity"], reverse=True)
        return out[:limit]

    def stats(self) -> dict:
        q = lambda s: self.db.execute(s).fetchone()[0]
        return {
            "projects": q("SELECT COUNT(*) FROM projects"),
            "jobs": q("SELECT COUNT(*) FROM jobs"),
            "with_feedback": q("SELECT COUNT(*) FROM jobs WHERE outcome IS NOT NULL"),
            "ok": q("SELECT COUNT(*) FROM jobs WHERE outcome='ok'"),
            "fail": q("SELECT COUNT(*) FROM jobs WHERE outcome='fail'"),
        }


def similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.3  # unknown shape: still somewhat relevant (same printer + material)
    d = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    return math.exp(-2.0 * d)
