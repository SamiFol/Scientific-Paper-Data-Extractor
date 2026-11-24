# fallback_llm.py
import os
import time
from typing import Any, Optional

from crewai import LLM, BaseLLM

# WORKAROUND pentru bug-ul CrewAI #5886: cache_breakpoint injectat la Groq
import crewai.llms.cache as _crewai_cache

_crewai_cache.mark_cache_breakpoint = lambda msg: msg

# Lanț de fallback actualizat cu modele gratuite STABILE
FALLBACK_CHAIN = [
    # 1. Groq - Foarte rapid
    ("groq/openai/gpt-oss-120b", "GROQ_API_KEY", "groq"),

    # 2. OpenRouter - Modele care sunt active ACUM
    ("openrouter/meta-llama/llama-3.3-70b-instruct:free", "OPENROUTER_API_KEY", "openrouter"),
    ("openrouter/qwen/qwen-2.5-72b-instruct:free", "OPENROUTER_API_KEY", "openrouter"),
    ("openrouter/mistralai/mistral-7b-instruct:free", "OPENROUTER_API_KEY", "openrouter"),
]


class FallbackLLM(BaseLLM):
    def __init__(
            self,
            model: str = "fallback-chain",
            temperature: float = 0.4,
            max_retries_per_model: int = 2,
            max_tokens=8192
    ):
        super().__init__(model=model, temperature=temperature)
        self.max_retries_per_model = max_retries_per_model
        self._clients: dict[str, LLM] = {}

        for model_name, key_env, provider in FALLBACK_CHAIN:
            api_key = os.getenv(key_env)
            if not api_key:
                print(f"[FallbackLLM] Sar peste {provider}: {key_env} lipsește din .env")
                continue
            self._clients[model_name] = LLM(
                model=model_name,
                api_key=api_key,
                temperature=temperature,
                max_retries=1,
                timeout=120,  # Am crescut timeout-ul pentru Writer
            )

        if not self._clients:
            raise ValueError("Niciun model din lanț nu are cheie API configurată.")

    def call(self, messages, tools=None, **kwargs) -> str:
        last_error: Optional[Exception] = None
        for model_name, client in self._clients.items():
            for attempt in range(self.max_retries_per_model):
                try:
                    print(f"[FallbackLLM] Încerc {model_name} (attempt {attempt + 1})")
                    return client.call(messages=messages, tools=tools, **kwargs)
                except Exception as e:
                    last_error = e
                    print(f"[FallbackLLM] {model_name} a eșuat: {type(e).__name__}: {e}")

                    # Dacă e Rate Limit (429), așteptăm 5 secunde ÎNAINTE de a reîncerca
                    if "429" in str(e) or "RateLimitError" in type(e).__name__:
                        print("[FallbackLLM] Rate limit atins. Aștept 5 secunde...")
                        time.sleep(5)

                    # Dacă e 404 (model dispărut) trecem direct la următorul
                    if "404" in str(e) or "NotFound" in type(e).__name__:
                        break

        raise RuntimeError(f"Toate modelele au eșuat. Ultima eroare: {last_error}") from last_error

    def supports_function_calling(self) -> bool:
        return True

    def supports_stop_words(self) -> bool:
        return True

    def get_context_window_size(self) -> int:
        return 128000