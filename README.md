# Academic Multi-Agent Paper Generator

Sistem multi-agent bazat pe **CrewAI** și **Google Gemini API** care analizează lucrări științifice existente, identifică un gap de cercetare și generează automat un articol nou în format **LaTeX**.

## 🏗️ Structura Echipei de Agenți

1. **Research Specialist (Agent 1):** Extrage concepte, rezultate și limitări din textele sursă furnizate.
2. **Academic Strategist (Agent 2):** Sintetizează informația, formulează o ipoteză nouă și creează outline-ul articolului.
3. **Lead Academic Writer (Agent 3):** Redactează articolul complet direct în cod LaTeX gata de compilat.

---

## 🚀 Instalare și Rulare

### 1. Clonare și configurare mediu
```bash
# Creează un mediu virtual
python -m venv venv

# Activează mediul (Linux/Mac)
source venv/bin/activate
# Activează mediul (Windows)
venv\Scripts\activate

# Instalează dependențele
pip install -r requirements.txt