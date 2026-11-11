"""Agent 3: write the paper section by section, following the global rules and framework_spec."""
import json
import re
from pathlib import Path

from pipeline import config, llm, prompts
from pipeline.agents.extractor import load_all
from pipeline.rules import GLOBAL_RULES

TYPES = ("position", "empirical")
CONTEXT_KEYS = ("paper_title", "research_gap", "novelty_statement", "framework_spec", "hypotheses",
                "evaluation_plan", "themes", "comparison_table")


def _words(t):
    return len(t.split())


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "section"


def _system():
    t = config.PAPER_TYPE if config.PAPER_TYPE in TYPES else "position"
    return prompts.load("writer", global_rules=GLOBAL_RULES, type_rules=prompts.load(f"writer_type_{t}"))


def _sources(section, fise):
    wanted = set(section.get("papers") or [])
    return [f for f in fise if f["cite_key"] in wanted] or fise


def _first_sentence(text):
    body = re.sub(r"^#+ .*\n", "", text.strip(), count=1).strip()
    return re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0][:160]


def _write_section(i, sec, ctx, fise, written, openings, title, topic, status, plan="", results=""):
    target = int(sec.get("target_words") or 400)
    level = int(sec.get("level") or 2)
    head = "#" * level + " " + sec["title"]
    kp = json.dumps(sec.get("key_points"), ensure_ascii=False)
    extras = []
    if "figure 1" in (kp + sec.get("goal", "")).lower():
        extras.append(prompts.load("writer_extra_figure1"))
    if "table 1" in (kp + sec.get("goal", "")).lower():
        extras.append(prompts.load("writer_extra_table1"))
    if "algorithm" in sec["title"].lower() or "pseudocode" in kp.lower():
        extras.append(prompts.load("writer_extra_algorithm"))
    dump = lambda x: json.dumps(x, ensure_ascii=False)
    prompt = prompts.load(
        "writer_section", title=title, topic=topic, paper_type=config.PAPER_TYPE,
        cite_keys=", ".join(f["cite_key"] for f in fise), plan=plan or "NONE",
        results=results or "NONE (no experiment has been run)",
        status=status or "NONE (no experiments of our own)", analysis=dump(ctx),
        sheets=dump(_sources(sec, fise)), openings=dump(openings),
        previous_end=" ".join(written[-1].split()[-200:]) if written else "(first section)",
        index=i, section_title=sec["title"], goal=sec.get("goal"), key_points=kp, target=target,
        min_words=int(target * 0.9), extras="\n".join(extras), head=head)
    text = llm.call(config.MODEL_SMART, prompt, _system(), max_tokens=config.MAX_OUT_WRITE, temperature=0.5)
    if _words(text) < 0.7 * target:
        print(f"  too short ({_words(text)}/{target}), expanding...")
        text = llm.call(config.MODEL_SMART,
                        prompts.load("writer_expand", target=target, sheets=dump(_sources(sec, fise)), text=text),
                        _system(), max_tokens=config.MAX_OUT_WRITE, temperature=0.5)
    return text


def _references(fise):
    lines = []
    for f in sorted(fise, key=lambda x: x["cite_key"]):
        authors = ", ".join(a if isinstance(a, str) else a.get("name", "") for a in (f.get("authors") or []))
        lines.append(f"- {f['cite_key']} {authors} ({f.get('year')}). {f.get('title')}. {f.get('venue') or ''}")
    return "\n".join(lines)


def run(topic, venue=None):
    config.ensure_dirs()
    analysis = json.loads(config.ANALYSIS_FILE.read_text(encoding="utf-8"))
    fise = load_all()
    outline = analysis.get("outline", [])
    title = analysis.get("paper_title", topic)
    ctx = {k: analysis[k] for k in CONTEXT_KEYS if k in analysis}
    status = config.STATUS_FILE.read_text(encoding="utf-8").strip() if config.STATUS_FILE.exists() else ""

    plan = config.PLAN_FILE.read_text(encoding="utf-8").strip() if config.PLAN_FILE.exists() else ""
    results = config.RESULTS_FILE.read_text(encoding="utf-8").strip() if config.RESULTS_FILE.exists() else ""
    skip = ("abstract", "reference") + (() if results else ("results", "experimental results"))
    for s_ in outline:
        if not results and s_["title"].lower().lstrip("0123456789. ").startswith(("results", "experimental results")):
            print(f"[3] no results.json: skipping section '{s_['title']}' (no invented results)")
    body_secs = [s for s in outline if not s["title"].lower().lstrip("0123456789. ").startswith(skip)]
    written, openings = [], []
    for i, sec in enumerate(body_secs, 1):
        f = config.SECTIONS_DIR / f"{i:02d}_{_slug(sec['title'])}.md"
        if f.exists():
            print(f"[3] skipping section {i} (already written)")
            text = f.read_text(encoding="utf-8")
        else:
            print(f"[3] writing section {i}/{len(body_secs)}: {sec['title']}")
            text = _write_section(i, sec, ctx, fise, written, openings, title, topic, status, plan, results)
            f.write_text(text, encoding="utf-8")
        written.append(text)
        openings.append(_first_sentence(text))

    body = "\n\n".join(written)
    abs_file = config.SECTIONS_DIR / "00_abstract.md"
    if abs_file.exists():
        abstract = abs_file.read_text(encoding="utf-8")
    else:
        print("[3] writing the abstract")
        abstract = llm.call(config.MODEL_SMART, prompts.load("writer_abstract", title=title,
                            paper_type=config.PAPER_TYPE, body=body), _system(), max_tokens=2000)
        abs_file.write_text(abstract, encoding="utf-8")

    draft = f"# {title}\n\n{abstract}\n\n{body}\n\n## References\n\n{_references(fise)}\n"
    config.DRAFT_FILE.write_text(draft, encoding="utf-8")
    print(f"  full draft: ~{_words(body) + _words(abstract)} words -> {config.DRAFT_FILE}")
