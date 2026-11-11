"""Shared settings: models, paths, API keys, length targets."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")   # .env in the project root
load_dotenv()                                                   # or in the current folder

# --- API keys (one is enough; models without a key are skipped) ---
API_KEY_VARS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY", "CEREBRAS_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")      # Claude
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def has_api_key():
    return any(globals().get(v) or os.getenv(v) for v in API_KEY_VARS)


def require_api_key():
    """Call before any LLM step; tests and export-only runs do not need a key."""
    if not has_api_key():
        raise SystemExit("No API key set in .env (see .env.example).")


# --- Models: "provider:model"; no prefix = gemini (override via .env). Claude: MODEL_SMART=anthropic:claude-sonnet-5-5 ---
MODEL_FAST = os.getenv("MODEL_FAST", "gemini:gemini-3.1-flash-lite")     # PDF extraction
MODEL_SMART = os.getenv("MODEL_SMART", "gemini:gemini-3-flash-preview")  # analysis + writing

# On errors (429/503/404...) llm.py tries the next model in order.
# Cerebras (small context) and Groq (tokens/minute cap) cope badly with big prompts, so they come last.
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
        "cerebras:gpt-oss-120b,"
        "anthropic:claude-sonnet-5-5",        # used last, only if ANTHROPIC_API_KEY is set
    ).split(",")
    if m.strip()
]

PAUSE_SECONDS = float(os.getenv("PAUSE_SECONDS", "4"))      # raise on 429
MAX_PDF_CHARS = int(os.getenv("MAX_PDF_CHARS", "60000"))    # PDF text for non-Gemini providers (~15k tokens)

# --- Draft length ---
TARGET_WORDS = int(os.getenv("TARGET_WORDS", "5000"))       # words in the paper body
MAX_OUT_EXTRACT = 24000   # max output tokens for detailed sheets
MAX_OUT_ANALYZE = 16000
MAX_OUT_WRITE = 8000
MAX_OUT_OTHER = int(os.getenv("MAX_OUT_OTHER", "12000"))    # output cap for non-Gemini providers

# --- Paper settings (overridden from the command line) ---
PAPER_TYPE = os.getenv("PAPER_TYPE", "position")     # position = no results of our own | empirical
FRAMEWORK_NAME = os.getenv("FRAMEWORK_NAME", "")     # empty = the analyst picks ONE name
PAGE_LIMIT = os.getenv("PAGE_LIMIT", "")
TEMPLATE = os.getenv("TEMPLATE", "")
PREVIOUS_DRAFT = None                                # old draft to audit (--draft)


def page_limit():
    """PAGE_LIMIT as int, or None when unset or invalid."""
    return int(PAGE_LIMIT) if PAGE_LIMIT.isdigit() else None


def _apply_root(root):
    root = Path(root)
    g = globals()
    g["ROOT"] = root
    g["PAPERS_DIR"] = root / "papers"
    g["OUT_DIR"] = root / "out"
    out = g["OUT_DIR"]
    g["EXTRACTED_DIR"] = out / "extracted_v3"   # v3 = sheets with model/setting/page per number
    g["SECTIONS_DIR"] = out / "sections"
    g["ANALYSIS_FILE"] = out / "analysis.json"
    g["DRAFT_FILE"] = out / "paper_draft.md"
    g["LATEX_FILE"] = out / "paper.tex"
    g["PDF_FILE"] = out / "paper.pdf"
    g["CLAIMS_FILE"] = out / "claims_vs_evidence.md"
    g["CHANGELOG_FILE"] = out / "change_log.md"
    g["HUMAN_FILE"] = out / "human_todo.md"
    g["LINT_FILE"] = out / "lint_report.md"
    g["REVIEW_FILE"] = out / "review.json"       # reviewer output, read by the gate
    g["STATUS_FILE"] = root / "project_status.txt"   # REAL results so far (needed for --type empirical)
    g["VERIFY_FILE"] = root / "verify_claims.txt"    # numbers to verify in the sources, one per line
    g["PLAN_FILE"] = root / "plan.txt"               # author-decided targets/budgets, used verbatim
    g["RESULTS_FILE"] = out / "results.json"         # real measurements (written by experiment analysis)


def set_root(root):
    """Point every input/output path at `root` (used by tests)."""
    _apply_root(root)


def ensure_dirs():
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)


_apply_root(".")
