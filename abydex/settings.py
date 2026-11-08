"""User settings (settings.json in the data folder): AI providers, models and API keys.

API keys are stored only on this computer, in the user's own data folder. An environment
variable (e.g. ANTHROPIC_API_KEY) always wins over the stored key.
"""
from __future__ import annotations

import json
import os
import sys

from .catalog import user_dir

# Text understanding (text -> CAD). "openai" kind = any OpenAI-compatible chat API.
# Model names of other vendors change often: they are only suggestions, editable in the UI.
LLM_PROVIDERS: dict[str, dict] = {
    "ollama": {"label": "Ollama (local, gratuit, offline)", "kind": "ollama", "model": "qwen2.5-coder:3b",
               "base_url": "http://127.0.0.1:11434", "env": None, "url": "https://ollama.com", "local": True},
    "llamafile": {"label": "llamafile / llama.cpp (local, gratuit, offline)", "kind": "openai", "model": "local",
                  "base_url": "http://127.0.0.1:8080/v1", "env": None, "local": True,
                  "url": "https://github.com/Mozilla-Ocho/llamafile"},
    "anthropic": {"label": "Anthropic Claude", "kind": "anthropic", "model": "claude-opus-5-5",
                  "env": "ANTHROPIC_API_KEY", "url": "https://console.anthropic.com/settings/keys"},
    "openai": {"label": "OpenAI", "kind": "openai", "model": "gpt-4.1-mini",
               "base_url": "https://api.openai.com/v1", "env": "OPENAI_API_KEY",
               "url": "https://platform.openai.com/api-keys"},
    "gemini": {"label": "Google Gemini", "kind": "openai", "model": "gemini-2.5-flash",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "env": "GEMINI_API_KEY",
               "url": "https://aistudio.google.com/apikey"},
    "mistral": {"label": "Mistral AI", "kind": "openai", "model": "mistral-small-latest",
                "base_url": "https://api.mistral.ai/v1", "env": "MISTRAL_API_KEY",
                "url": "https://console.mistral.ai/api-keys"},
    "deepseek": {"label": "DeepSeek", "kind": "openai", "model": "deepseek-chat",
                 "base_url": "https://api.deepseek.com/v1", "env": "DEEPSEEK_API_KEY",
                 "url": "https://platform.deepseek.com/api_keys"},
    "groq": {"label": "Groq", "kind": "openai", "model": "llama-3.3-70b-versatile",
             "base_url": "https://api.groq.com/openai/v1", "env": "GROQ_API_KEY",
             "url": "https://console.groq.com/keys"},
    "openrouter": {"label": "OpenRouter (multe modele)", "kind": "openai", "model": "openrouter/auto",
                   "base_url": "https://openrouter.ai/api/v1", "env": "OPENROUTER_API_KEY",
                   "url": "https://openrouter.ai/keys"},
    "custom": {"label": "Alt server compatibil OpenAI (LM Studio, vLLM...)", "kind": "openai", "model": "",
               "base_url": "http://127.0.0.1:1234/v1", "env": "ABYDEX_CUSTOM_API_KEY", "url": "", "local": True},
}

# Cloud text -> 3D for decorative objects (useful on PCs without a strong GPU).
CLOUD3D_PROVIDERS: dict[str, dict] = {
    "meshy": {"label": "Meshy", "env": "MESHY_API_KEY", "model": "latest", "url": "https://www.meshy.ai/api"},
    "tripo": {"label": "Tripo", "env": "TRIPO_API_KEY", "model": "v3.1-20260211",
              "url": "https://platform.tripo3d.ai/api-keys"},
}

DEFAULTS = {
    "llm": {"provider": "ollama", "model": "", "base_url": ""},
    "cloud3d": {"provider": "", "model": ""},
    "keys": {},
}


def _path():
    return user_dir() / "settings.json"


def load() -> dict:
    s = json.loads(json.dumps(DEFAULTS))
    p = _path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for k in ("llm", "cloud3d", "keys"):
                if isinstance(data.get(k), dict):
                    s[k].update(data[k])
        except (OSError, ValueError):
            pass
    return s


def save(s: dict) -> None:
    p = _path()
    p.write_text(json.dumps(s, indent=2), encoding="utf-8")
    if sys.platform != "win32":
        os.chmod(p, 0o600)  # keys: readable only by the user


def get_key(provider: str) -> str | None:
    info = LLM_PROVIDERS.get(provider) or CLOUD3D_PROVIDERS.get(provider) or {}
    env = info.get("env")
    if env and os.environ.get(env):
        return os.environ[env]
    return load()["keys"].get(provider) or None


def llm_config(s: dict | None = None) -> dict:
    """Effective text-AI config: provider info + chosen model/base_url + key."""
    s = s or load()
    pid = s["llm"].get("provider") or "ollama"
    info = LLM_PROVIDERS.get(pid, LLM_PROVIDERS["ollama"])
    return {"provider": pid, "kind": info["kind"], "label": info["label"], "local": bool(info.get("local")),
            "model": s["llm"].get("model") or info["model"],
            "base_url": (s["llm"].get("base_url") or info.get("base_url") or "").rstrip("/"),
            "key": get_key(pid)}


def cloud3d_config(s: dict | None = None) -> dict | None:
    s = s or load()
    pid = s["cloud3d"].get("provider")
    if not pid or pid not in CLOUD3D_PROVIDERS:
        return None
    return {"provider": pid, "model": s["cloud3d"].get("model") or CLOUD3D_PROVIDERS[pid]["model"],
            "key": get_key(pid)}


def public_view() -> dict:
    """Settings for the UI: keys are never sent back, only whether one is set."""
    s = load()
    key_set = {p: bool(get_key(p)) for p in list(LLM_PROVIDERS) + list(CLOUD3D_PROVIDERS)}
    return {"llm": s["llm"], "cloud3d": s["cloud3d"], "key_set": key_set,
            "llm_providers": {k: {kk: v[kk] for kk in ("label", "kind", "model", "url")} | {
                "base_url": v.get("base_url", ""), "local": bool(v.get("local")),
                "needs_key": not v.get("local")}
                for k, v in LLM_PROVIDERS.items()},
            "cloud3d_providers": {k: {kk: v[kk] for kk in ("label", "model", "url")}
                                  for k, v in CLOUD3D_PROVIDERS.items()}}


def update(changes: dict) -> dict:
    """changes: {"llm": {...}, "cloud3d": {...}, "keys": {provider: "sk-..." | "" (delete)}}"""
    s = load()
    for sect in ("llm", "cloud3d"):
        for k, v in (changes.get(sect) or {}).items():
            if k in DEFAULTS[sect]:
                s[sect][k] = str(v or "").strip()
    for prov, key in (changes.get("keys") or {}).items():
        if prov not in LLM_PROVIDERS and prov not in CLOUD3D_PROVIDERS:
            continue
        key = (key or "").strip()
        if key:
            s["keys"][prov] = key
        else:
            s["keys"].pop(prov, None)
    if s["llm"]["provider"] not in LLM_PROVIDERS:
        s["llm"]["provider"] = "ollama"
    save(s)
    return public_view()
