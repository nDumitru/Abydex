import io
import json
import types
import urllib.error

import pytest
import trimesh

from abydex import catalog, cloud3d, llm, settings, textcad, workflow


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("ABYDEX_HOME", str(tmp_path / "home"))
    for env in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "MESHY_API_KEY", "TRIPO_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(llm, "ollama_models", lambda *a, **k: None)
    yield tmp_path


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


# ---------------------------------------------------------------- settings
def test_keys_are_stored_locally_but_never_shown():
    v = settings.update({"llm": {"provider": "openai", "model": "gpt-x"}, "keys": {"openai": "sk-secret"}})
    assert v["key_set"]["openai"] is True
    assert "sk-secret" not in json.dumps(v)
    cfg = settings.llm_config()
    assert cfg["key"] == "sk-secret" and cfg["model"] == "gpt-x" and cfg["base_url"] == "https://api.openai.com/v1"
    settings.update({"keys": {"openai": ""}})          # empty = delete
    assert settings.llm_config()["key"] is None


def test_env_var_wins_and_unknown_provider_is_ignored(monkeypatch):
    settings.update({"llm": {"provider": "anthropic"}, "keys": {"anthropic": "stored", "evil": "x"}})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert settings.llm_config()["key"] == "from-env"
    assert "evil" not in settings.load()["keys"]
    settings.update({"llm": {"provider": "nope"}})
    assert settings.llm_config()["provider"] == "ollama"


def test_default_model_used_when_empty():
    settings.update({"llm": {"provider": "anthropic", "model": ""}})
    assert settings.llm_config()["model"] == "claude-opus-5-5"


# ---------------------------------------------------------------- OpenAI-compatible providers
@pytest.mark.parametrize("provider,url", [
    ("openai", "https://api.openai.com/v1/chat/completions"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"),
    ("mistral", "https://api.mistral.ai/v1/chat/completions"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions"),
])
def test_openai_compatible_request(monkeypatch, provider, url):
    settings.update({"llm": {"provider": provider}, "keys": {provider: "k-123"}})
    seen = {}

    def urlopen(req, timeout=None):
        seen["url"], seen["headers"], seen["body"] = req.full_url, dict(req.header_items()), json.loads(req.data)
        answer = {"template": "spacer", "params": {"outer": 25, "inner": 8, "height": 6}}
        return _Resp(json.dumps({"choices": [{"message": {"content": "```json\n" + json.dumps(answer) + "\n```"}}]}).encode())
    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    d = textcad.understand("inel pentru rulment")
    assert seen["url"] == url
    assert seen["headers"]["Authorization"] == "Bearer k-123"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert d["template"] == "spacer" and d["params"]["outer"] == 25 and d["source"].startswith("llm (")


def test_bad_key_falls_back_to_rules(monkeypatch):
    settings.update({"llm": {"provider": "openai"}, "keys": {"openai": "wrong"}})

    def urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error":"bad key"}'))
    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    d = textcad.understand("cutie 60x40x20")
    assert d["source"] == "reguli" and d["params"]["length"] == 60
    assert any("invalida" in n for n in d["notes"])


def test_no_key_means_no_request(monkeypatch):
    settings.update({"llm": {"provider": "openai"}})
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *a, **k: pytest.fail("no request expected"))
    assert textcad.understand("cutie 60x40x20")["source"] == "reguli"


# ---------------------------------------------------------------- Anthropic (official SDK, mocked)
def test_anthropic_structured_output(monkeypatch):
    import anthropic
    settings.update({"llm": {"provider": "anthropic"}, "keys": {"anthropic": "sk-ant-test"}})
    seen = {}

    class FakeClient:
        def __init__(self, api_key=None):
            seen["api_key"] = api_key
            self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=self.create))

        def create(self, **kw):
            seen.update(kw)
            env = {"kind": "csg", "template": "", "params_json": "{}",
                   "csg_json": json.dumps({"difference": [{"cylinder": {"d": 40, "h": 5}},
                                                          {"cylinder": {"d": 10, "h": 7}, "move": [0, 0, -1]}]})}
            return types.SimpleNamespace(stop_reason="end_turn",
                                         content=[types.SimpleNamespace(type="text", text=json.dumps(env))])
    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    d = textcad.understand("flansa rotunda 40 mm cu gaura de 10")
    assert "csg" in d and "Claude" in d["source"]
    assert seen["api_key"] == "sk-ant-test" and seen["model"] == "claude-opus-5-5"
    assert seen["output_config"]["format"]["type"] == "json_schema"
    assert seen["fallbacks"] == "default" and seen["betas"] == ["server-side-fallback-2026-07-01"]
    assert textcad.build_design(d).is_watertight


