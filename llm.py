"""Wrapper peste Gemini API: retry, pauza intre apeluri si fallback intre modele."""
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

import config

_client = genai.Client(api_key=config.GEMINI_API_KEY)

RETRYABLE = (429, 500, 502, 503, 504)


def call(model, contents, system, json_out=False, attempts_per_model=3):
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json" if json_out else "text/plain",
        temperature=0.3,
    )
    models = [model] + [m for m in config.FALLBACK_MODELS if m != model]

    for m in models:
        for attempt in range(attempts_per_model):
            try:
                r = _client.models.generate_content(model=m, contents=contents, config=cfg)
                time.sleep(config.PAUSE_SECONDS)
                return r.text
            except genai_errors.APIError as e:
                code = getattr(e, "code", None)
                print(f"  [{m}] API error {code}: {str(e)[:200]}")
                if code not in RETRYABLE:
                    break  # eroare de config (404/400/403): treci la urmatorul model
                wait = 10 * (attempt + 1)
                print(f"  reincerc in {wait}s...")
                time.sleep(wait)
        print(f"  trec la alt model (am renuntat la {m})")

    raise RuntimeError("Toate modelele au esuat. Incearca mai tarziu sau schimba modelele din .env")


def pdf_part(path):
    return types.Part.from_bytes(data=path.read_bytes(), mime_type="application/pdf")