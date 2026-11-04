"""Setari comune: modele, foldere, cheie API."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # citeste .env din folderul curent

# --- API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise SystemExit("Lipseste GEMINI_API_KEY. Creeaza fisierul .env (vezi .env.example).")

# --- Modele (pot fi suprascrise din .env) ---
MODEL_FAST = os.getenv("MODEL_FAST", "gemini-3.1-flash-lite")      # extractie din PDF-uri
MODEL_SMART = os.getenv("MODEL_SMART", "gemini-3-flash-preview")   # analiza + scriere

# Daca un model da eroare (404/503), llm.py incearca urmatoarele, in ordine.
FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv(
        "FALLBACK_MODELS",
        "gemini-3.1-flash-lite,gemini-3-flash-preview,gemini-flash-lite-latest",
    ).split(",")
    if m.strip()
]

# --- Rate limiting ---
PAUSE_SECONDS = float(os.getenv("PAUSE_SECONDS", "4"))  # mareste daca primesti 429

# --- Foldere si fisiere ---
PAPERS_DIR = Path("papers")
OUT_DIR = Path("out")
EXTRACTED_DIR = OUT_DIR / "extracted"
ANALYSIS_FILE = OUT_DIR / "analysis.json"
DRAFT_FILE = OUT_DIR / "paper_draft.md"

EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)