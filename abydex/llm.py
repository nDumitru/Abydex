"""Text AI providers. One function: complete_json(system, user) -> dict.

- Ollama (local)                      -> /api/chat with format=json
- Anthropic Claude                    -> official `anthropic` SDK, structured outputs (JSON schema)
- OpenAI, Gemini, Mistral, DeepSeek,
  Groq, OpenRouter, LM Studio...      -> OpenAI-compatible /chat/completions with JSON mode

Whatever the provider answers is treated as data and validated by the caller.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from . import settings

TIMEOUT = 300

# Claude: the CAD tree is recursive and recursive schemas are not supported by structured
# outputs, so the answer comes in a flat envelope with the nested parts as JSON strings.
ENVELOPE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["template", "csg", "organic"]},
        "template": {"type": "string", "description": "template name when kind=template, else empty"},
        "params_json": {"type": "string", "description": "JSON object with template params, else {}"},
        "csg_json": {"type": "string", "description": "JSON CSG tree when kind=csg, else {}"},
    },
    "required": ["kind", "template", "params_json", "csg_json"],
    "additionalProperties": False,
}


class LLMError(RuntimeError):
    pass


def _http_json(url: str, body: dict, headers: dict, timeout: float = TIMEOUT) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            raise LLMError(f"Cheia API e invalida sau nu are acces ({e.code}). {detail}")
        if e.code == 429:
            raise LLMError("Limita de cereri / credit epuizat la furnizor (429). Incearca mai tarziu.")
        raise LLMError(f"Furnizorul AI a raspuns cu eroare {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise LLMError(f"Nu pot contacta furnizorul AI: {e.reason}")


def parse_json_text(text: str) -> dict:
    """JSON from model text (tolerates ```json fences or text around the object)."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def from_envelope(d: dict) -> dict:
    """Envelope (Claude structured output) -> the plain answer format used everywhere else."""
    if "kind" not in d:
        return d
    if d["kind"] == "organic":
        return {"organic": True}
    if d["kind"] == "template":
        return {"template": d.get("template", ""), "params": json.loads(d.get("params_json") or "{}")}
    return {"csg": json.loads(d.get("csg_json") or "{}")}


def available(cfg: dict | None = None) -> bool:
    cfg = cfg or settings.llm_config()
    if cfg["kind"] == "ollama":
        return ollama_models(cfg["base_url"]) is not None
    if cfg["provider"] == "custom":
        return bool(cfg["base_url"] and cfg["model"])
    return bool(cfg["key"])


def ollama_models(base_url: str = "http://127.0.0.1:11434", timeout: float = 1.5) -> list[str] | None:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=timeout) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return None


def complete_json(system: str, user: str, cfg: dict | None = None) -> dict:
    cfg = cfg or settings.llm_config()
    kind = cfg["kind"]
    if kind == "ollama":
        r = _http_json(cfg["base_url"] + "/api/chat", {
            "model": cfg["model"], "stream": False, "format": "json",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0.1}}, {})
        return parse_json_text(r.get("message", {}).get("content", ""))
    if kind == "anthropic":
        return from_envelope(_anthropic(system, user, cfg))
    if kind == "openai":
        if not cfg["key"] and cfg["provider"] != "custom":
            raise LLMError(f"Lipseste cheia API pentru {cfg['label']} (Setari AI).")
        headers = {"Authorization": f"Bearer {cfg['key']}"} if cfg["key"] else {}
        if cfg["provider"] == "openrouter":
            headers |= {"HTTP-Referer": "https://github.com/nDumitru/abydex", "X-Title": "Abydex"}
        r = _http_json(cfg["base_url"] + "/chat/completions", {
            "model": cfg["model"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"}}, headers)
        try:
            return parse_json_text(r["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"Raspuns neasteptat de la {cfg['label']}.")
    raise LLMError(f"Furnizor necunoscut: {cfg['provider']}")


def _anthropic(system: str, user: str, cfg: dict) -> dict:
    try:
        import anthropic
    except ImportError:
        raise LLMError("Pachetul 'anthropic' nu e instalat (pip install anthropic).")
    client = anthropic.Anthropic(api_key=cfg["key"]) if cfg["key"] else anthropic.Anthropic()
    try:
        resp = client.beta.messages.create(
            model=cfg["model"],
            max_tokens=16000,
            system=system + "\n\nRaspunsul tau trece printr-un plic JSON: kind = template | csg | organic; "
                            "template = numele sablonului (sau \"\"); params_json = obiectul params ca text JSON "
                            "(sau \"{}\"); csg_json = arborele csg ca text JSON (sau \"{}\").",
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": ENVELOPE_SCHEMA}},
            # if a safety classifier declines, the API retries on a suitable fallback model
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        raise LLMError("Cheia API Anthropic e invalida.")
    except anthropic.PermissionDeniedError:
        raise LLMError("Cheia API Anthropic nu are acces la acest model.")
    except anthropic.NotFoundError:
        raise LLMError(f"Modelul '{cfg['model']}' nu exista la Anthropic.")
    except anthropic.RateLimitError:
        raise LLMError("Limita de cereri / credit epuizat la Anthropic. Incearca mai tarziu.")
    except anthropic.APIStatusError as e:
        raise LLMError(f"Eroare Anthropic {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise LLMError("Nu pot contacta Anthropic (verifica internetul).")
    if resp.stop_reason == "refusal":
        raise LLMError("Modelul a refuzat cererea.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)
