"""Punct de intrare.
  python main.py "Tema" "Conferinta"                       # tot pipeline-ul, pana la PDF
  python main.py --step extract|analyze|write|review|lint|latex|pdf "Tema" "Conf"
  python main.py --type position --name RCTA --pages 8 "Tema" "Conf"
  python main.py --draft vechi.md "Tema" "Conf"            # audit + rescriere a unui draft existent
Fisiere optionale in folderul proiectului:
  project_status.txt  - rezultate REALE obtinute pana acum (necesar pentru --type empirical)
  verify_claims.txt   - cifre de verificat in surse (o linie / cifra)
"""
import argparse

import config

p = argparse.ArgumentParser()
p.add_argument("topic", nargs="?", default="Tema lucrarii")
p.add_argument("venue", nargs="?", default="Conferinta tinta")
p.add_argument("--step", choices=["extract", "analyze", "write", "review", "lint", "latex", "pdf", "all"],
               default="all")
p.add_argument("--type", choices=["position", "empirical"], help="position = fara rezultate proprii")
p.add_argument("--name", help="numele UNIC al framework-ului propus")
p.add_argument("--pages", type=int, help="limita de pagini (seteaza lungimea tinta ~550 cuvinte/pagina)")
p.add_argument("--words", type=int, help="lungime tinta (cuvinte) pentru corpul paperului")
p.add_argument("--template", help="numele sablonului / conferintei (informativ pentru analist)")
p.add_argument("--draft", help="draft existent de auditat (consistenta, change log)")
p.add_argument("--author", help="autorii pentru LaTeX (implicit: Anonymous Authors)")
p.add_argument("--twocolumn", action="store_true", help="LaTeX pe 2 coloane")
a = p.parse_args()

if a.type:
    config.PAPER_TYPE = a.type
if a.name:
    config.FRAMEWORK_NAME = a.name
if a.template:
    config.TEMPLATE = a.template
if a.pages:
    config.PAGE_LIMIT = str(a.pages)
    config.TARGET_WORDS = int(a.pages * 550)      # estimare: fara referinte si figuri
if a.words:
    config.TARGET_WORDS = a.words
if a.draft:
    config.PREVIOUS_DRAFT = a.draft

if config.PAPER_TYPE == "empirical" and not config.STATUS_FILE.exists():
    raise SystemExit("Tip 'empirical' cere rezultate reale: creeaza project_status.txt cu ele, "
                     "sau foloseste --type position.")

import export_latex, export_pdf, lint                      # noqa: E402  (dupa setarea config)
from agents import analyst, extractor, reviewer, writer    # noqa: E402

if a.step in ("extract", "all"):
    extractor.run()
if a.step in ("analyze", "all"):
    analyst.run(a.topic)
if a.step in ("write", "all"):
    writer.run(a.topic, a.venue)
if a.step in ("review", "all"):
    reviewer.run()
if a.step == "lint":
    lint.run()
if a.step in ("latex", "all"):
    export_latex.convert_file(author=a.author, twocolumn=a.twocolumn)
if a.step in ("pdf", "all"):
    try:
        export_pdf.run()
    except RuntimeError as e:   # PDF-ul nu trebuie sa strice restul rezultatelor
        print(f"[pdf] {e}")
print("Gata. Vezi folderul out/")