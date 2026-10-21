# 📄 Plan de Proiect & Arhitectură: Scientific Paper Multi-Agent Generator

Sistem automatizat bazat pe **CrewAI** și **Google Gemini API** pentru analiza lucrărilor științifice din format PDF, identificarea oportunităților de cercetare și redactarea unui nou articol în format **LaTeX**.

---

## 🏗️ 1. Arhitectura Sistemului și Fluxul de Date

```
┌────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────┐      ┌──────────────────────┐
│ Folder /papers │ ───> │ Modul pdf_reader.py     │ ───> │ Agent 1 (Researcher)    │ ───> │ Agent 2 (Strategist)│ ───> │ Agent 3 (Writer)     │ ───> generated_paper.tex
│ (Fișiere PDF)  │      │ Extragere text brut     │      │ Extragere date cheie    │      │ Identificare gap    │      │ Generează cod LaTeX  │
└────────────────┘      └─────────────────────────┘      └─────────────────────────┘      └─────────────────────┘      └──────────────────────┘
```

---

## 🤖 2. Detalii și Responsabilități Agenți

### 🔹 Agent 1: Academic Research Specialist (`agent_researcher.py`)
* **Misiune:** Procesarea textului brut obținut din fișierele PDF.
* **Input:** Conținutul extras din articole de `pdf_reader.py`.
* **Sarcini (Task):**
  * Extrage ipotezele și metodologiile utilizate în lucrări.
  * Identifică rezultatele numerice/cantitative obținute.
  * Notează seturile de date (datasets) folosite.
  * Extrage limitările explicite menționate de autori.
* **Output:** Rezumat structurat în format Markdown.

---

### 🔹 Agent 2: Academic Strategist & Architect (`agent_strategist.py`)
* **Misiune:** Analiza sintetică și definirea noii direcții de cercetare.
* **Input:** Rezumatul structurat generat de Agentul 1.
* **Sarcini (Task):**
  * Compară lucrările furnizate și identifică un „research gap” (lipsă/neajuns în literatură).
  * Formulează ipoteza noii lucrări.
  * Adaptează conținutul la profilul conferinței țintă (`target_conference`).
  * Construiește outline-ul detaliat pe secțiuni (Abstract, Introduction, Related Work, Proposed Methodology, Experiments/Expected Results, Conclusion).
* **Output:** Structura și argumentația cadru a noului articol.

---

### 🔹 Agent 3: Lead Academic Writer (`agent_writer.py`)
* **Misiune:** Redactarea academică completă în LaTeX.
* **Input:** Outline-ul și strategia furnizate de Agentul 2.
* **Sarcini (Task):**
  * Redactează textul integral folosind un ton academic formal în limba engleză.
  * Inserează ecuații matematice relevante în sintaxă LaTeX.
  * Creează tabele sintetice în LaTeX pentru compararea rezultatelor.
  * Generează bibliografia și citările în format bibitem/BibTeX.
* **Output:** Fișier `.tex` complet, direct compilabil prin `pdflatex` sau în Overleaf.

---

## 📁 3. Structura Modulară a Proiectului

```text
Scientific-Paper-Data-Extractor/
├── papers/                 # Folder local pentru fișierele PDF de analizat
│   └── .gitkeep
├── .env                    # Chei API confidențiale (GEMINI_API_KEY)
├── .env.example            # Format de exemplu pentru .env
├── .gitignore              # Fișiere ignorate de Git (PDF-uri, .env, venv)
├── config.py               # Inițializare și configurare Gemini LLM
├── pdf_reader.py           # Modul extragere text din PDF-uri (pypdf)
├── agent_researcher.py     # Definire Agent 1
├── agent_strategist.py     # Definire Agent 2
├── agent_writer.py         # Definire Agent 3
├── tasks.py                # Definire sarcinilor (Tasks)
├── main.py                 # Scriptul principal de asamblare și executare
├── requirements.txt        # Dependențe Python
└── PROJECT_PLAN.md         # Documentația planului de proiect
```

---

## 🚀 4. Plan de Implementare & Roadmap

### Phase 1: Setup Mediu & Configurare (Completat)
* [x] Creare mediu virtual Python (Conda/venv).
* [x] Generare cheie API în Google AI Studio.
* [x] Instalare pachete: `crewai`, `pypdf`, `python-dotenv`.
* [x] Configurare arhitectură modulară pe fișiere separate.

### Phase 2: Ingestie Date (Completat)
* [x] Dezvoltare modul `pdf_reader.py` pentru citirea automata a folderului `papers/`.
* [x] Gestionare erori de formatare sau lipsă fișiere.

### Phase 3: Optimizare Prompt-uri & Output (Pasul Curent)
* [ ] Structurare prompt Agent 3 pentru formatarea explicită IEEEtran/ACM.
* [ ] Adăugare salvare automată a rezumatelor intermediare (`summary.md`).
* [ ] Testare pe un set real de 3-4 articole PDF.

### Phase 4: Extindere & Interfață (Viitor)
* [ ] Adăugare interfață grafică simplă (Streamlit/Gradio).
* [ ] Validare automată a codului LaTeX generat (verificare sintaxă).