# config.py
import os
from dotenv import load_dotenv
from fallback_llm import FallbackLLM

load_dotenv()

gemini_llm = FallbackLLM(temperature=0.4, max_retries_per_model=2)
gemini_llm_writer = FallbackLLM(temperature=0.2, max_retries_per_model=2)