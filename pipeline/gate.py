"""Blocking quality gate: runs before LaTeX/PDF export. --force bypasses it."""
import json
from pathlib import Path

from pipeline import config
from pipeline import lint
from pipeline.agents.extractor import load_all
from pipeline.common import sha256


class GateError(RuntimeError):
    """The draft is not allowed to be exported."""


def evaluate(draft, fise, analysis, review, paper_type, plan_text="", results_text=""):
    """Return (blockers, warnings) as lists of strings; pure, no I/O."""
    blockers, warnings = [], []
    res = lint.lint(draft, fise, paper_type, plan_text, results_text)
    for cat, n in lint.blocking(res):
        blockers.append(f"lint: {cat}: {n} (e.g. {res[cat][0][:90]})")

    if review is None:
        blockers.append("review: no review found; run `python main.py --step review`")
    else:
        if review.get("_draft_sha256") != sha256(draft):
            blockers.append("review: stale (the draft changed after the review); run `--step review` again")
        for c in review.get("claims", []):
            if c.get("status") == "unsupported":
                blockers.append(f"review: unsupported claim: {str(c.get('claim'))[:110]}")
        for m in review.get("abstract_conclusion_mismatches", []):
            blockers.append(f"review: abstract/conclusion mismatch: {str(m)[:110]}")

    nov = (analysis or {}).get("novelty_statement") or {}
    if nov.get("distinguishable") is False:
        warnings.append("NOVELTY NOT DISTINGUISHABLE from related work; sharpen it: "
                        + "; ".join(nov.get("sharpening_suggestions", [])[:3]))
    rec = ((analysis or {}).get("paper_type_recommendation") or {}).get("type")
    if rec and rec != paper_type:
        warnings.append(f"the analyst recommends type '{rec}' but you run --type {paper_type}")
    return blockers, warnings


def _load_json(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _read(path):
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run(force=False):
    draft_path = Path(config.DRAFT_FILE)
    if not draft_path.exists():
        raise GateError(f"No draft found at {draft_path}; run the write step first.")
    blockers, warnings = evaluate(
        draft_path.read_text(encoding="utf-8"), load_all(), _load_json(config.ANALYSIS_FILE),
        _load_json(config.REVIEW_FILE), config.PAPER_TYPE, _read(config.PLAN_FILE), _read(config.RESULTS_FILE))
    for w in warnings:
        print(f"[gate] !!! WARNING: {w}")
    if blockers and not force:
        raise GateError("Export blocked by the quality gate:\n  - " + "\n  - ".join(blockers)
                        + "\nFix the draft, or bypass with --force.")
    if blockers:
        print(f"[gate] FORCED: continuing despite {len(blockers)} blocking issue(s):")
        for b in blockers:
            print(f"  - {b}")
    else:
        print("[gate] passed")
