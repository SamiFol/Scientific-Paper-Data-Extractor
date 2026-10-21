import os
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY nu a fost găsită în .env!")

os.environ["GEMINI_API_KEY"] = api_key

gemini_llm = LLM(
    model="gemini/gemini-3.8-flash",
    api_key=api_key,
    temperature=0.4,
    max_retries=10,       # Reîncearcă automat de 10 ori dacă serverul e aglomerat
    request_timeout=120   # Așteaptă până la 2 minute pentru răspuns
)