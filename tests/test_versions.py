import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from forja3d import catalog, memory, updates

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("FORJA3D_HOME", str(tmp_path / "home"))
    yield tmp_path


def test_new_db_gets_latest_schema(tmp_path):
    m = memory.Memory(tmp_path / "a.db")
    assert m.db.execute("PRAGMA user_version").fetchone()[0] == len(memory.MIGRATIONS)
    m.close()


def test_future_migration_keeps_data_and_makes_backup(tmp_path, monkeypatch):
    db = tmp_path / "b.db"
    m = memory.Memory(db)
    pid = m.add_project("p", "h", "src", "dst", {"dims_mm": [1, 2, 3], "features": [0.1]})
    m.add_job(pid, "bambu_a1", "pla", 0.2, 0.4, {"nozzle_temp": 210})
    m.close()
    # simulate the next release adding a column
    monkeypatch.setattr(memory, "MIGRATIONS", memory.MIGRATIONS + ["ALTER TABLE jobs ADD COLUMN photo_path TEXT;"])
    m = memory.Memory(db)
    assert m.db.execute("PRAGMA user_version").fetchone()[0] == len(memory.MIGRATIONS)
    assert m.get_job(1)["settings"]["nozzle_temp"] == 210
    assert "photo_path" in m.get_job(1)
    m.close()
    assert (tmp_path / "b.db.bak-v1").exists()


def test_db_from_newer_app_is_refused(tmp_path):
    db = tmp_path / "c.db"
    con = sqlite3.connect(db); con.execute("PRAGMA user_version = 99"); con.commit(); con.close()
    with pytest.raises(RuntimeError):
        memory.Memory(db)


def test_old_feature_versions_are_not_compared(tmp_path, monkeypatch):
    m = memory.Memory(tmp_path / "d.db")
    pid = m.add_project("p", "h", "s", "d", {"dims_mm": [1, 1, 1], "features": [0.5, 0.5], "features_version": 0})
    j = m.add_job(pid, "bambu_a1", "pla", 0.2, 0.4, {})
    m.add_feedback(j, "ok")
    assert m.similar_jobs("bambu_a1", "pla", [0.5, 0.5])[0]["similarity"] == pytest.approx(0.3)
    m.close()


@pytest.mark.parametrize("latest,current,newer", [
    ("v0.2.0", "0.1.0", True), ("v0.1.0", "0.1.0", False), ("v0.1.1", "0.1.0", True),
    ("v0.2.0-beta.1", "0.1.0", True), ("v0.2.0", "0.2.0-beta.1", True), ("v0.2.0-beta.1", "0.2.0", False),
    ("v1.0.0", "0.9.9", True), ("v0.10.0", "0.9.0", True),
])
def test_version_compare(latest, current, newer):
    assert updates.is_newer(latest, current) is newer


def test_update_check_offline_is_harmless(monkeypatch):
    def boom(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(updates.urllib.request, "urlopen", boom)
    r = updates.check(force=True)
    assert r["update_available"] is False and "error" in r


def test_update_check_can_be_disabled(monkeypatch):
    monkeypatch.setenv("FORJA3D_NO_UPDATE_CHECK", "1")
    assert updates.check()["disabled"]


def test_changelog_has_notes_for_current_version():
    from forja3d import __version__
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "release.py"), "--notes", __version__],
                         capture_output=True, text=True, check=True).stdout
    assert out.strip() and out.strip() != "Vezi CHANGELOG.md"
