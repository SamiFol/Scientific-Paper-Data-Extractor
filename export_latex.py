"""Converteste paperul Markdown (out/paper_draft.md) intr-un fisier LaTeX self-contained.

Ce face:
  - titlu, autor, conferinta, abstract -> \\title / \\author / abstract
  - ## / ### / #### -> \\section / \\subsection / \\subsubsection
  - **bold**, *italic*, `cod`, $formule$, $$formule$$, liste, tabele, blocuri de cod, link-uri
  - [Autor et al., 2023] -> \\cite{...} + bibliografie (thebibliography) construita din sectiunea References
  - [TODO: ...] -> text rosu, ca sa nu-l ratezi
  - escapare caractere speciale LaTeX si simboluri unicode uzuale (-> >= x sqrt etc.)

Rulare:  python export_latex.py [in.md] [out.tex] [--author "Nume1, Nume2"] [--twocolumn]
"""
import argparse
import re
from pathlib import Path

import config

SPECIAL = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}
UNICODE = {
    "→": r"$\rightarrow$", "←": r"$\leftarrow$", "↔": r"$\leftrightarrow$", "⇒": r"$\Rightarrow$",
    "≥": r"$\geq$", "≤": r"$\leq$", "≈": r"$\approx$", "≠": r"$\neq$", "∼": r"$\sim$",
    "×": r"$\times$", "·": r"$\cdot$", "√": r"$\surd$", "±": r"$\pm$", "∞": r"$\infty$",
    "∈": r"$\in$", "∑": r"$\sum$", "∏": r"$\prod$", "∂": r"$\partial$", "∇": r"$\nabla$",
    "−": r"$-$", "‑": "-", "\u00a0": "~", "…": r"\ldots{}", "•": r"\textbullet{}",
    "“": "``", "”": "''", "‘": "`", "’": "'", "–": "--", "—": "---",
    "∗": "*", "†": r"\dag{}", "‡": r"\ddag{}", "°": r"$^\circ$", "ε": r"$\varepsilon$",
    "α": r"$\alpha$", "β": r"$\beta$", "γ": r"$\gamma$", "δ": r"$\delta$", "θ": r"$\theta$",
    "λ": r"$\lambda$", "μ": r"$\mu$", "π": r"$\pi$", "σ": r"$\sigma$", "τ": r"$\tau$",
    "φ": r"$\phi$", "ϕ": r"$\phi$", "Δ": r"$\Delta$", "Σ": r"$\Sigma$", "Ω": r"$\Omega$",
}

PREAMBLE = r"""\documentclass[%(opts)s]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[%(geometry)s]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{xcolor}
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta,shapes.geometric,calc}
\usepackage[colorlinks=true,linkcolor=black,citecolor=blue,urlcolor=blue]{hyperref}
\newcommand{\todo}[1]{\textcolor{red}{\textbf{[TODO: #1]}}}
"""


def esc(s):
    return "".join(SPECIAL.get(c) or UNICODE.get(c) or c for c in s)


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


# ----------------------------------------------------------------------------- inline
def inline(text, cmap):
    stash = []

    def put(x):
        stash.append(x)
        return f"ZQSTASH{len(stash) - 1}ZQ"

    # cod, formule, TODO, link-uri (protejate de escapare)
    text = re.sub(r"`([^`]+)`", lambda m: put(r"\texttt{" + esc(m.group(1)) + "}"), text)
    text = re.sub(r"\$\$(.+?)\$\$", lambda m: put(r"\[" + m.group(1) + r"\]"), text, flags=re.S)
    text = re.sub(r"\$(?=\S)([^$\n]+?)(?<=\S)\$(?!\d)", lambda m: put("$" + m.group(1) + "$"), text)
    text = re.sub(r"\[TODO:?\s*([^\]]*)\]", lambda m: put(r"\todo{" + esc(m.group(1).strip()) + "}"), text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda m: put(r"\href{" + m.group(2).replace("%", r"\%").replace("#", r"\#") + "}{" + esc(m.group(1)) + "}"),
        text)

    # citari [Autor et al., 2023] / [A, 2020; B, 2021]
    def cite(m):
        keys = [cmap.get(_norm(p)) for p in m.group(1).split(";")]
        return put(r"\cite{" + ",".join(keys) + "}") if keys and all(keys) else m.group(0)

    text = re.sub(r"\[([^\[\]]+)\]", cite, text)

    # ghilimele drepte -> tipografice
    text = re.sub(r'"([^"\n]+)"', lambda m: "“" + m.group(1) + "”", text)

    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\\emph{\1}", text)
    return re.sub(r"ZQSTASH(\d+)ZQ", lambda m: stash[int(m.group(1))], text)


