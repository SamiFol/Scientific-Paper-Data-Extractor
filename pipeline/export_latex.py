"""Convert the Markdown paper (out/paper_draft.md) into a self-contained LaTeX file.

  - title, author, abstract -> \\title / \\author / abstract; ## / ### / #### -> sections
  - **bold**, *italic*, `code`, $math$, lists, tables, code blocks, links; TikZ blocks pass through raw
  - [Author et al., 2023] -> \\cite{...} + bibliography (thebibliography, or refs.bib when present)
  - [TODO: ...] or an unresolved citation -> export FAILS (use --lenient to only warn)
  - venue template (--template-dir), anonymous mode (--anonymous)

Usage:  python -m pipeline.export_latex [in.md] [out.tex] [--author "A, B"] [--twocolumn] [--template-dir DIR]
"""
import argparse
import json
import re
import shutil
from pathlib import Path

from pipeline import config
from pipeline.common import CITE_RE, norm, strip_code

class LatexExportError(RuntimeError):
    """Leftover placeholders or unresolved citations."""


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
    scale = not OPTS.get("template")                 # \resizebox breaks venue font sizes
    out = [r"\begin{table}[htbp]", r"\centering\small"] + ([r"\resizebox{\linewidth}{!}{%"] if scale else [])
    out += [r"\begin{tabular}{" + "l" * n + "}", r"\toprule", row(header), r"\midrule"]
    out += [row(r) for r in body]
    out += [r"\bottomrule", r"\end{tabular}" + ("}" if scale else ""), r"\end{table}", ""]
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


TEMPLATE_FILES = (".sty", ".cls", ".bst", ".bbx", ".cbx", ".def", ".clo")


def load_template(template_dir):
    """Read a venue template folder: optional template.json, else first .cls (class) or .sty (package).
    template.json keys: documentclass, options, packages (list), preamble (raw LaTeX), bibstyle."""
    d = Path(template_dir)
    if not d.is_dir():
        raise LatexExportError(f"template dir not found: {d}")
    t = {"dir": d, "documentclass": "article", "options": "11pt", "packages": [], "preamble": "", "bibstyle": None}
    cfg = d / "template.json"
    if cfg.exists():
        t.update(json.loads(cfg.read_text(encoding="utf-8")))
    else:
        cls, sty, bst = (sorted(d.glob(f"*{e}")) for e in (".cls", ".sty", ".bst"))
        if cls:
            t["documentclass"] = cls[0].stem
        elif sty:
            t["packages"] = [sty[0].stem]
        if bst:
            t["bibstyle"] = bst[0].stem
    t["files"] = [f for f in sorted(d.iterdir()) if f.suffix in TEMPLATE_FILES]
    return t


def template_preamble(t):
    """Preamble for a venue template: class, its package(s), the extras the exporter needs, no custom geometry."""
    lines = [rf"\documentclass[{t['options']}]{{{t['documentclass']}}}" if t["options"]
             else rf"\documentclass{{{t['documentclass']}}}",
             r"\usepackage[utf8]{inputenc}", r"\usepackage[T1]{fontenc}",
             *[rf"\usepackage{{{p}}}" for p in t["packages"]],
             r"\usepackage{amsmath,amssymb}", r"\usepackage{graphicx}", r"\usepackage{booktabs}",
             r"\usepackage{xcolor}", r"\usepackage{tikz}",
             r"\usetikzlibrary{positioning,arrows.meta,shapes.geometric,calc}",
             r"\usepackage[colorlinks=true,linkcolor=black,citecolor=blue,urlcolor=blue]{hyperref}",
             r"\newcommand{\todo}[1]{\textcolor{red}{\textbf{[TODO: #1]}}}", t.get("preamble", "")]
    return "\n".join(l for l in lines if l) + "\n"


def bib_labels(bib_path):
    """{'[Yao et al., 2023]': 'yao2023'} from `citelabel` fields written by the literature agent."""
    txt = Path(bib_path).read_text(encoding="utf-8")
    return {m.group(2): m.group(1) for m in re.finditer(
        r"@\w+\s*\{\s*([^,\s]+)\s*,[^@]*?citelabel\s*=\s*\{([^}]*)\}", txt, re.S)}


def bib_keys(bib_path):
    """Entry keys in a .bib file."""
    return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", Path(bib_path).read_text(encoding="utf-8")))


def find_problems(title, secs, cmap):
    """Leftover [TODO] placeholders and citations that match no reference."""
    problems = []
    texts = [("title", title)] + [(n, "\n".join(ls)) for n, ls in secs if not n.lower().startswith("reference")]
    for name, text in texts:
        text = strip_code(text)
        for m in re.finditer(r"\[TODO[^\]]*\]?", text):
            problems.append(f"placeholder in '{name}': {m.group(0)[:60]}")
        for m in CITE_RE.finditer(text):
            for part in m.group(1).split(";"):
                if norm(part) not in cmap:
                    problems.append(f"unresolved citation in '{name}': [{norm(part)}]")
    return problems