def test_anthropic_refusal_is_an_error(monkeypatch):
    import anthropic

    class FakeClient:
        def __init__(self, api_key=None):
            self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(
                create=lambda **kw: types.SimpleNamespace(stop_reason="refusal", content=[])))
    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    settings.update({"llm": {"provider": "anthropic"}, "keys": {"anthropic": "k"}})
    with pytest.raises(llm.LLMError, match="refuzat"):
        llm.complete_json("s", "u")


def test_envelope_conversion():
    assert llm.from_envelope({"kind": "organic", "template": "", "params_json": "{}", "csg_json": "{}"}) == {"organic": True}
    assert llm.from_envelope({"kind": "template", "template": "box", "params_json": '{"length": 10}',
                              "csg_json": "{}"}) == {"template": "box", "params": {"length": 10}}
    assert llm.from_envelope({"template": "box"}) == {"template": "box"}


# ---------------------------------------------------------------- cloud 3D (mocked HTTP)
def _sphere_glb(path):
    trimesh.creation.icosphere(radius=0.5).export(path)
    return path


def test_meshy_flow(monkeypatch, tmp_path):
    calls = []
    states = iter([{"status": "IN_PROGRESS", "progress": 40},
                   {"status": "SUCCEEDED", "progress": 100, "model_urls": {"glb": "https://cdn/x.glb"}}])

    def req(method, url, key, body=None, timeout=60):
        calls.append((method, url, body))
        return {"result": "task1"} if method == "POST" else next(states)
    monkeypatch.setattr(cloud3d, "_req", req)
    monkeypatch.setattr(cloud3d, "_download", lambda url, out: _sphere_glb(out))
    monkeypatch.setattr(cloud3d, "POLL_SECONDS", 0)
    out = cloud3d.text_to_3d("a small dragon", tmp_path / "d", {"provider": "meshy", "model": "latest", "key": "m"},
                             log=lambda m: None)
    assert out.suffix == ".glb" and out.exists()
    assert calls[0] == ("POST", "https://api.meshy.ai/openapi/v2/text-to-3d",
                        {"mode": "preview", "prompt": "a small dragon", "target_formats": ["glb"]})
    assert calls[1][1].endswith("/text-to-3d/task1")


def test_tripo_failure_message(monkeypatch, tmp_path):
    def req(method, url, key, body=None, timeout=60):
        if method == "POST":
            assert url.endswith("/v3/generation/text-to-model") and body["model"]
            return {"code": 0, "data": {"task_id": "t9"}}
        return {"data": {"status": "banned"}}
    monkeypatch.setattr(cloud3d, "_req", req)
    with pytest.raises(cloud3d.Cloud3DError, match="banned"):
        cloud3d.text_to_3d("x", tmp_path / "t", {"provider": "tripo", "model": "v3.1-20260211", "key": "k"},
                           log=lambda m: None)


def test_organic_text_uses_cloud_when_configured(monkeypatch):
    settings.update({"cloud3d": {"provider": "meshy"}, "keys": {"meshy": "m-key"}})
    monkeypatch.setattr(cloud3d, "text_to_3d", lambda prompt, out, cfg, log=print: _sphere_glb(out))
    r = workflow.text_to_3d("o vaza decorativa", "bambu_a1", "pla", use_llm=False, size_mm=80)
    assert r["design"]["source"] == "cloud (meshy)"
    assert max(r["analysis"]["dims_mm"]) == pytest.approx(80, abs=0.5)


# ---------------------------------------------------------------- rename: data of the old app is kept
def test_old_forja3d_data_is_copied(tmp_path, monkeypatch):
    monkeypatch.delenv("ABYDEX_HOME")
    monkeypatch.delenv("FORJA3D_HOME", raising=False)
    old = tmp_path / "Forja3D"
    old.mkdir()
    (old / "forja3d.db").write_bytes(b"x")
    monkeypatch.setattr(catalog, "_default_dir", lambda app: tmp_path / app)
    new = catalog.user_dir()
    assert new == tmp_path / "Abydex" and (new / "forja3d.db").exists()
    assert (old / "forja3d.db").exists()                 # the old folder is left untouched


def test_old_database_is_picked_up(home):
    import sqlite3
    from abydex.memory import Memory
    d = catalog.user_dir()
    con = sqlite3.connect(d / "forja3d.db")
    con.execute("CREATE TABLE marker(x)"); con.commit(); con.close()
    m = Memory()
    assert m.path.name == "abydex.db"
    assert m.db.execute("SELECT name FROM sqlite_master WHERE name='marker'").fetchone()
    m.close()
