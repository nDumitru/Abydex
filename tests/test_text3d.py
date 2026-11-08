import io
import json
import threading
import urllib.request

import pytest

from forja3d import catalog, csg, templates, textcad, workflow
from forja3d.memory import Memory


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("FORJA3D_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FORJA3D_NO_UPDATE_CHECK", "1")
    monkeypatch.setattr(textcad, "ollama_models", lambda timeout=1.5: None)  # no LLM unless a test says so
    catalog.printers.cache_clear(); catalog.materials.cache_clear()
    yield tmp_path


# ---------------------------------------------------------------- CSG + templates
@pytest.mark.parametrize("name", list(templates.TEMPLATES))
def test_every_template_is_a_clean_solid(name):
    m = csg.build(templates.spec_for(name, {}))
    assert m.is_watertight and m.volume > 0
    expected_bodies = 2 if name == "box" else 1  # box = body + lid
    assert len(m.split(only_watertight=False)) == expected_bodies


def test_params_are_clamped_and_unknown_dropped():
    p = templates.clean_params("spacer", {"outer": 99999, "evil": 1, "height": "abc"})
    assert p["outer"] == 300 and "evil" not in p and p["height"] == 10


@pytest.mark.parametrize("spec,msg", [
    ({"box": [1, 2]}, "3 valori"), ({"exec": "import os"}, "necunoscut"), ({"box": [5000, 1, 1]}, "limitelor"),
    ({"difference": []}, "cel putin"), ({"cylinder": {"d": 5}}, "'h'"),
])
def test_csg_rejects_bad_input(spec, msg):
    with pytest.raises(csg.CSGError, match=msg):
        csg.build(spec)


def test_csg_node_limit():
    with pytest.raises(csg.CSGError, match="complex"):
        csg.build({"union": [{"box": [1, 1, 1]}] * 700})


def test_box_dimensions_and_holes():
    m = csg.build({"difference": [{"box": [40, 20, 10]}, {"cylinder": {"d": 5, "h": 12}, "move": [0, 0, -1]}]})
    assert list(m.extents.round(3)) == [40, 20, 10]
    assert m.volume == pytest.approx(40 * 20 * 10 - 3.14159 * 2.5 ** 2 * 10, rel=0.01)


# ---------------------------------------------------------------- rules parser
@pytest.mark.parametrize("text,tpl,expect", [
    ("cutie 80x50x30 cu capac, perete 2mm", "box", {"length": 80, "width": 50, "height": 30, "wall": 2, "lid": 1}),
    ("Carcasă Arduino 7x5.5x3 cm fără capac", "box", {"length": 70, "width": 55, "height": 30, "lid": 0}),
    ("box 120x80x40 with lid, wall 2.5", "box", {"length": 120, "wall": 2.5, "lid": 1}),
    ("suport L 50x40x20 cu găuri M4, grosime 5", "l_bracket", {"length": 50, "height": 40, "width": 20,
                                                                "thickness": 5, "hole": 4.5}),
    ("distanțier diametru 12 interior 5.5 înălțime 15", "spacer", {"outer": 12, "inner": 5.5, "height": 15}),
    ("saiba M8 grosime 2", "spacer", {"inner": 9.0, "outer": 18.0, "height": 2}),
    ("placa 100x60x3 cu 4 gauri M3", "plate", {"length": 100, "thickness": 3, "hole": 3.4, "holes_x": 2, "holes_y": 2}),
    ("cârlig de perete lățime 25 adâncime 40", "hook", {"width": 25, "depth": 40}),
    ("organizator 150x100x40 cu 4x3 compartimente", "tray", {"length": 150, "cells_x": 4, "cells_y": 3}),
])
def test_rules(text, tpl, expect):
    d = textcad.parse_rules(text)
    assert d["template"] == tpl
    for k, v in expect.items():
        assert d["params"][k] == pytest.approx(v), k


def test_organic_requests_are_not_forced_into_templates():
    assert textcad.parse_rules("o vaza decorativa cu flori") is None
    assert textcad.understand("o vaza decorativa cu flori")["organic"]
    with pytest.raises(ValueError):
        textcad.understand("o vaza decorativa cu flori", mode="technical")


