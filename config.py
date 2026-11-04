import os
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY nu a fost găsită în .env!")

os.environ["GEMINI_API_KEY"] = api_key

# Model valid — Google recomandă gemini-3.8-flash pentru utilizatori noi
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini/gemini-3.8-flash")

gemini_llm = LLM(
    model=MODEL_NAME,
    api_key=api_key,
    temperature=0.4,
    max_retries=5,        # era 2
    request_timeout=90    # era 60
)

gemini_llm_writer = LLM(
    model=MODEL_NAME,
    api_key=api_key,
    temperature=0.2,
    max_retries=5,        # era 2
    request_timeout=90    # era 60
)