"""Build the final PDF.

Default: compile out/paper.tex with tectonic / latexmk / pdflatex / xelatex; any failure is an error.
Optional (--allow-fallback): retry with TikZ as text, or Markdown -> HTML -> PDF (lower quality, marked as such).
Install LaTeX:  conda install -c conda-forge tectonic     Fallback:  pip install markdown xhtml2pdf
Usage:  python -m pipeline.export_pdf [paper.tex] [--allow-fallback]
"""
import argparse
import shutil
import subprocess
from pathlib import Path

from pipeline import config
ENGINES = ("tectonic", "latexmk", "pdflatex", "xelatex")
ASCII_FALLBACK = {"→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≈": "~", "≠": "!=", "×": "x", "·": "*",
                  "√": "sqrt", "−": "-", "∼": "~", "∗": "*", "‑": "-", "α": "alpha", "β": "beta",
                  "γ": "gamma", "ε": "eps", "λ": "lambda", "σ": "sigma", "π": "pi", "∞": "inf"}


def find_engine():
    return next((e for e in ENGINES if shutil.which(e)), None)


# Windows exit codes that mean the program could not even start (not a LaTeX error in the paper)
STARTUP_CRASH = {3221225785: "0xC0000139 entry point not found", 3221225781: "0xC0000135 DLL not found",
                 3221225477: "0xC0000005 access violation"}


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _explain_failure(cmd, r, tex, engine):
    """Build an error with the real output; retry tectonic verbosely if it failed silently; save a full log."""
    out = (r.stdout or "") + (r.stderr or "")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if engine == "tectonic" and len(lines) < 3:           # silent failure: ask tectonic to print engine output
        r2 = _run([engine, "--print", "--keep-logs", tex.name], tex.parent)
        out2 = (r2.stdout or "") + (r2.stderr or "")
        if out2.strip():
            out, lines = out2, [ln for ln in out2.splitlines() if ln.strip()]
    log = tex.parent / "latex_build.log"
    log.write_text(f"$ {' '.join(cmd)}\nexit code {r.returncode}\n\n{out}", encoding="utf-8")
    tail = "\n".join(lines[-40:]) or "(the engine printed nothing)"
    if r.returncode in STARTUP_CRASH:
        tail += (f"\nThe engine crashed on startup ({STARTUP_CRASH[r.returncode]}): the installation is broken "
                 f"(usually conflicting DLLs in the conda env), your paper is not the problem.\n"
                 f"Check: {engine} --version. Fix: reinstall {engine}, use the standalone {engine} binary, "
                 f"or install MiKTeX/TeX Live (pdflatex). Meanwhile upload out/paper.tex to Overleaf.")
    return RuntimeError(f"LaTeX compilation failed ({engine}, exit code {r.returncode}).\n{tail}\n"
                        f"Full log: {log}\nRun by hand: cd {tex.parent} && {' '.join(cmd)}")


def compile_latex(tex_path, pdf_path=None):
    tex = Path(tex_path).resolve()
    engine = find_engine()
    if not engine:
        raise RuntimeError("No LaTeX engine found (tectonic/latexmk/pdflatex/xelatex).")
    if engine == "tectonic":
        runs = [[engine, tex.name]]
    elif engine == "latexmk":
        runs = [[engine, "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex.name]]
    else:  # latex, bibtex (if refs.bib is used), latex twice: references and hyperlinks
        once = [engine, "-interaction=nonstopmode", "-halt-on-error", tex.name]
        runs = [once] + ([["bibtex", tex.stem]] if "\\bibliography{" in tex.read_text(encoding="utf-8") else []) + [once, once]

    print(f"[pdf] compiling with {engine}...")
    for cmd in runs:
        r = _run(cmd, tex.parent)
        if r.returncode != 0:
            raise _explain_failure(cmd, r, tex, engine)

    for ext in (".aux", ".log", ".out", ".fls", ".fdb_latexmk", ".toc", ".bbl", ".blg", ".xdv"):
        tex.with_suffix(ext).unlink(missing_ok=True)   # remove auxiliary files

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
        raise RuntimeError("Fallback packages missing. Run: pip install markdown xhtml2pdf")

    text = Path(md_path).read_text(encoding="utf-8")
    for k, v in ASCII_FALLBACK.items():          # standard fonts lack these symbols
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
        raise RuntimeError("xhtml2pdf reported errors while building the PDF.")
    return target.resolve()


def page_count(pdf):
    """Number of pages, or None if pypdf is missing."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(pdf)).pages)
    except Exception:
        return None


def report_pages(pdf):
    n = page_count(pdf)
    if n is None:
        return n
    limit = config.page_limit()
    print(f"[pdf] {n} pages" + (f" (limit {limit})" if limit else ""))
    if limit and n > limit:
        print(f"[pdf] !!! WARNING: {n} pages exceeds the limit of {limit} (check whether references count)")
    return n


def run(tex_path=None, md_path=None, pdf_path=None, allow_fallback=False):
    tex_path = Path(tex_path or config.LATEX_FILE)
    md_path = Path(md_path or config.DRAFT_FILE)
    from pipeline import export_latex
    if find_engine():
        if not tex_path.exists():
            export_latex.convert_file(md_path, tex_path)
        try:
            pdf = compile_latex(tex_path, pdf_path)
        except RuntimeError:
            if not allow_fallback:
                raise
            print("[pdf] WARNING: build failed; retrying with TikZ figures as text (--allow-fallback).")
            export_latex.convert_file(md_path, tex_path, no_figures=True)
            pdf = compile_latex(tex_path, pdf_path)
    elif allow_fallback:
        print("[pdf] WARNING: no LaTeX; using the HTML fallback (lower quality, NOT for submission).")
        pdf = html_to_pdf(md_path, pdf_path)
    else:
        raise RuntimeError("No LaTeX engine found. Install one (conda install -c conda-forge tectonic) "
                           "or pass --allow-fallback for a draft-quality HTML PDF.")
    print(f"[pdf] done: {pdf}")
    report_pages(pdf)
    return pdf


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tex", nargs="?", help="the .tex file (default out/paper.tex)")
    ap.add_argument("--allow-fallback", action="store_true", help="allow TikZ-as-text retry and HTML fallback")
    a = ap.parse_args()
    try:
        run(a.tex, allow_fallback=a.allow_fallback)
    except RuntimeError as e:
        raise SystemExit(f"[pdf] {e}")