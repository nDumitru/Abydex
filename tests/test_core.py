import json
import threading
import urllib.request

import pytest
import trimesh

from abydex import advisor, catalog, exporters, mesh_tools, workflow
from abydex.memory import Memory


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("ABYDEX_HOME", str(tmp_path / "home"))
    catalog.printers.cache_clear()
    catalog.materials.cache_clear()
    yield tmp_path


@pytest.fixture
def tee_stl(tmp_path):
    """Overlapping T bracket + a tiny floating fragment (typical messy mesh)."""
    a = trimesh.creation.box([80, 20, 5]); a.apply_translation([0, 0, 30])
    b = trimesh.creation.box([10, 20, 30]); b.apply_translation([0, 0, 12.5])
    f = trimesh.creation.icosphere(radius=0.3); f.apply_translation([50, 50, 50])
    p = tmp_path / "tee.stl"
    trimesh.util.concatenate([a, b, f]).export(p)
    return p


def test_repair_merges_bodies_and_drops_floaters(tee_stl):
    m, rep = mesh_tools.repair(mesh_tools.load(tee_stl))
    assert rep.removed_fragments == 1
    assert m.is_watertight
    assert len(m.split(only_watertight=False)) == 1


def test_orientation_puts_flat_side_down(tee_stl):
    m, _, a = mesh_tools.prepare(tee_stl)
    assert a.overhang_frac < 0.005          # upside-down T needs no supports
    assert a.dims_mm[2] == pytest.approx(35, abs=0.1)
    assert m.bounds[0, 2] == pytest.approx(0, abs=1e-6)


def test_scaling(tee_stl):
    _, rep, a = mesh_tools.prepare(tee_stl, target_size_mm=40)
    assert max(a.dims_mm) == pytest.approx(40, abs=0.01)


def test_asa_on_open_a1():
    r = advisor.recommend("bambu_a1", "asa", layer_height=0.12)
    s = r.settings
    assert s["bed_temp"] <= 100                    # A1 bed limit
    assert s["fan_max"] <= 15 and s["draft_shield"]
    assert any("deschisa" in w for w in r.warnings)


def test_tech_mismatch():
    with pytest.raises(ValueError):
        advisor.recommend("bambu_a1", "resin_standard")


def test_resin_and_sls():
    r = advisor.recommend("generic_resin", "resin_abs_like", {"dims_mm": [20, 20, 40], "volume_cm3": 30,
                                                              "watertight": True, "overhang_frac": 0.1,
                                                              "contact_frac": 0.1, "min_wall_mm": 0.4,
                                                              "features": []})
    assert r.settings["hollow"] and r.settings["supports"]
    assert any("Pereti" in w for w in r.warnings)
    assert not advisor.recommend("generic_sls", "pa12_sls").settings["supports"]


def test_learns_from_success_and_failures(tee_stl):
    mem = Memory()
    first = workflow.prepare_job(tee_stl, "bambu_a1", "petg", 0.2, memory=mem)
    base_temp = first["recommendation"]["settings"]["nozzle_temp"]
    # user printed at 235°C and it was perfect
    mem.add_feedback(first["job_id"], "ok", 5, [], actual_settings={"nozzle_temp": 235})
    second = workflow.prepare_job(tee_stl, "bambu_a1", "petg", 0.2, memory=mem)
    t2 = second["recommendation"]["settings"]["nozzle_temp"]
    assert 235 <= t2 < base_temp
    assert second["recommendation"]["learned_from"]
    # stringing on the next print pushes temperature further down, retraction up
    mem.add_feedback(second["job_id"], "partial", 3, ["stringing"])
    third = workflow.prepare_job(tee_stl, "bambu_a1", "petg", 0.2, memory=mem)
    s3 = third["recommendation"]["settings"]
    assert s3["nozzle_temp"] < t2
    assert s3["retraction_mm"] > first["recommendation"]["settings"]["retraction_mm"]


def test_other_printer_history_is_ignored(tee_stl):
    mem = Memory()
    j = workflow.prepare_job(tee_stl, "bambu_a1", "pla", memory=mem)
    mem.add_feedback(j["job_id"], "fail", 1, ["warping"])
    r = advisor.recommend("prusa_mk4", "pla", j["analysis"], memory=mem)
    assert not r.learned_from


def test_bambu_export(tee_stl, tmp_path):
    r = workflow.prepare_job(tee_stl, "bambu_a1", "asa", 0.12, out_dir=tmp_path / "out")
    files = {p.split("/")[-1].split("\\")[-1] for p in r["files"]}
    fil = next(f for f in r["files"] if f.endswith(".filament.json") and "orca" not in f)
    d = json.loads(open(fil, encoding="utf-8").read())
    assert d["inherits"] == "Generic ASA @BBL A1"
    assert d["textured_plate_temp"] == ["100"]
    proc = next(f for f in r["files"] if f.endswith(".process.json"))
    assert json.loads(open(proc, encoding="utf-8").read())["inherits"] == "0.12mm Fine @BBL A1"
    assert any(f.endswith(".prusaslicer.ini") for f in files)
    assert any(f.endswith("_setari.md") for f in files)


def test_web_api(tee_stl):
    from abydex.webui.server import make_server
    srv = make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        cat = json.load(urllib.request.urlopen(base + "/api/catalog"))
        assert "bambu_a1" in cat["printers"]
        req = urllib.request.Request(base + "/api/prepare?filename=tee.stl&printer=bambu_a1&material=pla&layer=0.2",
                                     data=tee_stl.read_bytes(), method="POST")
        r = json.load(urllib.request.urlopen(req))
        assert r["name"] == "tee"
        stl = urllib.request.urlopen(f"{base}/api/file?job={r['job_id']}").read()
        assert len(stl) > 1000
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(f"{base}/api/file?job={r['job_id']}&name=../../abydex.db")
        fb = urllib.request.Request(base + "/api/feedback", method="POST",
                                    data=json.dumps({"job_id": r["job_id"], "outcome": "ok"}).encode())
        assert json.load(urllib.request.urlopen(fb))["ok"]
    finally:
        srv.shutdown()
