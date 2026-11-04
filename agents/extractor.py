"""Agent 1: citeste PDF-urile si scoate informatie structurata (JSON)."""
import json

import config
import llm

SYSTEM = """Esti un cercetator care extrage informatii dintr-un paper stiintific.
Raspunde DOAR cu JSON valid, cu cheile:
title, authors, year, venue, problem, method, datasets, key_results,
limitations, future_work, key_claims (lista), references_cited (lista scurta).
Nu inventa nimic: daca informatia lipseste, pune null."""


def run():
    for pdf in sorted(config.PAPERS_DIR.glob("*.pdf")):
        target = config.EXTRACTED_DIR / f"{pdf.stem}.json"
        if target.exists():  # nu repeta apeluri deja facute
            print(f"[1] sar peste {pdf.name} (deja extras)")
            continue
        print(f"[1] extrag din {pdf.name}")
        raw = llm.call(config.MODEL_FAST,
                       [llm.pdf_part(pdf), "Extrage informatiile cerute."],
                       SYSTEM, json_out=True)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"parse_error": True, "raw": raw}
        data["source_file"] = pdf.name
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_all():
    """Citeste toate fisele extrase (folosit de ceilalti agenti)."""
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(config.EXTRACTED_DIR.glob("*.json"))]