"""Entry point.
  python main.py "Topic" "Venue"                           # full pipeline, up to PDF (gate in front of export)
  python main.py --step extract|analyze|literature|write|review|fix|lint|gate|latex|pdf "Topic" "Venue"
  python main.py --type position --name RCTA --pages 8 "Topic" "Venue"
  python main.py --draft old.md "Topic" "Venue"            # audit + rewrite an existing draft
  python main.py --force ...                               # export despite gate blockers (loudly)
Optional files in the project folder:
  plan.txt            - your own plan/targets/budgets, used verbatim (see plan.txt.example)
  project_status.txt  - REAL results obtained so far (required for --type empirical)
  verify_claims.txt   - numbers to verify against the sources (one per line)
"""
import argparse
import sys

from pipeline import config
LLM_STEPS = ("extract", "analyze", "write", "review", "fix")


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("topic", nargs="?", default="Paper topic")
    p.add_argument("venue", nargs="?", default="Target venue")
    p.add_argument("--step", choices=[*LLM_STEPS, "literature", "lint", "gate", "latex", "pdf", "all"], default="all")
    p.add_argument("--type", choices=["position", "empirical"], help="position = no results of our own")
    p.add_argument("--name", help="the ONE name of the proposed framework")
    p.add_argument("--pages", type=int, help="page limit (target length ~550 words/page)")
    p.add_argument("--words", type=int, help="target body length in words")
    p.add_argument("--template", help="template / venue name (informational for the analyst)")
    p.add_argument("--draft", help="existing draft to audit (consistency, change log)")
    p.add_argument("--template-dir", help="venue template folder (.cls/.sty/.bst, optional template.json)")
    p.add_argument("--anonymous", action="store_true", help="anonymous submission: no author names in the LaTeX")
    p.add_argument("--bib", help="BibTeX file (default: refs.bib in the project root, if present)")
    p.add_argument("--author", help="authors for LaTeX (default: Anonymous Authors)")
    p.add_argument("--twocolumn", action="store_true", help="two-column LaTeX")
    p.add_argument("--fresh", action="store_true", help="delete analysis, sections and draft before running")
    p.add_argument("--strict-extract", action="store_true", help="fail if a sheet is truncated or unparsable")
    p.add_argument("--no-fix", action="store_true", help="skip the automatic fix loop in the full run")
    p.add_argument("--no-literature", action="store_true", help="skip arXiv/DBLP lookup in the full run")
    p.add_argument("--download", action="store_true", help="literature: download found arXiv PDFs into papers/")
    p.add_argument("--force", action="store_true", help="export even if the quality gate has blockers")
    p.add_argument("--allow-fallback", action="store_true", help="PDF: allow TikZ-as-text retry / HTML fallback")
    return p


def apply_args(a):
    if a.type:
        config.PAPER_TYPE = a.type
    if a.name:
        config.FRAMEWORK_NAME = a.name
    if a.template:
        config.TEMPLATE = a.template
    if a.pages:
        config.PAGE_LIMIT = str(a.pages)
        config.TARGET_WORDS = int(a.pages * 550)     # rough: excludes references and figures
    if a.words:
        config.TARGET_WORDS = a.words
    if a.draft:
        config.PREVIOUS_DRAFT = a.draft


def _final_notes():
    """Repeat what a human must still do: missing related work, novelty and type warnings."""
    import json
    if not config.ANALYSIS_FILE.exists():
        return
    an = json.loads(config.ANALYSIS_FILE.read_text(encoding="utf-8"))
    for w in an.get("missing_related_work", []):
        print(f"[todo] missing related work: {w}")
    if (an.get("novelty_statement") or {}).get("distinguishable") is False:
        print("[todo] !!! novelty not distinguishable from related work; sharpen it (see analysis.json)")


def main(argv=None):
    a = build_parser().parse_args(argv)
    apply_args(a)
    config.ensure_dirs()
    step = a.step
    if config.PAPER_TYPE == "empirical" and not config.STATUS_FILE.exists():
        raise SystemExit("Type 'empirical' needs real results: create project_status.txt, or use --type position.")
    if step in LLM_STEPS or step == "all":
        config.require_api_key()

    from pipeline import cache, export_latex, export_pdf, fixloop, gate, lint   # noqa: E401  (after config is set)
    from pipeline.agents import analyst, extractor, literature, reviewer, writer

    try:
        if a.fresh:
            cache.fresh()
        elif step in ("analyze", "write", "all"):
            cache.check(a.topic)
        if step in ("extract", "all"):
            extractor.run(strict=a.strict_extract)
        if step in ("analyze", "all"):
            analyst.run(a.topic)
        if step == "literature" or (step == "all" and not a.no_literature):
            literature.run(download=a.download)
        if step in ("write", "all"):
            writer.run(a.topic, a.venue)
        if step in ("analyze", "write", "all"):
            cache.save(a.topic)
        if step in ("review", "all"):
            reviewer.run()
        if step == "fix" or (step == "all" and not a.no_fix):
            left = fixloop.run()
            if left:
                print(f"[fix] {len(left)} blocker(s) remain after the fix loop")
        if step == "lint":
            lint.run()
        if step in ("gate", "latex", "pdf", "all"):
            gate.run(force=a.force)
        if step in ("latex", "all"):
            export_latex.convert_file(author=a.author, twocolumn=a.twocolumn, template_dir=a.template_dir,
                                      anonymous=a.anonymous, bib_file=a.bib)
        if step in ("pdf", "all"):
            export_pdf.run(allow_fallback=a.allow_fallback)
    except (gate.GateError, export_latex.LatexExportError, extractor.ExtractError, RuntimeError) as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    _final_notes()
    print("Done. See the out/ folder; human checklist: README.md, out/human_todo.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
