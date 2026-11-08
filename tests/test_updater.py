import hashlib
import json
import threading
import urllib.request

import pytest

from abydex import updates


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("ABYDEX_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("ABYDEX_NO_UPDATE_CHECK", raising=False)
    updates.STATE.update(stage="idle", progress=0, message="")
    yield tmp_path


SETUP = b"fake installer bytes" * 1000
GOOD_SUMS = f"{hashlib.sha256(SETUP).hexdigest()}  Abydex-Setup-9.9.9.exe\n0000  abydex-9.9.9.tar.gz\n"
INFO = {"latest": "v9.9.9", "url": "https://github.com/nDumitru/abydex/releases/tag/v9.9.9",
        "assets": {"Abydex-Setup-9.9.9.exe": "https://github.com/nDumitru/abydex/releases/download/v9.9.9/Abydex-Setup-9.9.9.exe",
                   "SHA256SUMS.txt": "https://github.com/nDumitru/abydex/releases/download/v9.9.9/SHA256SUMS.txt"}}


def _fake_fetch(sums=GOOD_SUMS, payload=SETUP):
    def fetch(url, dest=None, progress=None):
        if url.endswith("SHA256SUMS.txt"):
            return sums.encode()
        dest.write_bytes(payload)
        if progress:
            progress(100)
        return dest
    return fetch


def test_checksum_parsing():
    assert updates.expected_sum("abc  file.exe\ndef *other.whl\n", "other.whl") == "def"
    assert updates.expected_sum("abc  file.exe", "missing") is None


def test_dev_checkout_is_not_auto_updated():
    assert updates.install_kind() == "source"
    with pytest.raises(RuntimeError, match="sursa"):
        updates.download_update(INFO)


def test_verified_download(monkeypatch):
    monkeypatch.setattr(updates, "install_kind", lambda: "windows")
    monkeypatch.setattr(updates, "_fetch", _fake_fetch())
    path = updates.download_update(INFO)
    assert path.name == "Abydex-Setup-9.9.9.exe" and path.read_bytes() == SETUP


def test_tampered_download_is_rejected(monkeypatch):
    monkeypatch.setattr(updates, "install_kind", lambda: "windows")
    monkeypatch.setattr(updates, "_fetch", _fake_fetch(payload=b"evil"))
    with pytest.raises(RuntimeError, match="sumei de control"):
        updates.download_update(INFO)


def test_release_without_checksums_is_not_installed(monkeypatch):
    monkeypatch.setattr(updates, "install_kind", lambda: "windows")
    info = {**INFO, "assets": {k: v for k, v in INFO["assets"].items() if k != "SHA256SUMS.txt"}}
    with pytest.raises(RuntimeError, match="suma de control"):
        updates.download_update(info)


def test_only_github_urls():
    with pytest.raises(RuntimeError, match="GitHub"):
        updates._fetch("https://evil.example.com/Abydex-Setup.exe")


def test_check_reports_installable_update(monkeypatch):
    rel = {"tag_name": "v9.9.9", "html_url": INFO["url"], "body": "nou",
           "assets": [{"name": k, "browser_download_url": v} for k, v in INFO["assets"].items()]}

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self, *a): return json.dumps(rel).encode()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: R())
    monkeypatch.setattr(updates, "install_kind", lambda: "windows")
    r = updates.check(force=True)
    assert r["update_available"] and r["can_install"] and r["install_kind"] == "windows"
    monkeypatch.setattr(updates, "install_kind", lambda: "source")
    assert updates.check()["can_install"] is False          # cached data, but a dev checkout


def test_windows_install_runs_silent_setup_then_exits(monkeypatch):
    monkeypatch.setattr(updates, "install_kind", lambda: "windows")
    monkeypatch.setattr(updates, "_fetch", _fake_fetch())
    started, exited = {}, threading.Event()
    monkeypatch.setattr(updates.subprocess, "Popen", lambda args, **kw: started.update(args=args, kw=kw))
    updates.start_install(INFO, exit_app=exited.set)
    assert exited.wait(10), updates.STATE
    assert started["args"][0].endswith("Abydex-Setup-9.9.9.exe")
    assert "/SILENT" in started["args"] and "/AUTOSTART=1" in started["args"]
    assert updates.STATE["stage"] == "installing"


def test_failed_install_reports_error(monkeypatch):
    monkeypatch.setattr(updates, "install_kind", lambda: "windows")
    monkeypatch.setattr(updates, "_fetch", _fake_fetch(sums="nothing here"))
    updates.start_install(INFO, exit_app=lambda: pytest.fail("must not exit"))
    for _ in range(100):
        if updates.STATE["stage"] == "error":
            break
        threading.Event().wait(0.05)
    assert updates.STATE["stage"] == "error" and "lipseste" in updates.STATE["message"]


def test_app_is_the_default_command():
    from abydex.cli import build_parser
    a = build_parser().parse_args(["app", "--mode", "browser"])
    assert a.fn.__name__ == "cmd_app" and a.mode == "browser"


def test_desktop_server_starts_on_free_port():
    import socket
    from abydex import desktop
    busy = socket.socket(); busy.bind(("127.0.0.1", 0)); port = busy.getsockname()[1]; busy.listen()
    srv, url = desktop._start_server(port)          # port taken -> next one
    try:
        assert url != f"http://127.0.0.1:{port}/"
        assert b"Abydex" in urllib.request.urlopen(url, timeout=5).read()
    finally:
        srv.shutdown(); busy.close()
