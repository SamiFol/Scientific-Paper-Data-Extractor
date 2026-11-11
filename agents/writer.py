"""Agent 3: scrie paperul sectiune cu sectiune, respectand regulile globale si framework_spec."""
import json
import re
from pathlib import Path

import config
import llm
from agents.extractor import load_all
from rules import GLOBAL_RULES

STYLE = """You are the author of a scientific paper for a conference. Write in English, academic tone,
concise, dense and concrete, no filler. Use ONLY the source sheets and the analysis you receive.
- Cite only with the allowed cite_keys, exactly as given (e.g. [Yao et al., 2023]); when quoting another
  paper's number, state model size and setting and cite it.
- Write complete paragraphs with transitions; sub-headings (###) only where the outline asks for them.
- Define every symbol and hypothesis the first time it is used.
- Never leave placeholders. If something is unknown, rephrase it as a plan or hypothesis, or leave it out."""

SYSTEM_TMPL = "ROLE: WRITER\n" + STYLE + "\n" + GLOBAL_RULES + "\n{type_rules}"
TYPE_RULES = {
    "position": ("This is a POSITION/PROPOSAL paper with NO results of its own: the evaluation is only "
                 "proposed. State outcomes of our approach nowhere; Discussion and Conclusion may only discuss "
                 "what the paper actually shows (the design, the argument, the plan)."),
    "empirical": ("This is an EMPIRICAL paper: results may be reported ONLY from the PROJECT STATUS text, "
                  "with exactly those numbers."),
}
CONTEXT_KEYS = ("paper_title", "research_gap", "novelty_statement", "framework_spec", "hypotheses",
                "evaluation_plan", "themes", "comparison_table")


def _words(t):
    return len(t.split())


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "section"


def _system():
    return SYSTEM_TMPL.format(type_rules=TYPE_RULES.get(config.PAPER_TYPE, TYPE_RULES["position"]))


def _sources(section, fise):
    wanted = set(section.get("papers") or [])
    return [f for f in fise if f["cite_key"] in wanted] or fise


def _first_sentence(text):
    body = re.sub(r"^#+ .*\n", "", text.strip(), count=1).strip()
    return re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0][:160]


def _write_section(i, sec, ctx, fise, written, openings, title, topic, status):
    target = int(sec.get("target_words") or 400)
    level = int(sec.get("level") or 2)
    head = "#" * level + " " + sec["title"]
    kp = json.dumps(sec.get("key_points"), ensure_ascii=False)
    extras = []
    if "figure 1" in (kp + sec.get("goal", "")).lower():
        extras.append("Include Figure 1 as a fenced ```tikz block holding a COMPLETE \\begin{figure}...\\end{figure} "
                      "with a simple TikZ diagram (nodes + arrows only; libraries allowed: positioning, "
                      "arrows.meta, shapes.geometric) and a caption. Reference it in the text.")
    if "table 1" in (kp + sec.get("goal", "")).lower():
        extras.append("Include Table 1 as a Markdown table with REAL content (benchmarks, baselines, metrics, "
                      "model size, compute), preceded by a one-line caption 'Table 1: ...'.")
    if "algorithm" in sec["title"].lower() or "pseudocode" in kp.lower():
        extras.append("Give the algorithm as NUMBERED pseudocode steps (a Markdown ordered list).")
    prompt = (
        f"Title: {title}\nTopic: {topic}\nPaper type: {config.PAPER_TYPE}\n"
        f"Allowed cite_keys: {', '.join(f['cite_key'] for f in fise)}\n\n"
        f"PROJECT STATUS:\n{status or 'NONE (no experiments of our own)'}\n\n"
        f"Global analysis (single source of truth for names/definitions):\n{json.dumps(ctx, ensure_ascii=False)}\n\n"
        f"Source sheets for this section:\n{json.dumps(_sources(sec, fise), ensure_ascii=False)}\n\n"
        f"Openings already used in earlier sections (do NOT imitate them):\n{json.dumps(openings, ensure_ascii=False)}\n"
        f"End of the previous section (continuity only):\n"
        f"{' '.join(written[-1].split()[-200:]) if written else '(first section)'}\n\n"
        f"WRITE section {i}: \"{sec['title']}\"\nGoal: {sec.get('goal')}\nKey points: {kp}\n"
        f"Length: about {target} words (at least {int(target * 0.9)}).\n"
        + "\n".join(extras) + f"\nStart directly with '{head}'. Do not repeat earlier sections."
    )
    text = llm.call(config.MODEL_SMART, prompt, _system(), max_tokens=config.MAX_OUT_WRITE, temperature=0.5)
    if _words(text) < 0.7 * target:
        print(f"  prea scurta ({_words(text)}/{target}), extind...")
        text = llm.call(
            config.MODEL_SMART,
            f"The text below is too short (target ~{target} words). Expand it with concrete detail from the "
            f"sheets (numbers with model size/setting, method steps), without inventing anything and keeping "
            f"every figure/table block unchanged.\n\nSheets:\n{json.dumps(_sources(sec, fise), ensure_ascii=False)}"
            f"\n\nTEXT:\n{text}", _system(), max_tokens=config.MAX_OUT_WRITE, temperature=0.5)
    return text


