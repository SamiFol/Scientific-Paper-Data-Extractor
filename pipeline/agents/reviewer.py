"""Final audit: claims-vs-evidence table, change log, human to-do list, review.json + automatic lint."""
import json
from pathlib import Path

from pipeline import config, lint, llm, prompts
from pipeline.common import sha256
from pipeline.agents.extractor import load_all
from pipeline.rules import GLOBAL_RULES

SYSTEM = prompts.load("reviewer", global_rules=GLOBAL_RULES)


def _read(p):
    return Path(p).read_text(encoding="utf-8") if p and Path(p).exists() else ""


def run():
    config.ensure_dirs()
    draft = _read(config.DRAFT_FILE)
    fise = load_all()
    analysis = json.loads(_read(config.ANALYSIS_FILE) or "{}")
    print("[4] reviewing the draft (claims vs evidence)")
    prompt = prompts.load(
        "reviewer_input", paper_type=config.PAPER_TYPE, plan=_read(config.PLAN_FILE) or "NONE",
        results=_read(config.RESULTS_FILE) or "NONE", status=_read(config.STATUS_FILE) or "NONE",
        previous_draft=_read(config.PREVIOUS_DRAFT) or "(none)",
        missing=json.dumps(analysis.get("missing_related_work", [])),
        sheets=json.dumps(fise, ensure_ascii=False), draft=draft)
    data = json.loads(llm.call(config.MODEL_SMART, prompt, SYSTEM, json_out=True,
                               max_tokens=config.MAX_OUT_ANALYZE))
    data["_draft_sha256"] = sha256(draft)   # lets the gate detect a stale review
    config.REVIEW_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = ["| # | Claim | Section | Source | Status | Note |", "|---|---|---|---|---|---|"]
    for n, c in enumerate(data.get("claims", []), 1):
        cell = lambda k: str(c.get(k, "")).replace("|", "/").replace("\n", " ")
        rows.append(f"| {n} | {cell('claim')} | {cell('section')} | {cell('source')} | {cell('status')} | {cell('note')} |")
    mism = data.get("abstract_conclusion_mismatches", [])
    config.CLAIMS_FILE.write_text("# Claims vs. evidence\n\n" + "\n".join(rows) + "\n\n## Abstract/Conclusion mismatches\n\n"
                                  + ("\n".join(f"- {m}" for m in mism) or "none") + "\n", encoding="utf-8")
    config.CHANGELOG_FILE.write_text("# Change log\n\n" + (
        "\n".join(f"- **{c.get('action')}**: {c.get('item')} - {c.get('reason')}" for c in data.get("change_log", []))
        or "No previous draft given (new draft).") + "\n", encoding="utf-8")
    config.HUMAN_FILE.write_text("# Remaining items for a human\n\n" + "\n".join(f"- [ ] {h}" for h in data.get("human_items", [])) + "\n",
                                 encoding="utf-8")
    bad = [c for c in data.get("claims", []) if c.get("status") == "unsupported"]
    print(f"  {len(data.get('claims', []))} claims; {len(bad)} UNSUPPORTED; {len(mism)} abstract/conclusion mismatches")
    lint.run()
    return data
