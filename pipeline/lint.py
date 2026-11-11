"""Automatic checks on the draft (no LLM): placeholders, own-results claims, citations, numbers.
Usage: python -m pipeline.lint [draft.md]"""
import json
import re
import sys
from pathlib import Path

from pipeline import config
from pipeline.agents.extractor import load_all
from pipeline.common import CITE_RE, PLACEHOLDER_RE, cite_parts, strip_code

# Category names; BLOCKING ones stop the export (see gate.py)
PLACEHOLDERS = "Placeholders"
OWN_CLAIMS = "Unsupported own-results claims"
UNKNOWN_CITES = "Unknown citations"
CITED_NUMBERS = "Cited numbers not found in the cited source"
UNTRACED = "Untraced result-like numbers"
UNTRACED_INTS = "Untraced integers (check manually)"
UNCITED = "Sources never cited"
REPEATS = "Repeated openings or sentences"
ABSTRACT_LONG = "Abstract longer than 250 words"
BLOCKING = (PLACEHOLDERS, OWN_CLAIMS, UNKNOWN_CITES, CITED_NUMBERS, UNTRACED)

NUM_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")
OUR_CLAIMS = [r"\bour (experiments|results|evaluation|analysis|approach|method|framework) "
              r"(show|shows|demonstrate|demonstrates|validate|validates|confirm|confirms|indicate|indicates"
              r"|achieve|achieves|outperform|outperforms)"]
GENERIC_CLAIMS = [r"\bconsistently (outperform|underperform)", r"\bachieves? parity", r"\bwe (observe|found|find) that",
                  r"\bresults (show|demonstrate|validate|confirm)\b", r"\bempirically (validate|confirm)"]
HEDGE = re.compile(r"hypothes|expect|would|plan|aim|propos|if |whether|could|may |might|should|test", re.I)


def numbers_in(text):
    """Yield (token, value, decimals, is_pct, context) for noteworthy numbers (small ints and years skipped)."""
    for m in NUM_RE.finditer(text):
        raw = m.group(0)
        tok = raw.rstrip("%").replace(",", "")
        try:
            v = float(tok)
        except ValueError:
            continue
        dec = len(tok.split(".")[1]) if "." in tok else 0
        pct = raw.endswith("%")
        if not dec and not pct and (v <= 20 or 1900 <= v <= 2035):
            continue
        yield tok, v, dec, pct, text[max(0, m.start() - 45):m.end() + 25].replace("\n", " ")


def values_in(text):
    return [v for _, v, *_ in numbers_in(text)]


def covered(value, dec, allowed):
    """True if `value` matches an allowed number (rounding and percent-vs-fraction tolerated)."""
    r = round(value, dec)
    for a in allowed:
        if abs(value - a) < 1e-9 or round(a, dec) == r:
            return True
        if 0 < abs(a) <= 1 and round(a * 100, dec) == r:
            return True
    return False


def units(prose):
    """Sentences; each Markdown table row counts as one unit."""
    out = []
    for block in re.split(r"\n\s*\n", prose):
        lines = block.splitlines()
        if lines and lines[0].lstrip().startswith("|"):
            out.extend(ln for ln in lines if ln.strip())
        else:
            out.extend(re.split(r"(?<=[.!?])\s+", block))
    return out


