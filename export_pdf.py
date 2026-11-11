"""Genereaza PDF-ul final.

Metoda 1 (recomandata, calitate LaTeX): compileaza out/paper.tex cu tectonic / latexmk / pdflatex / xelatex.
Metoda 2 (fallback, fara LaTeX instalat): Markdown -> HTML -> PDF cu `markdown` + `xhtml2pdf`.

Instalare LaTeX in mediul conda (cel mai simplu pe Windows):
    conda install -c conda-forge tectonic
Fallback:
    pip install markdown xhtml2pdf

Rulare:  python export_pdf.py [paper.tex] [--engine auto|latex|html]
"""
import argparse
import shutil
import subprocess
from pathlib import Path

import config

ENGINES = ("tectonic", "latexmk", "pdflatex", "xelatex")
ASCII_FALLBACK = {"→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≈": "~", "≠": "!=", "×": "x", "·": "*",
                  "√": "sqrt", "−": "-", "∼": "~", "∗": "*", "‑": "-", "α": "alpha", "β": "beta",
                  "γ": "gamma", "ε": "eps", "λ": "lambda", "σ": "sigma", "π": "pi", "∞": "inf"}


def find_engine():
    return next((e for e in ENGINES if shutil.which(e)), None)


def compile_latex(tex_path, pdf_path=None):
    tex = Path(tex_path).resolve()
    engine = find_engine()
    if not engine:
        raise RuntimeError("Nu am gasit niciun motor LaTeX (tectonic/latexmk/pdflatex/xelatex).")
    if engine == "tectonic":
        runs = [[engine, tex.name]]
    elif engine == "latexmk":
        runs = [[engine, "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex.name]]
    else:  # de doua ori, pentru referinte si hyperlink-uri
        runs = [[engine, "-interaction=nonstopmode", "-halt-on-error", tex.name]] * 2

    print(f"[pdf] compilez cu {engine}...")
    for cmd in runs:
        r = subprocess.run(cmd, cwd=tex.parent, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            tail = "\n".join((r.stdout + r.stderr).splitlines()[-30:])
            raise RuntimeError(f"Compilarea LaTeX a esuat ({engine}). Ultimele linii:\n{tail}")

    for ext in (".aux", ".log", ".out", ".fls", ".fdb_latexmk", ".toc", ".bbl", ".blg", ".xdv"):
        tex.with_suffix(ext).unlink(missing_ok=True)   # curatam fisierele auxiliare

    built = tex.with_suffix(".pdf")
    target = Path(pdf_path or config.PDF_FILE).resolve()
    if built != target:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(built, target)
    return target


def html_to_pdf(md_path, pdf_path=None):
    try:
        import markdown
        from xhtml2pdf import pisa
    except ImportError:
        raise RuntimeError("Lipsesc pachetele pentru fallback. Ruleaza: pip install markdown xhtml2pdf")

    text = Path(md_path).read_text(encoding="utf-8")
    for k, v in ASCII_FALLBACK.items():          # fonturile standard nu au simbolurile astea
        text = text.replace(k, v)
    body = markdown.markdown(text, extensions=["tables", "sane_lists", "fenced_code"])
    html = f"""<html><head><meta charset="utf-8"><style>
      @page {{ size: a4; margin: 2.2cm; }}
      body {{ font-family: Times-Roman; font-size: 11pt; line-height: 1.35; text-align: justify; }}
      h1 {{ font-size: 18pt; text-align: center; }} h2 {{ font-size: 14pt; }} h3 {{ font-size: 12pt; }}
      table {{ border: 1px solid #444; }} td, th {{ border: 1px solid #444; padding: 3px; font-size: 9pt; }}
      code, pre {{ font-family: Courier; font-size: 9pt; }}
    </style></head><body>{body}</body></html>"""
    target = Path(pdf_path or config.PDF_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as f:
        res = pisa.CreatePDF(html, dest=f, encoding="utf-8")
    if res.err:
        raise RuntimeError("xhtml2pdf a raportat erori la generarea PDF-ului.")
    return target.resolve()


def run(tex_path=None, md_path=None, pdf_path=None, engine="auto"):
    tex_path = Path(tex_path or config.LATEX_FILE)
    md_path = Path(md_path or config.DRAFT_FILE)
    if engine in ("auto", "latex"):
        if find_engine():
            if not tex_path.exists():
                import export_latex
                export_latex.convert_file(md_path, tex_path)
            try:
                pdf = compile_latex(tex_path, pdf_path)
            except RuntimeError as e:
                if "tikzpicture" not in tex_path.read_text(encoding="utf-8"):
                    raise
                print("[pdf] compilarea a esuat; reincerc cu figurile TikZ ca text (probabil o eroare in TikZ).")
                import export_latex
                export_latex.convert_file(md_path, tex_path, no_figures=True)
                pdf = compile_latex(tex_path, pdf_path)
            print(f"[pdf] gata: {pdf}")
            return pdf
        if engine == "latex":
            raise RuntimeError("Nu am gasit LaTeX. Instaleaza: conda install -c conda-forge tectonic")
        print("[pdf] LaTeX nu e instalat; folosesc fallback-ul HTML (calitate mai slaba).")
    pdf = html_to_pdf(md_path, pdf_path)
    print(f"[pdf] gata (fallback HTML): {pdf}")
    return pdf


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tex", nargs="?", help="fisierul .tex (implicit out/paper.tex)")
    ap.add_argument("--engine", choices=["auto", "latex", "html"], default="auto")
    a = ap.parse_args()
    try:
        run(a.tex, engine=a.engine)
    except RuntimeError as e:
        raise SystemExit(f"[pdf] {e}")