# ----------------------------------------------------------------------------- blocuri
OPTS = {"no_figures": False}
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")


def _table(rows, cmap):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    header, body = cells[0], cells[2:]
    n = max(len(r) for r in [header] + body)
    pad = lambda r: r + [""] * (n - len(r))
    row = lambda r: " & ".join(inline(c, cmap) for c in pad(r)) + r" \\"
    out = [r"\begin{table}[htbp]", r"\centering\small", r"\resizebox{\linewidth}{!}{%",
           r"\begin{tabular}{" + "l" * n + "}", r"\toprule", row(header), r"\midrule"]
    out += [row(r) for r in body]
    out += [r"\bottomrule", r"\end{tabular}}", r"\end{table}", ""]
    return out


def blocks(lines, cmap):
    out, para, i, n = [], [], 0, len(lines)

    def flush():
        if para:
            out.extend([inline(" ".join(para), cmap), ""])
            para.clear()

    while i < n:
        s = lines[i].strip()
        if s.startswith("```"):                                   # bloc de cod / figura TikZ
            flush()
            lang = s[3:].strip().lower()
            code = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i].rstrip("\n"))
                i += 1
            if lang in ("tikz", "latex", "tex") and not OPTS["no_figures"]:
                out.extend([*code, ""])                           # LaTeX brut (figura)
            else:
                out.extend([r"\begin{verbatim}", *code, r"\end{verbatim}", ""])
        elif re.match(r"^#{1,6}\s", s):                           # titlu
            flush()
            level = len(s) - len(s.lstrip("#"))
            title = re.sub(r"^\d+(\.\d+)*\.?\s+", "", s.lstrip("#").strip())
            cmd = {1: "section", 2: "section", 3: "subsection", 4: "subsubsection"}.get(level, "paragraph")
            out.extend([f"\\{cmd}{{{inline(title, cmap)}}}", ""])
        elif s.startswith("|") and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            flush()                                               # tabel
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.extend(_table(rows, cmap))
            continue
        elif s.startswith("$$"):                                  # formula display (si pe mai multe linii)
            flush()
            buf = [s]
            if s.count("$$") < 2:
                while i + 1 < n:
                    i += 1
                    buf.append(lines[i].strip())
                    if "$$" in lines[i]:
                        break
            out.extend([r"\[" + " ".join(buf).replace("$$", "").strip() + r"\]", ""])
        elif LIST_RE.match(lines[i]):                             # lista
            flush()
            ordered = bool(re.match(r"\d", LIST_RE.match(lines[i]).group(2)))
            env = "enumerate" if ordered else "itemize"
            items = []
            while i < n:
                m = LIST_RE.match(lines[i])
                if m:
                    items.append([m.group(3)])
                elif lines[i].strip() and lines[i].startswith((" ", "\t")) and items:
                    items[-1].append(lines[i].strip())
                else:
                    break
                i += 1
            out.append(rf"\begin{{{env}}}")
            out.extend(r"\item " + inline(" ".join(it), cmap) for it in items)
            out.extend([rf"\end{{{env}}}", ""])
            continue
        elif s.startswith(">"):                                   # citat
            flush()
            q = []
            while i < n and lines[i].strip().startswith(">"):
                q.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.extend([r"\begin{quote}", inline(" ".join(q), cmap), r"\end{quote}", ""])
            continue
        elif re.fullmatch(r"[-*_]{3,}", s):                       # linie orizontala: ignoram
            flush()
        elif not s:
            flush()
        else:
            para.append(s)
        i += 1
    flush()
    return out


