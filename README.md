# Academic Multi-Agent Paper Generator

Sistem multi-agent bazat pe **CrewAI** și **Google Gemini API** care analizează lucrări
științifice existente, identifică un gap de cercetare și generează automat un articol
nou în format **LaTeX**.

## 🏗️ Structura Echipei de Agenți

1. **Research Specialist** — extrage concepte, rezultate și limitări din textele sursă.
2. **Academic Strategist** — sintetizează informația, formulează o ipoteză nouă și creează outline-ul.
3. **Lead Academic Writer** — redactează articolul complet direct în cod LaTeX.

---

## 🚀 Instalare și Rulare

### 1. Clonare și configurare mediu

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt