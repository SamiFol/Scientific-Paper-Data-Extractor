"""Fix loop: rewrite ONLY the sections with blocking issues, then re-run lint + reviewer (max 2 rounds)."""
import json
import re

from pipeline import config, gate, llm, prompts
from pipeline.agents import reviewer, writer
from pipeline.agents.extractor import load_all
from pipeline.common import CITE_RE, cite_parts
from pipeline.rules import GLOBAL_RULES

MAX_ROUNDS = 2


def needle(item):
    """Three consecutive words from the issue text (citations are stripped in lint contexts)."""
    m = re.search(r"\.\.\.(.+)\.\.\.", item)
    words = (m.group(1) if m else item).split()
    words = words[1:4] if len(words) > 5 and m else words[:3]    # first word may be cut mid-word
    return " ".join(words)


def locate(issue, files):
    """Return the section file containing the issue text, or None."""
    n = needle(issue)
    return next((f for f in files if n and n in " ".join(f.read_text(encoding="utf-8").split())), None)


def collect(review, files):
    """{section_file: [issue, ...]} from lint blockers and unsupported claims."""
    out = {}
    res = gate.lint.lint(config.DRAFT_FILE.read_text(encoding="utf-8"), load_all(), config.PAPER_TYPE,
                         _read(config.PLAN_FILE), _read(config.RESULTS_FILE))
    for cat in gate.lint.BLOCKING:
        for item in res.get(cat, []):
            f = locate(item, files)
            if f:
                out.setdefault(f, []).append(f"{cat}: {item}")
    for c in (review or {}).get("claims", []):
        if c.get("status") == "unsupported":
            f = locate(str(c.get("claim")), files)
            if f:
                out.setdefault(f, []).append(f"unsupported claim: {c.get('claim')}")
    return out


def _read(p):
    return p.read_text(encoding="utf-8") if p.exists() else ""


def rewrite(path, issues, fise):
    text = path.read_text(encoding="utf-8")
    keys = {k for m in CITE_RE.finditer(text) for k in cite_parts(m.group(1))}
    sheets = [f for f in fise if f["cite_key"] in keys]
    prompt = prompts.load("fixer_rewrite", issues="\n".join(f"- {i}" for i in issues),
                          sheets=json.dumps(sheets, ensure_ascii=False), section=text)
    new = llm.call(config.MODEL_SMART, prompt, prompts.load("fixer", global_rules=GLOBAL_RULES), max_tokens=config.MAX_OUT_WRITE)
    path.write_text(new, encoding="utf-8")


def rebuild(fise):
    """Reassemble paper_draft.md from the section files (same layout as writer.run)."""
    old = _read(config.DRAFT_FILE)
    title = old.splitlines()[0] if old.startswith("# ") else "# Untitled"
    files = sorted(f for f in config.SECTIONS_DIR.glob("*.md") if not f.name.startswith("00_"))
    abstract = _read(config.SECTIONS_DIR / "00_abstract.md")
    body = "\n\n".join(f.read_text(encoding="utf-8") for f in files)
    config.DRAFT_FILE.write_text(f"{title}\n\n{abstract}\n\n{body}\n\n## References\n\n{writer._references(fise)}\n",
                                 encoding="utf-8")


def run(rounds=MAX_ROUNDS):
    """Return the blockers left after the loop (empty list = gate-clean)."""
    fise = load_all()
    for n in range(1, rounds + 1):
        review = json.loads(_read(config.REVIEW_FILE) or "null")
        blockers, _ = gate.evaluate(_read(config.DRAFT_FILE), fise, None, review, config.PAPER_TYPE,
                                    _read(config.PLAN_FILE), _read(config.RESULTS_FILE))
        blockers = [b for b in blockers if not b.startswith("review: stale") and "no review" not in b]
        if not blockers:
            print(f"[fix] nothing to fix (round {n})")
            return []
        files = sorted(f for f in config.SECTIONS_DIR.glob("*.md") if not f.name.startswith("00_"))
        todo = collect(review, files)
        if not todo:
            print("[fix] blockers remain but none maps to a section; fix by hand:")
            return blockers
        print(f"[fix] round {n}/{rounds}: rewriting {len(todo)} section(s): " + ", ".join(f.name for f in todo))
        for f, issues in todo.items():
            rewrite(f, issues, fise)
        rebuild(fise)
        reviewer.run()
    review = json.loads(_read(config.REVIEW_FILE) or "null")
    blockers, _ = gate.evaluate(_read(config.DRAFT_FILE), fise, None, review, config.PAPER_TYPE,
                                _read(config.PLAN_FILE), _read(config.RESULTS_FILE))
    return blockers
