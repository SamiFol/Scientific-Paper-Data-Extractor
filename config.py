"""Setari comune: modele, foldere, chei API, lungimi tinta."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # citeste .env din folderul curent

# --- API (ajunge o singura cheie; modelele fara cheie sunt sarite) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not any([GEMINI_API_KEY, MISTRAL_API_KEY, CEREBRAS_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY]):
    raise SystemExit("Nicio cheie API in .env (vezi .env.example).")

# --- Modele: "provider:model"; fara prefix = gemini (pot fi suprascrise din .env) ---
MODEL_FAST = os.getenv("MODEL_FAST", "gemini:gemini-3.1-flash-lite")     # extractie din PDF-uri
MODEL_SMART = os.getenv("MODEL_SMART", "gemini:gemini-3-flash-preview")  # analiza + scriere

# Daca un model da eroare (429/503/404...), llm.py incearca urmatoarele, in ordine.
# Ordinea conteaza: Cerebras (context mic pe free tier) si Groq (plafon de tokeni/minut)
# se descurca prost cu prompturile mari de la analiza/scriere, deci sunt la coada.
FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv(
        "FALLBACK_MODELS",
        "gemini:gemini-3.1-flash-lite,"
        "gemini:gemini-3-flash-preview,"
        "gemini:gemini-flash-lite-latest,"
        "mistral:mistral-small-latest,"
        "openrouter:meta-llama/llama-3.3-70b-instruct:free,"
        "groq:llama-3.3-70b-versatile,"
        "cerebras:gpt-oss-120b",
    ).split(",")
    if m.strip()
]

# --- Rate limiting ---
PAUSE_SECONDS = float(os.getenv("PAUSE_SECONDS", "4"))  # mareste daca primesti 429

# --- PDF pentru provideri non-Gemini (primesc doar text) ---
MAX_PDF_CHARS = int(os.getenv("MAX_PDF_CHARS", "60000"))  # ~15k tokeni; scade daca primesti 413

# --- Lungimea draftului ---
TARGET_WORDS = int(os.getenv("TARGET_WORDS", "5000"))  # cuvinte in corpul paperului
MAX_OUT_EXTRACT = 24000   # tokeni max de output la extractie (fise detaliate)
MAX_OUT_ANALYZE = 16000
MAX_OUT_WRITE = 8000
# Plafon de output pentru providerii non-Gemini (multi au limite mai mici; scade daca primesti 400)
MAX_OUT_OTHER = int(os.getenv("MAX_OUT_OTHER", "12000"))

# --- Foldere si fisiere ---
PAPERS_DIR = Path("papers")
OUT_DIR = Path("out")
EXTRACTED_DIR = OUT_DIR / "extracted_v3"   # v3 = fise cu model/setting/pagina pentru fiecare cifra
SECTIONS_DIR = OUT_DIR / "sections"
ANALYSIS_FILE = OUT_DIR / "analysis.json"
DRAFT_FILE = OUT_DIR / "paper_draft.md"
LATEX_FILE = OUT_DIR / "paper.tex"
PDF_FILE = OUT_DIR / "paper.pdf"
CLAIMS_FILE = OUT_DIR / "claims_vs_evidence.md"
CHANGELOG_FILE = OUT_DIR / "change_log.md"
HUMAN_FILE = OUT_DIR / "human_todo.md"
LINT_FILE = OUT_DIR / "lint_report.md"

# --- Starea proiectului si tipul paperului (suprascrise din linia de comanda) ---
PAPER_TYPE = os.getenv("PAPER_TYPE", "position")     # position = fara rezultate proprii | empirical
FRAMEWORK_NAME = os.getenv("FRAMEWORK_NAME", "")     # gol = analistul alege UN nume
PAGE_LIMIT = os.getenv("PAGE_LIMIT", "")
TEMPLATE = os.getenv("TEMPLATE", "")
STATUS_FILE = Path("project_status.txt")             # rezultate REALE obtinute pana acum (optional)
VERIFY_FILE = Path("verify_claims.txt")              # cifre de verificat in surse (o linie / cifra)
PREVIOUS_DRAFT = None                                # un draft vechi de auditat (--draft)

EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
SECTIONS_DIR.mkdir(parents=True, exist_ok=True)