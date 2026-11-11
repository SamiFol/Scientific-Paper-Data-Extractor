"""Multi-provider LLM wrapper: Gemini + OpenAI-compatible APIs (Claude, Groq, Cerebras, Mistral, OpenRouter).
Retry, pause between calls and fallback across models/providers."""
import os
import random
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pipeline import config
# provider -> (key env var, OpenAI-compatible base_url; None = native Gemini SDK)
PROVIDERS = {
    "gemini":     ("GEMINI_API_KEY", None),
    "groq":       ("GROQ_API_KEY", "https://api.groq.com/openai/v1"),
    "cerebras":   ("CEREBRAS_API_KEY", "https://api.cerebras.ai/v1"),
    "mistral":    ("MISTRAL_API_KEY", "https://api.mistral.ai/v1"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
    "anthropic":  ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/"),   # Claude via the OpenAI-compatible endpoint
}

RETRYABLE = (408, 429, 500, 502, 503, 504)
ROUNDS = 4  # passes over the model list
MAX_PDF_CHARS = getattr(config, "MAX_PDF_CHARS", 60_000)  # PDF text limit for non-Gemini

_clients = {}
LAST_MODEL = None   # "provider:model" that answered the most recent call


@dataclass
class PdfDoc:
    path: Path


def pdf_part(path):
    """Mark a PDF; each provider converts it its own way."""
    return PdfDoc(Path(path))


def _parse(spec):
    """'groq:llama-3.3-70b-versatile' -> ('groq', 'llama-3.3-70b-versatile'). No prefix = gemini."""
    provider, sep, name = spec.partition(":")
    if not sep or provider not in PROVIDERS:
        return "gemini", spec
    return provider, name


def _norm(spec):
    """Canonical 'provider:model' (so 'gemini-x' and 'gemini:gemini-x' are the same model)."""
    provider, name = _parse(spec)
    return f"{provider}:{name}"


def _key(provider):
    env = PROVIDERS[provider][0]
    return getattr(config, env, None) or os.getenv(env)


def _client(provider):
    if provider not in _clients:
        if provider == "gemini":
            from google import genai
            _clients[provider] = genai.Client(api_key=_key(provider))
        else:
            from openai import OpenAI
            # max_retries=0: we retry ourselves
            _clients[provider] = OpenAI(api_key=_key(provider), base_url=PROVIDERS[provider][1],
                                        max_retries=0, timeout=180)
    return _clients[provider]


def _api_errors():
    """API/network errors we handle (anything else is a bug and should crash)."""
    errs = []
    try:
        from google.genai import errors
        errs.append(errors.APIError)
    except ImportError:
        pass
    try:
        import openai
        errs.append(openai.APIError)
    except ImportError:
        pass
    try:
        import httpx
        errs.append(httpx.TransportError)
    except ImportError:
        pass
    return tuple(errs)


def _status(e):
    return getattr(e, "status_code", None) or getattr(e, "code", None)


@lru_cache(maxsize=64)
def _pdf_text(path):
    from pypdf import PdfReader
    text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    return text[:MAX_PDF_CHARS]


def pdf_truncated(path):
    """True if a non-Gemini provider would only see part of this PDF's text."""
    from pypdf import PdfReader
    return sum(len(p.extract_text() or "") for p in PdfReader(str(path)).pages) > MAX_PDF_CHARS


def _items(contents):
    return contents if isinstance(contents, list) else [contents]


def _out_cap(provider, max_tokens):
    """Non-Gemini providers have lower output caps; clamp to MAX_OUT_OTHER."""
    if max_tokens is None or provider == "gemini":
        return max_tokens
    return min(max_tokens, getattr(config, "MAX_OUT_OTHER", 12000))


def _call_gemini(model, contents, system, json_out, max_tokens, temperature):
    from google.genai import types
    parts = [types.Part.from_bytes(data=c.path.read_bytes(), mime_type="application/pdf")
             if isinstance(c, PdfDoc) else c for c in _items(contents)]
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json" if json_out else "text/plain",
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    return _client("gemini").models.generate_content(model=model, contents=parts, config=cfg).text


def _call_openai(provider, model, contents, system, json_out, max_tokens, temperature):
    # PDF -> locally extracted text (these APIs take no PDF)
    chunks = [f"--- PDF: {c.path.name} ---\n{_pdf_text(str(c.path))}" if isinstance(c, PdfDoc)
              else str(c) for c in _items(contents)]
    sys_msg = (system or "") + ("\nRespond ONLY with valid JSON, no extra text." if json_out else "")
    kwargs = {}
    cap = _out_cap(provider, max_tokens) or (8192 if provider == "anthropic" else None)   # Claude needs a cap
    if cap:
        # Cerebras uses max_completion_tokens; the others take max_tokens
        kwargs["max_completion_tokens" if provider == "cerebras" else "max_tokens"] = cap
    r = _client(provider).chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": sys_msg},
                  {"role": "user", "content": "\n\n".join(chunks)}],
        temperature=temperature,
        **kwargs,
    )
    return r.choices[0].message.content


def _clean(text, json_out):
    """Strip ```json fences and any text around the JSON object."""
    text = text.strip()
    if json_out:
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]
    return text


def call(model, contents, system, json_out=False, max_tokens=None, temperature=0.3):
    # model list without duplicates (compare canonical provider:model)
    models, seen = [], set()
    for m in [model] + list(config.FALLBACK_MODELS):
        k = _norm(m)
        if k not in seen:
            seen.add(k)
            models.append(k)
    models = [m for m in models if _key(_parse(m)[0])]  # skip providers without a key
    if not models:
        raise RuntimeError("No API key set for any model in config.")

    errors = _api_errors()
    dead = set()  # models with config errors (400/401/403/404/413): do not retry

    for rnd in range(ROUNDS):
        for m in models:
            if m in dead:
                continue
            provider, name = _parse(m)
            try:
                if provider == "gemini":
                    text = _call_gemini(name, contents, system, json_out, max_tokens, temperature)
                else:
                    text = _call_openai(provider, name, contents, system, json_out,
                                        max_tokens, temperature)
                if not text:
                    print(f"  [{m}] empty response")
                    continue
                global LAST_MODEL
                LAST_MODEL = m
                time.sleep(config.PAUSE_SECONDS)
                return _clean(text, json_out)
            except errors as e:
                code = _status(e)  # None = network error -> retry
                print(f"  [{m}] API error {code}")
                if code is not None and code not in RETRYABLE:
                    print(f"  {m} excluded: {str(e)[:150]}")
                    dead.add(m)
                time.sleep(3 + random.random() * 3)  # short pause between models

        if len(dead) == len(models):
            raise RuntimeError("All models have configuration errors (key, model name, "
                               "context too large). See the messages above.")
        wait = 30 * (rnd + 1)
        print(f"  round {rnd + 1}/{ROUNDS} failed, waiting {wait}s...")
        time.sleep(wait)

    raise RuntimeError("All models are unavailable right now. Run again later.")
