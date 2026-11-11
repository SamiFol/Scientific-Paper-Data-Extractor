"""Agent 2: analiza, verificarea cifrelor, gap, noutate, ipoteze, plan de evaluare, outline."""
import json
from pathlib import Path

import config
import llm
from agents.extractor import load_all
from rules import GLOBAL_RULES


def _read(path):
    return Path(path).read_text(encoding="utf-8").strip() if path and Path(path).exists() else ""


def _system(paper_type):
    if paper_type == "position":
        outline_spec = (
            'Outline (in this order; level 2 = "##", level 3 = "###"): Abstract; Introduction (problem, gap, '
            'exactly 3 contribution bullets, paper outline paragraph); Related Work (by theme, ending with a '
            'clear comparison to our approach); Method (level 2, short overview) followed by level-3 entries: '
            '"Formal Definitions" (memory tuple, retrieval score with every symbol defined), "Architecture" '
            '(must include Figure 1 as a TikZ diagram), "Tool-Chaining Algorithm" (numbered pseudocode), '
            '"Training Objective and Cost" (loss/objective written out, or explicitly state it is '
            'prompting-based, plus complexity/cost); Proposed Evaluation (level 2, must include Table 1 '
            'summarizing the setup; hypotheses H1-H3); Discussion; Limitations; Conclusion. '
            'NO Results section: the paper has no results of its own.')
    else:
        outline_spec = (
            'Outline (in this order): Abstract; Introduction; Related Work; Method (level 2) with level-3 '
            'entries "Formal Definitions", "Architecture" (Figure 1 as TikZ), "Tool-Chaining Algorithm", '
            '"Training Objective and Cost"; Experimental Setup (with Table 1); Results (ONLY the real data '
            'given in PROJECT STATUS); Discussion; Limitations; Conclusion.')
    return f"""ROLE: ANALYZER
You are a senior literature analyst and co-author. You receive exhaustive source sheets (with cite_key),
a topic, the project status and optionally a previous draft. Refer to papers ONLY by cite_key.
{GLOBAL_RULES}

Reply ONLY with valid JSON with these keys:
{{
 "paper_title": str,
 "paper_type_recommendation": {{"type": "position"|"empirical", "reason": str,
                               "sections_to_remove_or_rewrite": [str]}},
 "number_verification": [{{"claim": str, "status": "correct"|"incorrect"|"out_of_context"|"not_found_in_sources",
                          "actual": str, "setting": str, "source": "cite_key + page/table"}}],
 "consistency_report": [{{"issue": str, "type": "contradiction"|"undefined_term"|"unsupported_claim"|"missing_citation",
                         "where": str}}],
 "themes": [{{"theme": str, "description": str, "papers": [cite_key]}}],
 "comparison_table": [{{"paper": cite_key, "problem": str, "method": str, "evidence": "exact numbers + setting",
                       "strengths": str, "weaknesses": str}}],
 "research_gap": {{"statement": str,
                  "supported_by": [{{"limitation": str, "paper": cite_key, "where": str}}]}},
 "novelty_statement": {{"statement": str, "distinguishable": bool,
                       "differs_from": [{{"work": str, "difference": str}}],
                       "sharpening_suggestions": [str]}},
 "framework_spec": {{"name": str, "memory_object": "formal tuple definition",
                    "retrieval_score": "formula with every symbol defined",
                    "tool_chaining": "numbered steps", "training_mode": "prompting"|"finetuned",
                    "training_objective": str, "complexity_and_cost": str}},
 "hypotheses": [{{"id": "H1", "statement": str, "metric": str, "baseline": str,
                 "confirmed_if": str, "refuted_if": str}}],
 "evaluation_plan": {{"benchmarks": [str], "baselines": [str], "metrics": [str], "ablations": [str],
                     "model_size": str, "compute_budget": str, "threats_to_validity": [str],
                     "unfair_comparisons_to_avoid": [str]}},
 "missing_related_work": [str],
 "outline": [{{"id": int, "title": str, "level": 2|3, "goal": str, "key_points": [str],
              "papers": [cite_key], "target_words": int}}]
}}
Rules for the keys:
- number_verification: check EVERY line of "Numbers to verify" against the sheets (claims_table/results);
  say in which setting it holds. consistency_report: only if a previous draft is given, else [].
- research_gap must be supported by limitations stated by the authors in the sheets, not generic statements.
- novelty_statement: compare with the works available in the sheets (e.g. Generative Agents). If it cannot be
  distinguished, set distinguishable=false and say how to sharpen it. Do NOT invent other works.
- framework_spec: define the memory object, retrieval scoring, tool chaining and whether it is
  prompting-based or finetuned ONCE (reuse the chosen name if given). Ground it in the sources.
- hypotheses: exactly 3, each testable with a metric and baseline. evaluation_plan must flag unfair
  comparisons (e.g. small model vs. numbers of a larger model from a different paper/protocol).
- missing_related_work: well-known relevant works NOT present in the sheets (name only; a human must add
  their PDFs). Never cite them in the outline.
- {outline_spec}
- target_words must sum (Abstract excluded) to about the requested length."""


def run(topic):
    fise = load_all()
    print(f"[2] analizez in profunzime {len(fise)} papers (tip: {config.PAPER_TYPE})")
    prompt = (
        f"Topic: {topic}\nPaper type requested: {config.PAPER_TYPE}\n"
        f"Chosen framework name: {config.FRAMEWORK_NAME or '(choose ONE short name)'}\n"
        f"Venue/template: {config.TEMPLATE or 'unspecified'}; page limit: {config.PAGE_LIMIT or 'unspecified'}\n"
        f"Target length (body, abstract excluded): {config.TARGET_WORDS} words\n\n"
        f"PROJECT STATUS (real experiments so far):\n{_read(config.STATUS_FILE) or 'NONE'}\n\n"
        f"Numbers to verify against the sources:\n{_read(config.VERIFY_FILE) or '(none)'}\n\n"
        f"Previous draft to audit:\n{_read(config.PREVIOUS_DRAFT) or '(none)'}\n\n"
        f"Source sheets:\n{json.dumps(fise, ensure_ascii=False)}"
    )
    raw = llm.call(config.MODEL_SMART, prompt, _system(config.PAPER_TYPE), json_out=True,
                   max_tokens=config.MAX_OUT_ANALYZE)
    data = json.loads(raw)
    config.ANALYSIS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(s.get("target_words", 0) for s in data.get("outline", []))
    bad = [v for v in data.get("number_verification", []) if v.get("status") != "correct"]
    print(f"  outline: {len(data.get('outline', []))} sectiuni, ~{total} cuvinte tinta")
    if bad:
        print(f"  ATENTIE: {len(bad)} cifre din lista de verificat NU sunt 'correct' (vezi analysis.json)")
    return data