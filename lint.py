"""Verificari AUTOMATE (fara LLM) pe draft: placeholdere, afirmatii interzise, cifre netrasabile,
citari necunoscute, repetitii.  Rulare: python lint.py [draft.md]"""
import json
import re
import sys
from pathlib import Path

import config
from agents.extractor import load_all

NUM_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")
CITE_RE = re.compile(r"\[([^\[\]]+?,\s*(?:\d{4}|n\.d\.)(?:\s*;[^\[\]]+)?)\]")
PLACEHOLDER_RE = re.compile(r"\[TODO|TODO:|Target venue|Author Name|Anonymous Author", re.I)
OUR_CLAIMS = [r"\bour (experiments|results|evaluation|analysis|approach|method|framework) "
              r"(show|shows|demonstrate|demonstrates|validate|validates|confirm|confirms|indicate|indicates|achieve|achieves|outperform|outperforms)"]
GENERIC_CLAIMS = [r"\bconsistently (outperform|underperform)", r"\bachieves? parity", r"\bwe (observe|found|find) that",
                  r"\bresults (show|demonstrate|validate|confirm)\b", r"\bempirically (validate|confirm)"]
HEDGE = re.compile(r"hypothes|expect|would|plan|aim|propos|if |whether|could|may |might|should|test", re.I)


def _norm_num(t):
    return t.rstrip("%").replace(",", "")


def _numbers(text):
    out = {}
    for m in NUM_RE.finditer(text):
        t = _norm_num(m.group(0))
        try:
            v = float(t)
        except ValueError:
            continue
        if ("." not in t and "%" not in m.group(0) and (v <= 20 or 1900 <= v <= 2035)):
            continue  # numere mici / ani: zgomot
        out.setdefault(t, text[max(0, m.start() - 45):m.end() + 25].replace("\n", " "))
    return out


def lint(md, fise, paper_type):
    body, _, _ = md.partition("\n## References")
    refs = md.partition("\n## References")[2]
    keys = {f["cite_key"] for f in fise}
    r = {"Placeholdere": [], "Afirmatii de rezultate fara dovezi": [], "Cifre netrasabile (verifica manual)": [],
         "Citari necunoscute (nu sunt in lista de papers)": [], "Surse niciodata citate": [],
         "Deschideri / propozitii repetate": []}

    for ln in body.splitlines():
        if PLACEHOLDER_RE.search(ln):
            r["Placeholdere"].append(ln.strip()[:140])

    prose = re.sub(r"```.*?```", " ", body, flags=re.S)
    for sent in re.split(r"(?<=[.!?])\s+", prose):
        hedged = bool(HEDGE.search(sent))
        ours = paper_type == "position" and any(re.search(p, sent, re.I) for p in OUR_CLAIMS)
        generic = any(re.search(p, sent, re.I) for p in GENERIC_CLAIMS) and not CITE_RE.search(sent)
        if (ours or generic) and not hedged:
            r["Afirmatii de rezultate fara dovezi"].append(sent.strip()[:160])

    cited = set()
    for m in CITE_RE.finditer(prose):
        for part in m.group(1).split(";"):
            k = f"[{part.strip()}]"
            cited.add(k)
            if k not in keys:
                r["Citari necunoscute (nu sunt in lista de papers)"].append(k)
    r["Citari necunoscute (nu sunt in lista de papers)"] = sorted(set(r["Citari necunoscute (nu sunt in lista de papers)"]))
    r["Surse niciodata citate"] = sorted(keys - cited)

    clean = CITE_RE.sub(" ", prose)
    clean = re.sub(r"(?m)^\s*(#+\s*)?\d+(\.\d+)*[.)]?\s+", "", clean)
    known = set(_numbers(json.dumps(fise, ensure_ascii=False)))
    for t, ctx in _numbers(clean).items():
        if t not in known:
            r["Cifre netrasabile (verifica manual)"].append(f"{t}  ...{ctx}...")

    seen, firsts = {}, {}
    for sec in re.split(r"(?m)^## ", body)[1:]:
        name, _, rest = sec.partition("\n")
        first = " ".join(rest.strip().split()[:6]).lower()
        if first and first in firsts:
            r["Deschideri / propozitii repetate"].append(f"'{name}' incepe ca '{firsts[first]}': \"{first}...\"")
        firsts.setdefault(first, name)
    for sent in re.split(r"(?<=[.!?])\s+", prose):
        s = " ".join(sent.split())
        if len(s.split()) > 8:
            if s in seen:
                r["Deschideri / propozitii repetate"].append(f"propozitie repetata: {s[:100]}")
            seen[s] = 1
    return r


def run(draft_path=None):
    draft = Path(draft_path or config.DRAFT_FILE)
    res = lint(draft.read_text(encoding="utf-8"), load_all(), config.PAPER_TYPE)
    lines = ["# Raport lint (verificari automate)\n"]
    for k, v in res.items():
        lines.append(f"## {k}: {len(v)}\n")
        lines.extend(f"- {x}" for x in v[:60])
        lines.append("")
    config.LINT_FILE.write_text("\n".join(lines), encoding="utf-8")
    flagged = {k: len(v) for k, v in res.items() if v and not k.startswith("Surse")}
    print(f"[lint] {config.LINT_FILE}: " + (", ".join(f"{k}={n}" for k, n in flagged.items()) or "nicio problema"))
    return res


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
