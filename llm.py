"""Wrapper LLM multi-provider: Gemini + API-uri compatibile OpenAI (Groq, Cerebras, Mistral, OpenRouter).
Retry, pauza intre apeluri si fallback intre modele/provideri."""
import os
import random
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import config

# provider -> (variabila cu cheia, base_url compatibil OpenAI; None = SDK Gemini nativ)
PROVIDERS = {
    "gemini":     ("GEMINI_API_KEY", None),
    "groq":       ("GROQ_API_KEY", "https://api.groq.com/openai/v1"),
    "cerebras":   ("CEREBRAS_API_KEY", "https://api.cerebras.ai/v1"),
    "mistral":    ("MISTRAL_API_KEY", "https://api.mistral.ai/v1"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
}

RETRYABLE = (408, 429, 500, 502, 503, 504)
ROUNDS = 4  # de cate ori parcurgem lista de modele
MAX_PDF_CHARS = getattr(config, "MAX_PDF_CHARS", 60_000)  # limita text PDF pt. non-Gemini

_clients = {}


@dataclass
class PdfDoc:
    path: Path


def pdf_part(path):
    """Marcheaza un PDF; fiecare provider il converteste cum stie."""
    return PdfDoc(Path(path))


def _parse(spec):
    """'groq:llama-3.3-70b-versatile' -> ('groq', 'llama-3.3-70b-versatile'). Fara prefix = gemini."""
    provider, sep, name = spec.partition(":")
    if not sep or provider not in PROVIDERS:
        return "gemini", spec
    return provider, name


def _norm(spec):
    """Forma canonica 'provider:model' (ca 'gemini-x' si 'gemini:gemini-x' sa fie acelasi model)."""
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
            # max_retries=0: retry-ul il facem noi
            _clients[provider] = OpenAI(api_key=_key(provider), base_url=PROVIDERS[provider][1],
                                        max_retries=0, timeout=180)
    return _clients[provider]


def _api_errors():
    """Erorile de API/retea pe care le tratam (restul = bug in cod, le lasam sa crape)."""
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


def _items(contents):
    return contents if isinstance(contents, list) else [contents]


def _out_cap(provider, max_tokens):
    """Providerii non-Gemini au plafoane de output mai mici; taiem cererea la MAX_OUT_OTHER."""
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
    # PDF -> text extras local (API-urile astea nu primesc PDF direct)
    chunks = [f"--- PDF: {c.path.name} ---\n{_pdf_text(str(c.path))}" if isinstance(c, PdfDoc)
              else str(c) for c in _items(contents)]
    sys_msg = (system or "") + ("\nRespond ONLY with valid JSON, no extra text." if json_out else "")
    kwargs = {}
    cap = _out_cap(provider, max_tokens)
    if cap:
        # Cerebras foloseste max_completion_tokens; ceilalti accepta max_tokens
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
    """Scoate ```json ... ``` si textul din jurul obiectului JSON, daca modelul le-a pus."""
    text = text.strip()
    if json_out:
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]
    return text


def call(model, contents, system, json_out=False, max_tokens=None, temperature=0.3):
    # lista de modele, fara dubluri (comparam forma canonica provider:model)
    models, seen = [], set()
    for m in [model] + list(config.FALLBACK_MODELS):
        k = _norm(m)
        if k not in seen:
            seen.add(k)
            models.append(k)
    models = [m for m in models if _key(_parse(m)[0])]  # sarim providerii fara cheie
    if not models:
        raise RuntimeError("Nicio cheie API setata pentru modelele din config.")

    errors = _api_errors()
    dead = set()  # modele cu eroare de config (400/401/403/404/413), nu le mai incercam

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
                    print(f"  [{m}] raspuns gol")
                    continue
                time.sleep(config.PAUSE_SECONDS)
                return _clean(text, json_out)
            except errors as e:
                code = _status(e)  # None = eroare de retea -> reincercam
                print(f"  [{m}] API error {code}")
                if code is not None and code not in RETRYABLE:
                    print(f"  {m} exclus: {str(e)[:150]}")
                    dead.add(m)
                time.sleep(3 + random.random() * 3)  # pauza scurta intre modele

        if len(dead) == len(models):
            raise RuntimeError("Toate modelele au erori de configurare (cheie, nume model, "
                               "context prea mare). Vezi mesajele de mai sus.")
        wait = 30 * (rnd + 1)
        print(f"  runda {rnd + 1}/{ROUNDS} esuata, astept {wait}s...")
        time.sleep(wait)

    raise RuntimeError("Toate modelele sunt indisponibile acum. Ruleaza din nou mai tarziu.")