def lint(md, fise, paper_type, plan_text="", results_text="", extra_keys=()):
    body = md.partition("\n## References")[0]
    prose = strip_code(body)
    keys = {f["cite_key"] for f in fise} | set(extra_keys)
    sheet_vals = {f["cite_key"]: values_in(json.dumps(f, ensure_ascii=False)) for f in fise}
    own_vals = values_in(plan_text) + values_in(results_text)          # plan.txt + results.json
    all_vals = own_vals + [v for vs in sheet_vals.values() for v in vs]
    r = {k: [] for k in (PLACEHOLDERS, OWN_CLAIMS, UNKNOWN_CITES, CITED_NUMBERS, UNTRACED,
                         UNTRACED_INTS, UNCITED, REPEATS, ABSTRACT_LONG)}

    for ln in body.splitlines():
        if PLACEHOLDER_RE.search(ln):
            r[PLACEHOLDERS].append(ln.strip()[:140])

    ab = re.search(r"(?ms)^## Abstract\s*\n(.*?)(?=^## )", body)
    if ab and len(ab.group(1).split()) > 250:
        r[ABSTRACT_LONG].append(f"{len(ab.group(1).split())} words (most venues allow 150-250)")

    cited = set()
    for sent in units(prose):
        hedged = bool(HEDGE.search(sent))
        ours = paper_type == "position" and any(re.search(p, sent, re.I) for p in OUR_CLAIMS)
        generic = any(re.search(p, sent, re.I) for p in GENERIC_CLAIMS) and not CITE_RE.search(sent)
        if (ours or generic) and not hedged:
            r[OWN_CLAIMS].append(sent.strip()[:160])

        sent_keys = [k for m in CITE_RE.finditer(sent) for k in cite_parts(m.group(1))]
        for k in sent_keys:
            cited.add(k)
            if k not in keys:
                r[UNKNOWN_CITES].append(k)
        text = CITE_RE.sub(" ", sent)
        text = re.sub(r"(?m)^\s*(#+\s*)?\d+(\.\d+)*[.)]?\s+", "", text)   # list/heading numbering
        known_keys = [k for k in sent_keys if k in sheet_vals]
        for tok, v, dec, pct, ctx in numbers_in(text):
            if known_keys:       # cited sentence: number must come from a cited source, plan or results
                allowed = own_vals + [x for k in known_keys for x in sheet_vals[k]]
                if not covered(v, dec, allowed):
                    r[CITED_NUMBERS].append(f"{tok} cites {', '.join(known_keys)}: ...{ctx}...")
            elif not covered(v, dec, all_vals):
                r[UNTRACED if (dec or pct) else UNTRACED_INTS].append(f"{tok}  ...{ctx}...")

    r[UNKNOWN_CITES] = sorted(set(r[UNKNOWN_CITES]))
    r[UNCITED] = sorted(keys - cited)

    firsts, seen = {}, set()
    for sec in re.split(r"(?m)^## ", body)[1:]:
        name, _, rest = sec.partition("\n")
        first = " ".join(rest.strip().split()[:6]).lower()
        if first and first in firsts:
            r[REPEATS].append(f"'{name}' opens like '{firsts[first]}': \"{first}...\"")
        firsts.setdefault(first, name)
    for sent in re.split(r"(?<=[.!?])\s+", prose):
        s = " ".join(sent.split())
        if len(s.split()) > 8:
            if s in seen:
                r[REPEATS].append(f"repeated sentence: {s[:100]}")
            seen.add(s)
    return r


def blocking(result):
    """[(category, count)] for blocking categories that have findings."""
    return [(k, len(result[k])) for k in BLOCKING if result.get(k)]


def _read(path):
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run(draft_path=None):
    config.ensure_dirs()
    draft = Path(draft_path or config.DRAFT_FILE)
    res = lint(draft.read_text(encoding="utf-8"), load_all(), config.PAPER_TYPE,
               _read(config.PLAN_FILE), _read(config.RESULTS_FILE))
    lines = ["# Lint report (automatic checks)\n"]
    for k, v in res.items():
        tag = " [BLOCKING]" if k in BLOCKING else ""
        lines.append(f"## {k}{tag}: {len(v)}\n")
        lines.extend(f"- {x}" for x in v[:60])
        lines.append("")
    config.LINT_FILE.write_text("\n".join(lines), encoding="utf-8")
    flagged = {k: len(v) for k, v in res.items() if v and k != UNCITED}
    print(f"[lint] {config.LINT_FILE}: " + (", ".join(f"{k}={n}" for k, n in flagged.items()) or "no issues"))
    return res


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