def _references(fise):
    lines = []
    for f in sorted(fise, key=lambda x: x["cite_key"]):
        authors = ", ".join(a if isinstance(a, str) else a.get("name", "") for a in (f.get("authors") or []))
        lines.append(f"- {f['cite_key']} {authors} ({f.get('year')}). {f.get('title')}. {f.get('venue') or ''}")
    return "\n".join(lines)


def run(topic, venue=None):
    analysis = json.loads(config.ANALYSIS_FILE.read_text(encoding="utf-8"))
    fise = load_all()
    outline = analysis.get("outline", [])
    title = analysis.get("paper_title", topic)
    ctx = {k: analysis[k] for k in CONTEXT_KEYS if k in analysis}
    status = config.STATUS_FILE.read_text(encoding="utf-8").strip() if config.STATUS_FILE.exists() else ""

    body_secs = [s for s in outline if not s["title"].lower().startswith(("abstract", "reference"))]
    written, openings = [], []
    for i, sec in enumerate(body_secs, 1):
        f = config.SECTIONS_DIR / f"{i:02d}_{_slug(sec['title'])}.md"
        if f.exists():
            print(f"[3] sar peste sectiunea {i} (deja scrisa)")
            text = f.read_text(encoding="utf-8")
        else:
            print(f"[3] scriu sectiunea {i}/{len(body_secs)}: {sec['title']}")
            text = _write_section(i, sec, ctx, fise, written, openings, title, topic, status)
            f.write_text(text, encoding="utf-8")
        written.append(text)
        openings.append(_first_sentence(text))

    body = "\n\n".join(written)
    abs_file = config.SECTIONS_DIR / "00_abstract.md"
    if abs_file.exists():
        abstract = abs_file.read_text(encoding="utf-8")
    else:
        print("[3] scriu abstractul")
        abstract = llm.call(
            config.MODEL_SMART,
            f"Write the abstract (200-250 words, one paragraph) of the paper '{title}' from the full text below. "
            f"It must contain no claim above the evidence level of the paper (type: {config.PAPER_TYPE}) and "
            f"match the Conclusion. Start with '## Abstract'.\n\n{body}", _system(), max_tokens=2000)
        abs_file.write_text(abstract, encoding="utf-8")

    draft = f"# {title}\n\n{abstract}\n\n{body}\n\n## References\n\n{_references(fise)}\n"
    config.DRAFT_FILE.write_text(draft, encoding="utf-8")
    print(f"  draft complet: ~{_words(body) + _words(abstract)} cuvinte -> {config.DRAFT_FILE}")