# ----------------------------------------------------------------------------- document
def parse_refs(lines):
    """'- [Yao et al., 2023] Autori (2023). Titlu. Venue' -> bibitems + harta text-citare -> cheie."""
    cmap, items, used = {}, [], set()
    for line in lines:
        m = re.match(r"^\s*[-*]\s+\[([^\]]+)\]\s*(.*)$", line)
        if not m:
            continue
        label, rest = _norm(m.group(1)), m.group(2).strip()
        year = re.search(r"\d{4}", label)
        base = re.sub(r"[^a-z0-9]", "", label.split()[0].lower()) + (year.group(0) if year else "") or "ref"
        key, k = base, 1
        while key in used:
            k += 1
            key = f"{base}{chr(96 + k)}"
        used.add(key)
        cmap.setdefault(label, key)
        items.append((key, rest))
    return cmap, items


def split_sections(md):
    """-> (titlu, linii inainte de primul ##, [(titlu_sectiune, linii), ...])"""
    lines = md.splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), "Untitled")
    pre, secs, cur = [], [], None
    for l in lines:
        if l.startswith("## "):
            cur = (l[3:].strip(), [])
            secs.append(cur)
        elif cur is None:
            pre.append(l)
        else:
            cur[1].append(l)
    return title, pre, secs


def md_to_latex(md, author=None, twocolumn=False, no_figures=False):
    OPTS["no_figures"] = no_figures
    title, pre, secs = split_sections(md)
    meta = "\n".join(pre)
    m = re.search(r"\*\*Author:?\*\*:?\s*(.+)", meta)
    author_txt = author or (m.group(1).strip() if m else "")
    if "TODO" in author_txt:
        author_txt = ""
    author_txt = author_txt or "Anonymous Authors"      # fara placeholdere in textul final

    refs = next((s for s in secs if s[0].lower().startswith("reference")), None)
    cmap, bib = parse_refs(refs[1]) if refs else ({}, [])

    opts = "10pt,a4paper,twocolumn" if twocolumn else "11pt,a4paper"
    geometry = "margin=2cm" if twocolumn else "margin=2.5cm"
    doc = [PREAMBLE % {"opts": opts, "geometry": geometry}]
    doc.append(rf"\title{{{inline(title, cmap)}}}")
    doc.append(rf"\author{{{inline(author_txt, cmap)}}}")
    doc.extend([r"\date{}", r"\begin{document}", r"\maketitle", ""])

    for name, lines in secs:
        low = name.lower()
        if low.startswith("reference"):
            continue
        if low == "abstract":
            doc.extend([r"\begin{abstract}", *blocks(lines, cmap), r"\end{abstract}", ""])
        else:
            doc.append(rf"\section{{{inline(re.sub(r'^\d+(\.\d+)*\.?\s+', '', name), cmap)}}}")
            doc.extend(blocks(lines, cmap))

    if bib:
        doc.append(r"\begin{thebibliography}{99}")
        doc.extend(rf"\bibitem{{{k}}} {inline(text, {})}" for k, text in bib)
        doc.append(r"\end{thebibliography}")
    doc.append(r"\end{document}")
    return "\n".join(doc) + "\n"


def convert_file(md_path=None, tex_path=None, author=None, twocolumn=False, no_figures=False):
    md_path = Path(md_path or config.DRAFT_FILE)
    tex_path = Path(tex_path or config.LATEX_FILE)
    tex = md_to_latex(md_path.read_text(encoding="utf-8"), author, twocolumn, no_figures)
    left = tex.count("\\todo{")
    if left:
        print(f"[latex] ATENTIE: {left} placeholdere [TODO] au ramas in text (apar rosu in PDF)")
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(tex, encoding="utf-8")
    print(f"[latex] {md_path} -> {tex_path}")
    return tex_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md", nargs="?")
    ap.add_argument("tex", nargs="?")
    ap.add_argument("--author", help="suprascrie autorul din draft")
    ap.add_argument("--twocolumn", action="store_true", help="layout pe 2 coloane")
    ap.add_argument("--no-figures", action="store_true", help="figurile TikZ raman ca text (daca nu compileaza)")
    a = ap.parse_args()
    convert_file(a.md, a.tex, a.author, a.twocolumn, a.no_figures)