# ---------------------------------------------------------------- LLM (mocked Ollama)
class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def _fake_ollama(monkeypatch, answer: dict | str):
    monkeypatch.setattr(textcad, "ollama_models", lambda timeout=1.5: ["qwen2.5-coder:3b"])
    seen = {}

    def urlopen(req, timeout=None):
        seen["body"] = json.loads(req.data)
        raw = answer if isinstance(answer, str) else json.dumps(answer)
        return _Resp(json.dumps({"response": raw}).encode())
    monkeypatch.setattr(textcad.urllib.request, "urlopen", urlopen)
    return seen


def test_llm_template_answer(monkeypatch):
    seen = _fake_ollama(monkeypatch, {"template": "spacer", "params": {"outer": 30, "inner": 8, "height": 4}})
    d = textcad.understand("un inel pentru rulment 608")
    assert d["source"] == "llm" and d["template"] == "spacer" and d["params"]["outer"] == 30
    assert seen["body"]["format"] == "json"


def test_llm_free_csg_answer(monkeypatch):
    _fake_ollama(monkeypatch, {"csg": {"difference": [{"cylinder": {"d": 40, "h": 5}},
                                                      {"ring": {"node": {"cylinder": {"d": 4, "h": 7}},
                                                                "count": 6, "radius": 14}, "move": [0, 0, -1]}]}})
    d = textcad.understand("flansa rotunda cu 6 gauri pe cerc")
    assert "csg" in d
    m = textcad.build_design(d)
    assert m.is_watertight and m.extents[0] == pytest.approx(40, abs=0.1)


def test_invalid_llm_output_falls_back_to_rules(monkeypatch):
    _fake_ollama(monkeypatch, {"csg": {"box": [1, 2]}})
    d = textcad.understand("cutie 60x40x20")
    assert d["source"] == "reguli" and d["params"]["length"] == 60
    assert any("nu a dat un raspuns valid" in n for n in d["notes"])
    _fake_ollama(monkeypatch, "asta nu e json")
    assert textcad.understand("cutie 60x40x20")["template"] == "box"


# ---------------------------------------------------------------- workflow + learning
def test_text_to_3d_job_and_reuse_of_good_designs():
    r = workflow.text_to_3d("placa 100x60x3 cu 4 gauri M3", "bambu_a1", "petg", 0.2, use_llm=False)
    assert r["analysis"]["dims_mm"] == [100.0, 60.0, 3.0]
    assert r["design"]["template"] == "plate"
    mem = Memory()
    assert mem.good_text_designs() == []          # no feedback yet -> nothing to reuse
    mem.add_feedback(r["job_id"], "ok", 5)
    good = mem.good_text_designs()
    mem.close()
    assert good[0]["prompt"] == "placa 100x60x3 cu 4 gauri M3"
    d = textcad.understand("Placă 100x60x3 cu 4 găuri M3", past=good)
    assert d["source"] == "memorie" and d["params"]["hole"] == 3.4


def test_user_edited_design_is_used():
    r = workflow.text_to_3d("cutie", "bambu_a1", "pla", design={"template": "box",
                            "params": {"length": 60, "width": 40, "height": 20, "lid": 0}})
    assert r["analysis"]["dims_mm"] == [60.0, 40.0, 20.0]


def test_organic_without_engines_gives_clear_error():
    with pytest.raises(RuntimeError, match="engine install sdturbo"):
        workflow.text_to_3d("o vaza decorativa", "bambu_a1", "pla", use_llm=False)


def test_web_text3d_api():
    from forja3d.webui.server import make_server
    srv = make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        cat = json.load(urllib.request.urlopen(base + "/api/catalog"))
        assert "tray" in cat["templates"]
        post = lambda path, d: json.load(urllib.request.urlopen(urllib.request.Request(
            base + path, data=json.dumps(d).encode(), method="POST", headers={"Content-Type": "application/json"})))
        d = post("/api/text/parse", {"text": "distantier 20x10"})
        assert d["template"] == "spacer" and d["params"]["outer"] == 20
        r = post("/api/text3d", {"text": "distantier 20x10", "printer": "bambu_a1", "material": "pla", "use_llm": False})
        assert r["design"]["template"] == "spacer" and r["analysis"]["dims_mm"][2] == 10
        with pytest.raises(urllib.error.HTTPError) as e:
            post("/api/text3d", {"text": "x", "printer": "bambu_a1", "material": "pla", "mode": "technical"})
        assert e.value.code == 400
    finally:
        srv.shutdown()
