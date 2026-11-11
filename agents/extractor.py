"""Agent 1: citeste TOT paperul (cu tabele si appendix) si scoate o fisa foarte detaliata."""
import json

import config
import llm

SYSTEM = """ROLE: EXTRACTOR
Esti un cercetator care construieste o fisa de lectura EXHAUSTIVA a unui paper stiintific.
Citeste intregul document: text, tabele, figuri, appendix. Fisa va fi singura sursa pe care
o vor folosi colegii tai ca sa scrie un paper nou, deci trebuie sa contina toate detaliile utile.

Raspunde DOAR cu JSON valid, cu exact aceste chei:
{
 "title": str, "authors": [str], "year": int, "venue": str, "arxiv_id": str|null,
 "abstract_summary": "5-8 propozitii",
 "problem_and_motivation": "paragraf detaliat: ce problema, de ce conteaza, ce lipsea in literatura",
 "contributions": [str],
 "method": {
   "overview": "paragraf detaliat",
   "components": [{"name": str, "description": "explicatie pas cu pas, 4-8 propozitii",
                   "equations_or_algorithms": "formule/pseudo-cod in text, daca exista"}],
   "settings": "hiperparametri, modele de baza, marimi, date de antrenare, compute"
 },
 "experiments": {
   "tasks_and_datasets": [{"name": str, "description": str, "metric": str}],
   "baselines": [str],
   "setup_details": str
 },
 "results": [{"experiment": str, "comparison": "ce se compara cu ce",
              "numbers": "cifrele EXACTE din tabele/text", "model_size": str|null,
              "setting": "zero-shot/few-shot/finetuned, greedy/beam, benchmark split",
              "where": "pagina / tabel / figura", "takeaway": str}],
 "claims_table": [{"claim": str, "metric": str, "value": "valoarea EXACTA", "benchmark": str,
                   "model_size": str|null, "setting": str, "where": "pagina / tabel"}],
 "ablations_and_analysis": [{"what_varied": str, "finding": str, "numbers": str}],
 "limitations": [str],   // limitarile declarate EXPLICIT de autori
 "failure_modes": [str],
 "future_work": [str],
 "key_claims": [{"claim": str, "where": "sectiune/tabel/figura"}],
 "definitions_and_terms": [{"term": str, "meaning": str}],
 "related_work_positioning": "cum se raporteaza la lucrari anterioare, numind lucrarile",
 "sections_summary": [{"section": str, "summary": "3-6 propozitii"}],
 "figures_and_tables": [{"id": str, "what_it_shows": str, "key_numbers": str}],
 "references_cited": [{"authors_short": str, "title": str, "year": int|null}],
 "reproducibility": "cod, modele, date, resurse"
}
Reguli: copiaza cifrele exact, nu rotunji si nu inventa nimic. Daca o informatie lipseste pune null
sau lista goala. Fii detaliat: fisa completa trebuie sa aiba cel putin 2500 de cuvinte.
references_cited: cele mai importante 15-25 lucrari citate."""


def cite_key(f):
    authors = f.get("authors") or []
    names = []
    for a in authors[:3]:
        a = a.get("name", "") if isinstance(a, dict) else str(a)
        a = a.replace("∗", "").replace("†", "").replace("‡", "").strip()
        names.append(a.split()[-1] if a else "Unknown")
    year = f.get("year") or "n.d."
    if not names:
        return f"[Unknown, {year}]"
    if len(authors) >= 3:
        return f"[{names[0]} et al., {year}]"
    if len(authors) == 2:
        return f"[{names[0]} & {names[1]}, {year}]"
    return f"[{names[0]}, {year}]"


def _extract_one(pdf):
    for attempt in range(2):
        raw = llm.call(config.MODEL_FAST,
                       [llm.pdf_part(pdf), "Construieste fisa exhaustiva a acestui paper."],
                       SYSTEM, json_out=True, max_tokens=config.MAX_OUT_EXTRACT)
        try:
            return json.loads(raw), raw
        except json.JSONDecodeError:
            print(f"  JSON invalid (incercarea {attempt + 1}/2)")
    return None, raw


def run():
    for pdf in sorted(config.PAPERS_DIR.glob("*.pdf")):
        target = config.EXTRACTED_DIR / f"{pdf.stem}.json"
        if target.exists():
            print(f"[1] sar peste {pdf.name} (deja extras)")
            continue
        print(f"[1] extrag detaliat din {pdf.name}")
        data, raw = _extract_one(pdf)
        if data is None:
            (config.EXTRACTED_DIR / f"{pdf.stem}.raw.txt").write_text(raw, encoding="utf-8")
            print(f"  ATENTIE: nu am putut parsa JSON pentru {pdf.name}; vezi .raw.txt")
            continue
        data["source_file"] = pdf.name
        data["cite_key"] = cite_key(data)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        words = len(json.dumps(data, ensure_ascii=False).split())
        print(f"  fisa salvata ({words} cuvinte) -> {data['cite_key']}")


def load_all():
    fise = []
    for p in sorted(config.EXTRACTED_DIR.glob("*.json")):
        f = json.loads(p.read_text(encoding="utf-8"))
        f.setdefault("cite_key", cite_key(f))
        fise.append(f)
    return fise