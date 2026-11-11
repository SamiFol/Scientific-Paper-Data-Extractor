"""Agent 2: analysis, number verification, gap, novelty, hypotheses, evaluation plan, outline."""
import json
from pathlib import Path

from pipeline import config, llm, prompts
from pipeline.agents.extractor import compact, load_all
from pipeline.rules import GLOBAL_RULES


def _read(path):
    return Path(path).read_text(encoding="utf-8").strip() if path and Path(path).exists() else ""


def _system(paper_type):
    spec = prompts.load("analyst_outline_position" if paper_type == "position" else "analyst_outline_empirical")
    return prompts.load("analyst", global_rules=GLOBAL_RULES, outline_spec=spec)


MAX_PROMPT_TOKENS = 120_000   # warn above this (rough: 4 chars per token)


def run(topic):
    config.ensure_dirs()
    fise = load_all()
    print(f"[2] analyzing {len(fise)} papers in depth (type: {config.PAPER_TYPE})")
    plan = _read(config.PLAN_FILE)
    prompt = prompts.load(
        "analyst_input", topic=topic, paper_type=config.PAPER_TYPE,
        framework_name=config.FRAMEWORK_NAME or "(choose ONE short name)",
        template=config.TEMPLATE or "unspecified", page_limit=config.PAGE_LIMIT or "unspecified",
        target_words=config.TARGET_WORDS, plan=plan or "NONE", status=_read(config.STATUS_FILE) or "NONE",
        verify=_read(config.VERIFY_FILE) or "(none)", previous_draft=_read(config.PREVIOUS_DRAFT) or "(none)",
        sheets=json.dumps([compact(f) for f in fise], ensure_ascii=False))
    est = len(prompt) // 4
    print(f"  analyst prompt: ~{est} tokens")
    if est > MAX_PROMPT_TOKENS:
        print(f"  WARNING: prompt above ~{MAX_PROMPT_TOKENS} tokens; the model may truncate or fail. "
              "Use fewer papers or a long-context model.")
    raw = llm.call(config.MODEL_SMART, prompt, _system(config.PAPER_TYPE), json_out=True,
                   max_tokens=config.MAX_OUT_ANALYZE)
    data = json.loads(raw)
    config.ANALYSIS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(s.get("target_words", 0) for s in data.get("outline", []))
    bad = [v for v in data.get("number_verification", []) if v.get("status") != "correct"]
    print(f"  outline: {len(data.get('outline', []))} sections, ~{total} target words")
    for w in data.get("missing_related_work", []):
        print(f"  MISSING RELATED WORK (add the PDF to papers/): {w}")
    if bad:
        print(f"  WARNING: {len(bad)} numbers from the verify list are NOT 'correct' (see analysis.json)")
    return data
