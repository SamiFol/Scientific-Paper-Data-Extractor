"""Agent 3: scrie draftul noului paper pe baza analizei."""
import json

import config
import llm
from agents.extractor import load_all

SYSTEM = """Esti autorul unui paper stiintific. Scrii in engleza, stil academic.
Folosesti STRICT analiza si fisele primite; cita doar papers din fise
(format [Autor, An]). Nu inventa rezultate experimentale sau referinte.
Unde lipsesc date, scrie [TODO: ...] ca autorul uman sa completeze."""


def run(topic, venue):
    analysis = json.loads(config.ANALYSIS_FILE.read_text(encoding="utf-8"))
    fise = load_all()
    print("[3] scriu draftul")
    prompt = (
        f"Tema: {topic}\nConferinta tinta: {venue}\n\n"
        f"Analiza:\n{json.dumps(analysis, ensure_ascii=False)}\n\n"
        f"Fise (pentru citari):\n{json.dumps(fise, ensure_ascii=False)}\n\n"
        "Scrie paperul complet in Markdown: Abstract, Introduction, Related Work, "
        "Proposed Approach, Discussion, Conclusion, References."
    )
    draft = llm.call(config.MODEL_SMART, prompt, SYSTEM)
    config.DRAFT_FILE.write_text(draft, encoding="utf-8")