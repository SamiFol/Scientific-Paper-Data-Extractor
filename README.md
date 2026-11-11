# paper_project

## Layout
    main.py              the only command you run
    pipeline/            all pipeline code (agents/, checks, export, llm, config)
    experiment/          optional ReAct-vs-memory experiment (python -m experiment.run / .analyze)
    tests/               offline tests (python -m pytest -q tests)
    docs/                preregistration
    prompts/             all LLM prompts as readable text files (see prompts/INDEX.txt)
    papers/              your source PDFs
    out/                 generated files (created automatically)
    .env  plan.txt       your keys and plan (copy from the .example files)

Agent pipeline: source PDFs -> sheets -> analysis -> (literature) -> draft -> review -> fix loop -> lint -> **gate** -> LaTeX -> PDF.
Optional `experiment/` subproject produces the only numbers of our own (`out/results.json`).

## Setup
    pip install -r requirements.txt          # + pytest to run the tests
    cp .env.example .env                     # fill at least one key: GEMINI_API_KEY (free) and/or ANTHROPIC_API_KEY (Claude)
    cp plan.txt.example plan.txt             # optional: your own decided plan/budgets (used verbatim)
    python -m pytest -q tests                # offline, no keys needed

## Run order
1. Put PDFs in `papers/`.
2. `python main.py --type position --name MYNAME --pages 8 "Topic" "Venue"` runs everything:
   extract -> analyze -> literature -> write -> review -> fix (max 2 rounds) -> gate -> latex -> pdf.
   Single steps: `--step extract|analyze|literature|write|review|fix|lint|gate|latex|pdf`.
3. Read `out/review.json`, `out/claims_vs_evidence.md`, `out/lint_report.md`, `out/human_todo.md`, `out/reading_list.md`.
4. Experiment (empirical papers):
       python -m experiment.run --data data/hotpot_dev_distractor_v1.json --pilot --n 10   # debug
       # fill docs/preregistration.md, then:  python -m experiment.run --lock
       python -m experiment.run --data data/hotpot_dev_distractor_v1.json                  # main (prints call/cost estimate)
       python -m experiment.analyze                                                        # writes out/results.json
   then re-run `python main.py --fresh --step write ...` so the writer can use `results.json`.

## Using Claude
Put `ANTHROPIC_API_KEY=...` in `.env`. To make Claude the main model also add
`MODEL_FAST=anthropic:claude-haiku-5-5` and `MODEL_SMART=anthropic:claude-sonnet-5-5`.
Without those lines Claude is only a last-resort fallback after the free models.

## Useful flags
`--fresh` (drop analysis/sections/draft) · `--strict-extract` · `--force` (export despite gate blockers, loud) ·
`--no-fix` · `--no-literature` · `--download` (fetch arXiv PDFs) · `--template-dir DIR` · `--anonymous` · `--bib FILE` ·
`--allow-fallback` (PDF: TikZ-as-text / HTML, draft quality only).

## Rules the code enforces
- No result of our own without `results.json`/`plan.txt`; every number in a cited sentence must be in the cited sheet.
- Export is blocked by: placeholders, unsupported own-results claims, unknown citations, numbers not in the cited source,
  untraced result-like numbers, unsupported claims or abstract/conclusion mismatches in the review, a stale review.
- `refs.bib` contains only references resolved from a real record (PDF metadata, arXiv, DBLP).
- LaTeX export fails on `[TODO]` and unresolved citations; PDF build fails if LaTeX fails.

## Human checklist before submitting
- [ ] Read the whole paper; check every claim in `claims_vs_evidence.md` against the PDF.
- [ ] Add the PDFs listed in `out/reading_list.md`, re-run extract/analyze, check `missing_related_work` is empty.
- [ ] Sheets marked `"truncated": true` or extracted by a weaker fallback model: re-extract (`--strict-extract`).
- [ ] Run the real experiment, or keep the paper a position paper; never edit `results.json` by hand.
- [ ] Download the venue template, run with `--template-dir`, `--anonymous` if double-blind; check page limit and format.
- [ ] Verify every entry in `refs.bib` (key, venue, year); fix author names.
- [ ] Figures: open the PDF and check TikZ diagrams.
- [ ] Check ethics/compute/reproducibility statements the venue requires; write the acknowledgments yourself.