def md_to_latex(md, author=None, twocolumn=False, no_figures=False, strict=True, template=None,
                anonymous=False, bib_file=None):
    OPTS["no_figures"] = no_figures
    OPTS["template"] = bool(template)
    title, pre, secs = split_sections(md)
    meta = "\n".join(pre)
    m = re.search(r"\*\*Author:?\*\*:?\s*(.+)", meta)
    author_txt = author or (m.group(1).strip() if m else "")
    if "TODO" in author_txt:
        author_txt = ""
    author_txt = "Anonymous Authors" if anonymous else (author_txt or "Anonymous Authors")

    refs = next((s for s in secs if s[0].lower().startswith("reference")), None)
    cmap, bib = parse_refs(refs[1]) if refs else ({}, [])
    use_bib = bool(bib_file) and Path(bib_file).exists()
    if use_bib:                       # labels resolve through refs.bib: `citelabel` field first, else same-name key
        known = bib_keys(bib_file)
        by_label = bib_labels(bib_file)
        cmap = {k: by_label.get(f"[{k}]", v) for k, v in cmap.items() if by_label.get(f"[{k}]", v) in known}
    if strict:
        problems = find_problems(title, secs, cmap)
        if problems:
            raise LatexExportError("LaTeX export refused:\n  - " + "\n  - ".join(problems[:20]))

    opts = "10pt,a4paper,twocolumn" if twocolumn else "11pt,a4paper"
    geometry = "margin=2cm" if twocolumn else "margin=2.5cm"
    doc = [template_preamble(template) if template else PREAMBLE % {"opts": opts, "geometry": geometry}]
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

    if use_bib:
        style = (template or {}).get("bibstyle") or "plain"
        doc.extend([rf"\bibliographystyle{{{style}}}", rf"\bibliography{{{Path(bib_file).stem}}}"])
    elif bib:
        doc.append(r"\begin{thebibliography}{99}")
        doc.extend(rf"\bibitem{{{k}}} {inline(text, {})}" for k, text in bib)
        doc.append(r"\end{thebibliography}")
    doc.append(r"\end{document}")
    return "\n".join(doc) + "\n"


def convert_file(md_path=None, tex_path=None, author=None, twocolumn=False, no_figures=False, strict=True,
                 template_dir=None, anonymous=False, bib_file=None):
    md_path = Path(md_path or config.DRAFT_FILE)
    tex_path = Path(tex_path or config.LATEX_FILE)
    tpl = load_template(template_dir) if template_dir else None
    if bib_file is None and (config.ROOT / "refs.bib").exists():
        bib_file = config.ROOT / "refs.bib"
    tex = md_to_latex(md_path.read_text(encoding="utf-8"), author, twocolumn, no_figures, strict, tpl,
                      anonymous, bib_file)
    left = tex.count("\\todo{")
    if left:
        print(f"[latex] WARNING: {left} [TODO] placeholders left in the text (shown in red)")
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(tex, encoding="utf-8")
    for f in (tpl["files"] if tpl else []):          # template files must sit next to the .tex
        shutil.copyfile(f, tex_path.parent / f.name)
    if bib_file and Path(bib_file).exists() and "\\bibliography{" in tex:
        shutil.copyfile(bib_file, tex_path.parent / Path(bib_file).name)
    print(f"[latex] {md_path} -> {tex_path}" + (f" (template: {tpl['documentclass']})" if tpl else ""))
    return tex_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md", nargs="?")
    ap.add_argument("tex", nargs="?")
    ap.add_argument("--author", help="override the draft author")
    ap.add_argument("--twocolumn", action="store_true", help="two-column layout")
    ap.add_argument("--template-dir", help="venue template folder (.cls/.sty/.bst, optional template.json)")
    ap.add_argument("--anonymous", action="store_true", help="anonymous submission (author block removed)")
    ap.add_argument("--bib", help="BibTeX file (default: refs.bib in the project root if present)")
    ap.add_argument("--lenient", action="store_true", help="do not fail on TODOs/unresolved citations")
    ap.add_argument("--no-figures", action="store_true", help="keep TikZ figures as text (if they do not compile)")
    a = ap.parse_args()
    convert_file(a.md, a.tex, a.author, a.twocolumn, a.no_figures, strict=not a.lenient,
                 template_dir=a.template_dir, anonymous=a.anonymous, bib_file=a.bib)
