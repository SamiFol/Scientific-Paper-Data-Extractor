"""Pas final: tabel afirmatii-vs-dovezi, change log, lista pentru om + lint automat."""
import json
from pathlib import Path

import config
import llm
import lint
from agents.extractor import load_all
from rules import GLOBAL_RULES

SYSTEM = f"""ROLE: REVIEWER
You audit a finished draft against the source sheets. {GLOBAL_RULES}
Reply ONLY with valid JSON:
{{
 "claims": [{{"claim": str, "section": str,
             "source": "cite_key + page/table | own experiment | none",
             "status": "verified"|"hypothesis"|"removed"|"unsupported", "note": str}}],
 "abstract_conclusion_mismatches": [str],
 "change_log": [{{"action": "removed"|"rewritten"|"added", "item": str, "reason": str}}],
 "human_items": [str]
}}
- claims: EVERY factual or evaluative claim of the paper. status=verified only if a sheet supports it;
  hypothesis if it is stated as a plan/expectation; unsupported if neither (these must be fixed).
- change_log: compare with the previous draft if one is given, else return [] .
- abstract_conclusion_mismatches: claims in the Conclusion above the evidence level of the Abstract (or vice versa).
- human_items: what a human must still supply (real experiments, author names, venue formatting, missing
  related-work PDFs, figures to polish)."""


def _read(p):
    return Path(p).read_text(encoding="utf-8") if p and Path(p).exists() else ""


def run():
    draft = _read(config.DRAFT_FILE)
    fise = load_all()
    analysis = json.loads(_read(config.ANALYSIS_FILE) or "{}")
    print("[4] revizuiesc draftul (afirmatii vs dovezi)")
    prompt = (
        f"Paper type: {config.PAPER_TYPE}\nPROJECT STATUS:\n{_read(config.STATUS_FILE) or 'NONE'}\n\n"
        f"Previous draft (may be empty):\n{_read(config.PREVIOUS_DRAFT) or '(none)'}\n\n"
        f"Missing related work noted by the analyzer: {json.dumps(analysis.get('missing_related_work', []))}\n\n"
        f"Source sheets:\n{json.dumps(fise, ensure_ascii=False)}\n\nDRAFT:\n{draft}")
    data = json.loads(llm.call(config.MODEL_SMART, prompt, SYSTEM, json_out=True,
                               max_tokens=config.MAX_OUT_ANALYZE))

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
    print(f"  {len(data.get('claims', []))} afirmatii; {len(bad)} NEACOPERITE; {len(mism)} nepotriviri abstract/concluzie")
    lint.run()
    return data
