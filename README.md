# 📄 Academic Multi-Agent Paper Generator

Un sistem automatizat bazat pe **CrewAI** și modele LLM avansate care analizează lucrări științifice, identifică un "research gap" și generează un draft complet în format **LaTeX**. 

Proiectul implementează un lanț de fallback robust între mai mulți provideri (Groq, OpenRouter, Gemini) pentru a asigura funcționarea continuă, indiferent de limitele de rată (rate limits) sau erorile 503/429. Include și un **Server MCP (Model Context Protocol)** complet, însoțit de propriul său Client UI.

## 🏗️ Arhitectura Sistemului

Proiectul folosește 3 agenți specializați care lucrează secvențial:
1. **Academic Research Specialist**: Extrage metodologii, rezultate, dataset-uri și limitări.
2. **Academic Strategist**: Identifică o nișă de cercetare și creează un outline detaliat.
3. **Lead Academic Writer**: Scrie articolul complet în LaTeX, cu ecuații și tabele.

**Sistemul de Fallback:** Dacă un model pică (ex. eroare de rețea, limită atinsă), sistemul încearcă automat următorul model din lanț (Groq -> OpenRouter -> Gemini), cu retry logic și auto-reparare a codului LaTeX (adaugă `\end{document}` automat dacă modelul se taie la final).

## 📁 Structura Proiectului

- `paper_crew.py` - Logica principală (orchestrarea agenților, sync & async)
- `fallback_llm.py` - Sistemul de fallback între modele
- `agent_*.py` / `tasks.py` - Definirea celor 3 agenți și a sarcinilor lor
- `mcp_server.py` - Serverul MCP care expune pipeline-ul ca unelte (tools)
- **Interfețe (UI/CLI):**
  - `app.py` - UI Streamlit general (apelează direct pipeline-ul)
  - `mcp_client_ui.py` - UI Streamlit care acționează ca **MCP Client** (comunică cu serverul prin JSON-RPC)
  - `paper_generator.ipynb` - Notebook Jupyter pentru testare
  - `main.py` - Script CLI

## 🚀 Instalare

### 1. Cerințe preliminare
- Python 3.10 - 3.12 (Python 3.13+ nu este încă suportat complet de CrewAI)
- Node.js (opțional, doar pentru MCP Inspector)

### 2. Setup mediu
```bash
python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
pip install streamlit mcp nest_asyncio