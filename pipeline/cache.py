"""Input hash + --fresh: detect stale derived files (analysis, sections, draft) after the inputs change."""
import json
import shutil

from pipeline import config
from pipeline.common import sha256

HASH_FILE_NAME = "input_hash.json"


def _read(p):
    return p.read_text(encoding="utf-8") if p and p.exists() else ""


def input_state(topic="", name=None, paper_type=None):
    """Everything that should invalidate analysis/sections when it changes."""
    pdfs = sorted((p.name, p.stat().st_size) for p in config.PAPERS_DIR.glob("*.pdf"))
    return {"pdfs": pdfs, "plan": sha256(_read(config.PLAN_FILE)), "status": sha256(_read(config.STATUS_FILE)),
            "topic": topic, "name": name or config.FRAMEWORK_NAME, "type": paper_type or config.PAPER_TYPE}


def digest(state):
    return sha256(json.dumps(state, sort_keys=True))


def hash_path():
    return config.OUT_DIR / HASH_FILE_NAME


def check(topic=""):
    """Return True if inputs changed since the derived files were built (and print a warning)."""
    new = digest(input_state(topic))
    hp = hash_path()
    old = json.loads(hp.read_text(encoding="utf-8")).get("hash") if hp.exists() else None
    derived = config.ANALYSIS_FILE.exists() or any(config.SECTIONS_DIR.glob("*.md"))
    changed = bool(old) and old != new and derived
    if changed:
        print("[cache] WARNING: inputs changed since the last run (PDFs, plan.txt, status, topic, name or type). "
              "analysis.json and sections/ may be stale; re-run with --fresh.")
    return changed


def save(topic=""):
    config.OUT_DIR.mkdir(parents=True, exist_ok=True)
    hash_path().write_text(json.dumps({"hash": digest(input_state(topic))}), encoding="utf-8")


def fresh():
    """Delete derived files (keeps extracted sheets, which cost the most to produce)."""
    config.ANALYSIS_FILE.unlink(missing_ok=True)
    config.DRAFT_FILE.unlink(missing_ok=True)
    config.REVIEW_FILE.unlink(missing_ok=True)
    shutil.rmtree(config.SECTIONS_DIR, ignore_errors=True)
    config.SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    hash_path().unlink(missing_ok=True)
    print("[cache] --fresh: removed analysis.json, sections/, paper_draft.md, review.json (sheets kept)")
