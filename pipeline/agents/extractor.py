"""Agent 1: read the WHOLE paper (tables and appendix included) and build a very detailed sheet."""
import json

from pipeline import config
from pipeline import llm, prompts
SYSTEM = prompts.load("extractor")


def cite_key(f):
    authors = f.get("authors") or []
    names = []
    for a in authors[:3]:
        a = a.get("name", "") if isinstance(a, dict) else str(a)
        a = a.replace("∗", "").replace("†", "").replace("‡", "").strip()
        names.append(a.split()[-1] if a else "Unknown")
    year = f.get("year") or "n.d."
    if not names:
        return f"[Unknown, {year}]"
    if len(authors) >= 3:
        return f"[{names[0]} et al., {year}]"
    if len(authors) == 2:
        return f"[{names[0]} & {names[1]}, {year}]"
    return f"[{names[0]}, {year}]"


class ExtractError(RuntimeError):
    """Raised with --strict-extract when a sheet is incomplete."""


def _extract_one(pdf):
    for attempt in range(2):
        raw = llm.call(config.MODEL_FAST,
                       [llm.pdf_part(pdf), "Build the exhaustive sheet of this paper."],
                       SYSTEM, json_out=True, max_tokens=config.MAX_OUT_EXTRACT)
        try:
            return json.loads(raw), raw
        except json.JSONDecodeError:
            print(f"  invalid JSON (attempt {attempt + 1}/2)")
    return None, raw


def run(strict=False):
    config.ensure_dirs()
    for pdf in sorted(config.PAPERS_DIR.glob("*.pdf")):
        target = config.EXTRACTED_DIR / f"{pdf.stem}.json"
        if target.exists():
            print(f"[1] skipping {pdf.name} (already extracted)")
            continue
        print(f"[1] extracting in detail from {pdf.name}")
        data, raw = _extract_one(pdf)
        if data is None:
            (config.EXTRACTED_DIR / f"{pdf.stem}.raw.txt").write_text(raw, encoding="utf-8")
            msg = f"could not parse JSON for {pdf.name}; see .raw.txt"
            if strict:
                raise ExtractError(msg)
            print(f"  WARNING: {msg}")
            continue
        data["source_file"] = pdf.name
        data["cite_key"] = cite_key(data)
        data["extracted_by"] = llm.LAST_MODEL                    # which model produced this sheet
        cut = llm.LAST_MODEL is not None and not llm.LAST_MODEL.startswith("gemini") and llm.pdf_truncated(pdf)
        data["truncated"] = bool(cut)                            # fallback model saw only part of the text
        if cut:
            msg = f"{pdf.name} was TRUNCATED ({data['extracted_by']} saw only the first {llm.MAX_PDF_CHARS} chars)"
            if strict:
                raise ExtractError(msg + "; delete the sheet and re-run with a Gemini key or higher MAX_PDF_CHARS")
            print(f"  WARNING: {msg}")
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        words = len(json.dumps(data, ensure_ascii=False).split())
        print(f"  sheet saved ({words} words) -> {data['cite_key']}")


def load_all():
    """All sheets; duplicate cite keys get a/b/c suffixes in the year (e.g. [Yao et al., 2023b])."""
    fise, used = [], {}
    for p in sorted(config.EXTRACTED_DIR.glob("*.json")):
        f = json.loads(p.read_text(encoding="utf-8"))
        key = f.get("cite_key") or cite_key(f)
        n = used.get(key, 0)
        used[key] = n + 1
        if n:
            key = key[:-1] + chr(ord("a") + n) + "]"
        f["cite_key"] = key
        fise.append(f)
    return fise


def compact(f):
    """Short view of a sheet for the analyst: drops long prose, keeps numbers, claims and structure."""
    keep = ("cite_key", "title", "year", "venue", "problem_and_motivation", "contributions", "claims_table",
            "results", "limitations", "failure_modes", "key_claims", "related_work_positioning")
    out = {k: f[k] for k in keep if k in f}
    m = f.get("method") or {}
    out["method"] = {"overview": m.get("overview"), "components": [c.get("name") for c in m.get("components", [])],
                     "settings": m.get("settings")}
    out["datasets"] = [d.get("name") for d in (f.get("experiments") or {}).get("tasks_and_datasets", [])]
    for k in ("extracted_by", "truncated"):
        if k in f:
            out[k] = f[k]
    return out
