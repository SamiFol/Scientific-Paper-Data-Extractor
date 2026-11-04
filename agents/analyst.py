"""Agent 2: compara fisele, gaseste lacune si propune structura noului paper."""
import json

import config
import llm
from agents.extractor import load_all

SYSTEM = """Esti un analist de literatura stiintifica.
Primesti fisele structurate ale mai multor papers si o tema.
Raspunde DOAR cu JSON valid, cu cheile:
themes (grupari tematice, cu papers asociate), comparison (metode vs rezultate),
gaps (lacune concrete in literatura), contradictions,
proposed_contribution (ce ar putea aduce un paper nou),
outline (lista de sectiuni cu puncte cheie si ce papers se citeaza in fiecare).
Foloseste doar informatiile din fise. Refera papers prin source_file."""


def run(topic):
    fise = load_all()
    print(f"[2] analizez {len(fise)} papers")
    prompt = f"Tema: {topic}\n\nFise:\n{json.dumps(fise, ensure_ascii=False)}"
    raw = llm.call(config.MODEL_SMART, prompt, SYSTEM, json_out=True)
    config.ANALYSIS_FILE.write_text(raw, encoding="utf-8")
    return json.loads(raw)